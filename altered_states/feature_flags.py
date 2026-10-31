"""File-backed feature flags with percentage rollout and staleness checks.

Flags let a change ship to a slice of traffic before it reaches everyone, and
let an agent merge work without exposing it to all users at once.

The store is ``feature_flags.json`` at the repository root::

    {"flags": [
      {"name": "site.music_section", "enabled": true, "rollout_percentage": 100,
       "owner": "site", "expires_on": "2027-01-31", "description": "..."}
    ]}

Bucketing is deterministic — ``sha256(name:subject)`` mapped to 0-99 — so a
given visitor always lands in the same bucket and rollouts move monotonically
forward as the percentage increases.

Staleness tooling (``python3 bin/feature_flags.py check``) compares declared
flags against names referenced in the source tree, and flags whose
``expires_on`` has passed. That is the cleanup mechanism: a flag that no code
mentions is dead and must be deleted.

Usage:
    from feature_flags import flags

    if flags.is_enabled("site.music_section"):
        ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FLAG_FILE = REPO_ROOT / "feature_flags.json"
ENV_OVERRIDE_PREFIX = "FLAG_"

# Flag names are referenced in source as quoted string literals.
_FLAG_LITERAL = re.compile(r"[\"']([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)[\"']")

BUCKETS = 100
SOURCE_SUFFIXES = (".py", ".html", ".js", ".mjs")


@dataclass(frozen=True)
class Flag:
    """One declared flag."""

    name: str
    enabled: bool = False
    rollout_percentage: int = 0
    owner: str = "unassigned"
    description: str = ""
    expires_on: str | None = None
    allowlist: tuple[str, ...] = field(default_factory=tuple)
    denylist: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> Flag:
        return cls(
            name=str(raw["name"]),
            enabled=bool(raw.get("enabled", False)),
            rollout_percentage=int(raw.get("rollout_percentage", 0)),
            owner=str(raw.get("owner", "unassigned")),
            description=str(raw.get("description", "")),
            expires_on=raw.get("expires_on") or None,
            allowlist=tuple(raw.get("allowlist", ())),
            denylist=tuple(raw.get("denylist", ())),
        )

    def expired(self, today: date | None = None) -> bool:
        """True when the flag outlived its declared review date."""
        if not self.expires_on:
            return False
        try:
            expiry = date.fromisoformat(self.expires_on)
        except ValueError:
            return True
        return (today or date.today()) >= expiry


def bucket_for(name: str, subject: str) -> int:
    """Deterministic 0-99 bucket for a subject, stable across processes."""
    digest = hashlib.sha256(f"{name}:{subject}".encode()).hexdigest()
    return int(digest[:8], 16) % BUCKETS


class FlagStore:
    """An immutable snapshot of declared flags plus per-subject evaluation."""

    def __init__(self, flags: Iterable[Flag] = (), path: Path | None = None) -> None:
        self._flags: dict[str, Flag] = {flag.name: flag for flag in flags}
        self.path = path

    def __len__(self) -> int:
        return len(self._flags)

    def __contains__(self, name: object) -> bool:
        return name in self._flags

    @property
    def names(self) -> list[str]:
        return sorted(self._flags)

    def get(self, name: str) -> Flag | None:
        return self._flags.get(name)

    def is_enabled(self, name: str, subject: str | None = None) -> bool:
        """Evaluate a flag.

        Unknown flags are treated as off — a typo must never turn a feature on.
        """
        flag = self._flags.get(name)
        if flag is None or not flag.enabled:
            return False
        if subject is not None:
            if subject in flag.denylist:
                return False
            if subject in flag.allowlist:
                return True
            return bucket_for(name, subject) < flag.rollout_percentage
        return flag.rollout_percentage >= BUCKETS

    def load_from_env(self, environ: Mapping[str, str]) -> FlagStore:
        """Apply ``FLAG_<UPPER_NAME>=on|off`` overrides without mutating self."""
        overridden: list[Flag] = []
        for name, flag in self._flags.items():
            env_key = ENV_OVERRIDE_PREFIX + re.sub(r"[^A-Za-z0-9]+", "_", name).upper()
            raw = environ.get(env_key)
            if raw is None:
                overridden.append(flag)
                continue
            enabled = raw.strip().lower() in {"1", "true", "on", "yes"}
            overridden.append(
                Flag(
                    name=flag.name,
                    enabled=enabled,
                    rollout_percentage=BUCKETS if enabled else 0,
                    owner=flag.owner,
                    description=flag.description,
                    expires_on=flag.expires_on,
                    allowlist=flag.allowlist,
                    denylist=flag.denylist,
                )
            )
        return FlagStore(overridden, self.path)

    def expired(self, today: date | None = None) -> list[Flag]:
        return [flag for flag in self._flags.values() if flag.expired(today)]


def load_flags(path: Path | None = None, environ: Mapping[str, str] | None = None) -> FlagStore:
    """Load the flag file. A missing file yields an empty (all-off) store."""
    target = path or DEFAULT_FLAG_FILE
    if not target.exists():
        return FlagStore(path=target)
    raw: dict[str, Any] = json.loads(target.read_text())
    store = FlagStore((Flag.from_mapping(item) for item in raw.get("flags", [])), target)
    return store.load_from_env(environ if environ is not None else os.environ)


def referenced_names(root: Path) -> set[str]:
    """Every dotted flag-shaped literal quoted anywhere in the source tree."""
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in {"site", "node_modules", ".git", "tests"} for part in path.parts):
            continue
        try:
            found.update(_FLAG_LITERAL.findall(path.read_text(errors="ignore")))
        except OSError:
            continue
    return found


def unused_flags(store: FlagStore, root: Path = REPO_ROOT) -> list[Flag]:
    """Declared flags that no source file mentions — candidates for deletion."""
    referenced = referenced_names(root)
    return [flag for flag in store._flags.values() if flag.name not in referenced]


def _print_status(store: FlagStore, root: Path) -> int:
    print(f"Declared flags ({len(store)}):")
    for name in store.names:
        flag = store.get(name)
        if flag is None:  # names come from the store, so this cannot happen
            continue
        state = "on" if store.is_enabled(name) else "off"
        print(f"  {name:34s} {state:4s} rollout={flag.rollout_percentage:3d}% owner={flag.owner}")
    problems = 0
    for flag in store.expired():
        print(f"  EXPIRED: {flag.name} (expires_on={flag.expires_on}) — delete or re-dated")
        problems += 1
    for flag in unused_flags(store, root):
        print(f"  DEAD: {flag.name} is declared but never referenced — delete it")
        problems += 1
    return 1 if problems else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and validate feature flags.")
    parser.add_argument("--file", type=Path, default=DEFAULT_FLAG_FILE)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("show", help="print every flag and its state")
    evaluate = sub.add_parser("eval", help="evaluate one flag for a subject")
    evaluate.add_argument("name")
    evaluate.add_argument("--subject", default=None)
    sub.add_parser("check", help="fail when a flag is expired or unused")
    args = parser.parse_args(argv)

    store = load_flags(args.file)

    if args.command == "eval":
        decided = store.is_enabled(args.name, args.subject)
        print(f"{args.name} subject={args.subject!r} -> {'on' if decided else 'off'}")
        return 0
    if args.command == "check":
        return _print_status(store, REPO_ROOT)
    _print_status(store, REPO_ROOT)
    return 0


FLAGS_FILE = DEFAULT_FLAG_FILE
flags = load_flags()


if __name__ == "__main__":
    sys.exit(main())

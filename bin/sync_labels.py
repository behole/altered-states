#!/usr/bin/env python3
"""Reconcile GitHub labels with ``.github/labels.yml``.

Declarative: the YAML file is the source of truth. Labels listed there are
created or updated; managed labels (those under ``managed_prefixes`` or named in
``managed_names``) that are *absent* from the file are deleted, so the taxonomy
cannot drift. Labels outside the managed set are left alone.

Usage:
    python bin/sync_labels.py --dry-run     # show the plan, change nothing
    python bin/sync_labels.py               # apply it (needs `gh` on PATH)

Requires PyYAML: run via ``uvx --with pyyaml==6.0.2 python bin/sync_labels.py``
or ``make labels``.

The only process this starts is the `gh` CLI, located with `shutil.which` and
run with a literal argv and no shell, so nothing here interpolates untrusted
input (`# nosec B404` above marks that deliberate).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LABELS_FILE = REPO_ROOT / ".github" / "labels.yml"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_MISSING_TOOL = 2


@dataclass(frozen=True)
class DesiredLabel:
    """One label as declared in labels.yml."""

    name: str
    color: str
    description: str

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> DesiredLabel:
        name = str(raw["name"]).strip()
        if not name:
            raise ValueError("a label needs a non-empty name")
        return cls(
            name=name,
            color=str(raw.get("color", "ededed")).lstrip("#"),
            description=str(raw.get("description", "")),
        )


@dataclass(frozen=True)
class Plan:
    """What the sync would do, so it can be reviewed before it runs."""

    create: tuple[DesiredLabel, ...]
    update: tuple[DesiredLabel, ...]
    delete: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.create or self.update or self.delete)

    def summary(self) -> str:
        return (
            f"{len(self.create)} to create, {len(self.update)} to update, "
            f"{len(self.delete)} to delete, {len(self.unchanged)} unchanged"
        )


def _load_yaml(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = yaml.safe_load(path.read_text())
    return parsed


def desired_labels(config: dict[str, Any]) -> list[DesiredLabel]:
    """Parse the declared labels, rejecting duplicate names."""
    labels = [DesiredLabel.from_mapping(raw) for raw in config.get("labels", [])]
    seen: set[str] = set()
    for label in labels:
        if label.name in seen:
            raise ValueError(f"duplicate label declared: {label.name}")
        seen.add(label.name)
    return labels


def is_managed(name: str, config: dict[str, Any]) -> bool:
    """True when this file owns the label and may delete it."""
    if name in {str(item) for item in config.get("keep", [])}:
        return False
    if name in {str(item) for item in config.get("managed_names", [])}:
        return True
    return any(name.startswith(str(prefix)) for prefix in config.get("managed_prefixes", []))


def build_plan(config: dict[str, Any], existing: list[dict[str, Any]]) -> Plan:
    """Diff the declared labels against what the repository currently has."""
    wanted = desired_labels(config)
    current = {str(item["name"]): item for item in existing}
    wanted_names = {label.name for label in wanted}

    create = tuple(label for label in wanted if label.name not in current)
    update = tuple(
        label
        for label in wanted
        if label.name in current
        and (
            label.color.lower() != str(current[label.name].get("color", "")).lstrip("#").lower()
            or label.description != str(current[label.name].get("description") or "")
        )
    )
    changed = {label.name for label in create} | {label.name for label in update}
    unchanged = tuple(label.name for label in wanted if label.name not in changed)
    delete = tuple(sorted(name for name in current if name not in wanted_names and is_managed(name, config)))
    return Plan(create=create, update=update, delete=delete, unchanged=unchanged)


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    gh = shutil.which("gh")
    if gh is None:
        raise SystemExit("The GitHub CLI (`gh`) is required to apply label changes.")
    # Fixed argv, resolved executable, no shell.
    return subprocess.run(  # nosec B603
        [gh, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def fetch_existing() -> list[dict[str, Any]]:
    """Current labels from the API, or an empty list when `gh` is unavailable."""
    result = _gh("label", "list", "--limit", "200", "--json", "name,color,description")
    if result.returncode != 0:
        raise SystemExit(f"could not list labels:\n{result.stderr.strip()}")
    payload: list[dict[str, Any]] = json.loads(result.stdout or "[]")
    return payload


def apply_plan(plan: Plan) -> int:
    """Execute the plan. Returns the number of failed operations."""
    failures = 0
    for label in plan.create:
        result = _gh("label", "create", label.name, "--color", label.color, "--description", label.description)
        print(("  created " if result.returncode == 0 else "  FAILED  ") + label.name)
        failures += result.returncode != 0
    for label in plan.update:
        result = _gh("label", "edit", label.name, "--color", label.color, "--description", label.description)
        print(("  updated " if result.returncode == 0 else "  FAILED  ") + label.name)
        failures += result.returncode != 0
    for name in plan.delete:
        result = _gh("label", "delete", name, "--yes")
        print(("  deleted " if result.returncode == 0 else "  FAILED  ") + name)
        failures += result.returncode != 0
    return failures


def print_plan(plan: Plan) -> None:
    print(f"Label plan: {plan.summary()}")
    for label in plan.create:
        print(f"  + {label.name} #{label.color}")
    for label in plan.update:
        print(f"  ~ {label.name} #{label.color}")
    for name in plan.delete:
        print(f"  - {name}")
    for name in plan.unchanged:
        print(f"  = {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile GitHub labels with .github/labels.yml")
    parser.add_argument("--file", type=Path, default=LABELS_FILE, help="label taxonomy file")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without changing anything")
    parser.add_argument(
        "--existing",
        type=Path,
        default=None,
        help="JSON file of current labels (offline use; skips the API)",
    )
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"ERROR: {args.file} does not exist", file=sys.stderr)
        return EXIT_USAGE

    config = _load_yaml(args.file)
    if args.existing is not None:
        existing: list[dict[str, Any]] = json.loads(args.existing.read_text() or "[]")
    else:
        existing = fetch_existing()

    plan = build_plan(config, existing)
    print_plan(plan)

    if args.dry_run or plan.is_empty:
        return EXIT_OK

    failures = apply_plan(plan)
    if failures:
        print(f"\n{failures} operation(s) failed", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

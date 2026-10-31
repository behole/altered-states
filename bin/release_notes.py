#!/usr/bin/env python3
"""Generate release notes from conventional commits.

Reads `git log` between two refs, groups the commits by conventional type, and
writes markdown suitable for a GitHub release body. Commits that are not
conventional are still reported — an unclassified change is better than a
silently dropped one, and it is a nudge to write better subjects.

Usage:
    python bin/release_notes.py                          # since the last tag
    python bin/release_notes.py --from v1.4.0 --to HEAD
    python bin/release_notes.py --version v1.5.0 --output notes.md

The only process this starts is `git`, located with `shutil.which` and run with
a literal argv and no shell (`# nosec B404` above marks that deliberate).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXIT_OK = 0
EXIT_USAGE = 2

# Conventional types, in release-note order. `hidden` types are omitted from the
# rendered notes but still counted, so `ci:` spam does not bury user-facing work.
SECTIONS: tuple[tuple[str, str], ...] = (
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("security", "Security"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("build", "Build"),
    ("revert", "Reverts"),
    ("restore", "Restores"),
)

HIDDEN_TYPES = {"chore", "ci", "style"}

SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<summary>.+)$")
RELEASE_SUBJECT = re.compile(r"^(?:chore\(release\)|release):\s*(?P<version>v?\d+\.\d+\.\d+)\s*$", re.IGNORECASE)

COMMIT_SEPARATOR = "\x1e"
FIELD_SEPARATOR = "\x1f"

# `sha<US>subject<US>body`
SHA_INDEX = 0
SUBJECT_INDEX = 1
BODY_INDEX = 2
MIN_COMMIT_FIELDS = 2


KNOWN_TYPES = frozenset(kind for kind, _ in SECTIONS) | HIDDEN_TYPES


@dataclass(frozen=True)
class Commit:
    """One commit reduced to what the release notes need."""

    sha: str
    subject: str
    body: str = ""

    @property
    def _match(self) -> re.Match[str] | None:
        return SUBJECT.match(self.subject)

    @property
    def kind(self) -> str:
        match = self._match
        return match.group("type") if match else "other"

    @property
    def scope(self) -> str:
        match = self._match
        return (match.group("scope") or "") if match else ""

    @property
    def summary(self) -> str:
        match = self._match
        return match.group("summary").strip() if match else self.subject.strip()

    @property
    def is_breaking(self) -> bool:
        match = self._match
        if match is not None and match.group("breaking"):
            return True
        return "BREAKING CHANGE" in self.body

    @property
    def is_release_commit(self) -> bool:
        return bool(RELEASE_SUBJECT.match(self.subject))

    def render(self) -> str:
        scope = f"**{self.scope}:** " if self.scope else ""
        breaking = " **BREAKING**" if self.is_breaking else ""
        return f"- {scope}{self.summary}{breaking} ({self.sha[:7]})"


@dataclass
class Notes:
    """The grouped result."""

    version: str
    commits: list[Commit] = field(default_factory=list)

    def grouped(self) -> dict[str, list[Commit]]:
        groups: dict[str, list[Commit]] = {kind: [] for kind, _ in SECTIONS}
        for commit in self.commits:
            if commit.kind in groups:
                groups[commit.kind].append(commit)
        return groups

    @property
    def breaking(self) -> list[Commit]:
        return [commit for commit in self.commits if commit.is_breaking]

    @property
    def unclassified(self) -> list[Commit]:
        return [commit for commit in self.commits if commit.kind not in KNOWN_TYPES]

    @property
    def user_visible(self) -> list[Commit]:
        return [commit for commit in self.commits if commit.kind in dict(SECTIONS)]

    def render(self) -> str:
        lines = [f"# {self.version}", ""]
        lines.append(f"{len(self.commits)} commit(s), {len(self.user_visible)} user-visible.")
        lines.append("")

        if self.breaking:
            lines.append("## Breaking changes")
            lines.extend(commit.render() for commit in self.breaking)
            lines.append("")

        for kind, title in SECTIONS:
            commits = self.grouped()[kind]
            if not commits:
                continue
            lines.append(f"## {title}")
            lines.extend(commit.render() for commit in sorted(commits, key=lambda c: c.summary.lower()))
            lines.append("")

        if self.unclassified:
            lines.append("## Unclassified")
            lines.append("_Commits that do not follow the conventional-commit format._")
            lines.extend(commit.render() for commit in self.unclassified)
            lines.append("")

        if not any(self.grouped().values()) and not self.breaking:
            lines.append("No user-visible changes in this range.")
        return "\n".join(lines).rstrip() + "\n"


def git(*args: str) -> str:
    """Run git and return stdout, or an empty string on failure."""
    executable = shutil.which("git")
    if executable is None:
        print("ERROR: git is not installed", file=sys.stderr)
        return ""
    # Fixed argv with a resolved executable path and no shell involved.
    result = subprocess.run(  # nosec B603
        [executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: git {' '.join(args)} failed:\n{result.stderr}", file=sys.stderr)
        return ""
    return result.stdout


def latest_tag() -> str | None:
    tag = git("describe", "--tags", "--abbrev=0").strip()
    return tag or None


def read_commits(rev_range: str) -> list[Commit]:
    """Parse `git log` output into commits, newest first."""
    raw = git("log", f"--format=%H{FIELD_SEPARATOR}%s{FIELD_SEPARATOR}%b{COMMIT_SEPARATOR}", rev_range)
    commits: list[Commit] = []
    for record in raw.split(COMMIT_SEPARATOR):
        fields = record.strip().split(FIELD_SEPARATOR)
        if len(fields) < MIN_COMMIT_FIELDS or not fields[SHA_INDEX].strip():
            continue
        commits.append(
            Commit(
                sha=fields[SHA_INDEX].strip(),
                subject=fields[SUBJECT_INDEX].strip(),
                body=fields[BODY_INDEX] if len(fields) > BODY_INDEX else "",
            )
        )
    return commits


def build_notes(version: str, rev_range: str) -> Notes:
    return Notes(version=version, commits=read_commits(rev_range))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate release notes from conventional commits")
    parser.add_argument("--from", dest="since", default=None, help="start ref (default: the last tag)")
    parser.add_argument("--to", dest="until", default="HEAD", help="end ref (default: HEAD)")
    parser.add_argument("--version", default=None, help="version heading (default: the end ref)")
    parser.add_argument("--output", type=Path, default=None, help="write markdown here too")
    args = parser.parse_args(argv)

    since = args.since or latest_tag()
    if since is None:
        print("WARNING: no tags found; using the full history", file=sys.stderr)
        rev_range = args.until
    else:
        rev_range = f"{since}..{args.until}"

    notes = build_notes(args.version or args.until, rev_range)
    rendered = notes.render()

    print(rendered, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

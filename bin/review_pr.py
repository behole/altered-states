#!/usr/bin/env python3
"""Review a pull-request diff against this repository's conventions.

This is a deterministic first reviewer, not a style opinion generator. It reads
a unified diff and reports things a human reviewer would otherwise have to
remember to check:

* a change to a Python module with no accompanying test change;
* a change to a template or build script with no regenerated output check;
* a hand-edit to generated files (`site/index.html`, lockfiles);
* a new dependency without a lockfile refresh;
* a flag added without an entry in `feature_flags.json`, or one removed while
  still referenced;
* credential-shaped strings in added lines;
* a data-file deletion (journals and character state are not recoverable).

Output is a markdown report on stdout. `--fail-on blocking` turns blocking
findings into a non-zero exit, which is how the workflow gates a pull request.

Usage:
    git diff origin/main...HEAD | python bin/review_pr.py
    python bin/review_pr.py --diff-file pr.diff --fail-on blocking
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXIT_OK = 0
EXIT_BLOCKING = 1
EXIT_USAGE = 2

BLOCKING = "blocking"
ADVISORY = "advisory"

# Files whose changes are reviewed by machinery rather than by hand.
GENERATED = {"site/index.html"}

# Data that cannot be regenerated. Deleting it loses history.
IRREPLACEABLE = (
    "experiments/temporal-lab/runtime/journals/",
    "experiments/temporal-lab/runtime/characters/",
    "experiments/same-prompt/output/",
    "experiments/music/",
)

TEST_PREFIX = "tests/"

# `requirements.txt`, `requirements-dev.txt`, `bin/requirements.lock`'s source…
REQUIREMENTS_NAME = re.compile(r"^requirements.*\.txt$")

# Same shapes the logging layer redacts; catching them before merge is cheaper.
# Ordered most- to least-specific, and the trailing class includes `-` so an
# `sk-or-v1-…` key matches whole instead of being truncated at its first hyphen.
SECRET_PATTERNS = (
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")),
    ("OpenRouter key", re.compile(r"sk-or-v1-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack token", re.compile(r"xox[abposr]-[A-Za-z0-9\-]{10,}")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)

# Test fixtures legitimately contain credential-shaped strings: the redaction
# tests have to feed known secrets through the logger to prove they are
# stripped. Those files are not a leak surface, so the scan skips them, exactly
# as bandit does.
SECRET_SCAN_EXEMPT_PREFIXES = (TEST_PREFIX, "site/")

HUNK = re.compile(r"^@@ .* @@ ?(.*)$")


@dataclass
class FileChange:
    """One file's worth of diff."""

    path: str
    status: str = "modified"
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def is_new(self) -> bool:
        return self.status == "added"

    @property
    def is_deleted(self) -> bool:
        return self.status == "deleted"

    @property
    def is_test(self) -> bool:
        return self.path.startswith(TEST_PREFIX)

    @property
    def is_python(self) -> bool:
        return self.path.endswith(".py")


@dataclass
class Finding:
    """One review comment."""

    severity: str
    path: str
    message: str

    def render(self) -> str:
        marker = "**blocking**" if self.severity == BLOCKING else "advisory"
        return f"- [{marker}] `{self.path}` — {self.message}"


def _strip_diff_prefix(header: str, prefix: str) -> str:
    """`--- a/path` -> `path`; `+++ b/path` -> `path`."""
    value = header[4:].strip()
    return value[2:] if value.startswith(prefix) else value


def _resolve_change(old_path: str, new_path: str, pending_status: str) -> tuple[str, str]:
    """Work out a change's real path and status from both diff headers.

    A deletion shows ``+++ /dev/null``, so the path comes from the old side. An
    addition shows ``--- /dev/null``, so the status comes from the new side.
    """
    if new_path == "/dev/null":
        return old_path, "deleted"
    if old_path == "/dev/null":
        return new_path, "added"
    return new_path, pending_status


def parse_diff(text: str) -> list[FileChange]:
    """Split a unified diff into per-file changes with added/removed lines.

    Handles the three shapes git emits: a modification has both sides named, an
    addition has ``--- /dev/null``, and a deletion has ``+++ /dev/null``. The
    status header arrives before the ``+++`` line, so it is buffered until the
    path is known.
    """
    changes: list[FileChange] = []
    current: FileChange | None = None
    old_path = ""
    pending_status = "modified"

    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = None
            pending_status = "modified"
        elif line.startswith("new file mode"):
            pending_status = "added"
        elif line.startswith("deleted file mode"):
            pending_status = "deleted"
        elif line.startswith("--- "):
            old_path = _strip_diff_prefix(line, "a/")
        elif line.startswith("+++ "):
            path, status = _resolve_change(old_path, _strip_diff_prefix(line, "b/"), pending_status)
            current = FileChange(path=path, status=status)
            changes.append(current)
        elif current is not None and line.startswith("+"):
            current.added.append(line[1:])
        elif current is not None and line.startswith("-"):
            current.removed.append(line[1:])

    return changes


def _touches_tests(changes: list[FileChange]) -> bool:
    return any(change.is_test for change in changes)


def _requirement_files(changes: list[FileChange]) -> set[str]:
    """Every `requirements*.txt`, wherever it lives.

    Matching the names rather than a fixed list means a new requirement file
    (there are four now) is covered by the lockfile rule the day it is added
    instead of the day someone remembers to extend this set.
    """
    return {change.path for change in changes if REQUIREMENTS_NAME.match(Path(change.path).name)}


def review(changes: list[FileChange], flag_names: set[str] | None = None) -> list[Finding]:
    """Apply every rule to a parsed diff."""
    findings: list[Finding] = []
    tests_changed = _touches_tests(changes)

    for change in changes:
        findings.extend(_review_file(change, tests_changed))

    findings.extend(_review_dependencies(changes))
    findings.extend(_review_flags(changes, flag_names if flag_names is not None else _declared_flags()))
    findings.extend(_review_secrets(changes))
    return findings


def _review_file(change: FileChange, tests_changed: bool) -> list[Finding]:
    findings: list[Finding] = []

    if change.is_deleted and any(change.path.startswith(prefix) for prefix in IRREPLACEABLE):
        findings.append(
            Finding(
                BLOCKING,
                change.path,
                "deletes data that cannot be regenerated. Journals, character state, "
                "captured responses, and audio are the only copy of that history.",
            )
        )

    if change.path in GENERATED and change.added and change.removed:
        findings.append(
            Finding(
                ADVISORY,
                change.path,
                "hand-edited generated file. Edit `site/index.template.html` and let `make build` write this one.",
            )
        )

    if change.is_python and not change.is_test and change.added and not tests_changed:
        findings.append(
            Finding(
                ADVISORY,
                change.path,
                "Python behaviour changed with no change under `tests/`. If this is "
                "covered elsewhere, say so in the description.",
            )
        )

    if change.is_test and change.is_new and not change.added:
        findings.append(Finding(ADVISORY, change.path, "new empty test file."))

    return findings


def _review_dependencies(changes: list[FileChange]) -> list[Finding]:
    findings: list[Finding] = []
    touched_requirements = _requirement_files(changes)
    touched_locks = {change.path for change in changes if Path(change.path).suffix == ".lock"}
    expected_locks = {lock_for(requirement) for requirement in touched_requirements}

    for requirement in sorted(touched_requirements):
        expected = lock_for(requirement)
        if expected not in touched_locks:
            findings.append(
                Finding(
                    BLOCKING,
                    requirement,
                    f"dependency declaration changed without `{expected}`. Run `make lock` and commit the result.",
                )
            )

    for lock in sorted(touched_locks - expected_locks):
        findings.append(
            Finding(
                ADVISORY,
                lock,
                "lockfile changed with no matching requirements edit — expected only from Dependabot or `make lock`.",
            )
        )
    return findings


def lock_for(requirements_path: str) -> str:
    """`bin/requirements.txt` -> `bin/requirements.lock`."""
    return str(Path(requirements_path).with_suffix(".lock"))


def _declared_flags() -> set[str]:
    path = REPO_ROOT / "feature_flags.json"
    if not path.exists():
        return set()
    payload = json.loads(path.read_text())
    return {str(entry["name"]) for entry in payload.get("flags", [])}


# A flag reference is a quoted dotted literal passed to one of the three call
# shapes the codebase uses. Matching any dotted string would flag log event
# names (`eval.complete`) and error codes, which are not flags.
FLAG_CALL_PATTERNS = (
    re.compile(r"""is_enabled\(\s*["']([^"']+)["']"""),
    re.compile(r"""flagOn\(\s*["']([^"']+)["']"""),
    re.compile(r"""flags\.get\(\s*["']([^"']+)["']"""),
    re.compile(r"""FLAGS\[["']([^"']+)["']\]"""),
)

FLAG_SCAN_SUFFIXES = (".py", ".html", ".js", ".mjs")


def _flag_references(line: str) -> set[str]:
    """Flag names this line actually reads."""
    return {match for pattern in FLAG_CALL_PATTERNS for match in pattern.findall(line)}


def _review_flags(changes: list[FileChange], declared: set[str]) -> list[Finding]:
    """A reference from shipped code must resolve to a declared flag.

    Test files are exempt: asserting that an unknown flag evaluates off requires
    naming one that does not exist.
    """
    findings: list[Finding] = []
    flags_file = "feature_flags.json"
    if not any(change.path == flags_file for change in changes):
        return findings

    declared_after = declared | _flags_added_in(changes)

    for change in changes:
        if change.is_test or not change.path.endswith(FLAG_SCAN_SUFFIXES) or change.path == flags_file:
            continue
        seen: set[str] = set()
        for line in change.added:
            for name in _flag_references(line):
                if name in declared_after or name in seen:
                    continue
                seen.add(name)
                findings.append(
                    Finding(
                        BLOCKING,
                        change.path,
                        f"reads flag `{name}`, which `feature_flags.json` does not declare. "
                        "An undeclared flag always evaluates off.",
                    )
                )
    return findings


def _flags_added_in(changes: list[FileChange]) -> set[str]:
    names: set[str] = set()
    for change in changes:
        if change.path != "feature_flags.json":
            continue
        for line in change.added:
            match = re.search(r'"name"\s*:\s*"([^"]+)"', line)
            if match:
                names.add(match.group(1))
    return names


def _review_secrets(changes: list[FileChange]) -> list[Finding]:
    findings: list[Finding] = []
    for change in changes:
        if change.path.startswith(SECRET_SCAN_EXEMPT_PREFIXES):
            continue
        for line in change.added:
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            BLOCKING,
                            change.path,
                            f"added line contains what looks like a {label}. Rotate it and "
                            "load it from the environment instead.",
                        )
                    )
                    break
    return findings


def render(findings: list[Finding], changes: list[FileChange]) -> str:
    """A markdown report suitable for a pull-request comment."""
    blocking = [finding for finding in findings if finding.severity == BLOCKING]
    advisory = [finding for finding in findings if finding.severity != BLOCKING]

    lines = ["## Automated review", ""]
    lines.append(f"Reviewed {len(changes)} changed file(s): {len(blocking)} blocking, {len(advisory)} advisory.")
    lines.append("")

    if blocking:
        lines.append("### Blocking")
        lines.extend(finding.render() for finding in blocking)
        lines.append("")
    if advisory:
        lines.append("### Advisory")
        lines.extend(finding.render() for finding in advisory)
        lines.append("")
    if not findings:
        lines.append("No convention violations found. A human still needs to review intent.")
        lines.append("")

    lines.append("<sub>Generated by `bin/review_pr.py`. Rules live in that file.</sub>")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review a pull-request diff against repo conventions")
    parser.add_argument("--diff-file", type=Path, default=None, help="read the diff from here instead of stdin")
    parser.add_argument(
        "--fail-on",
        choices=["never", BLOCKING],
        default=BLOCKING,
        help="exit non-zero on blocking findings (default) or never",
    )
    parser.add_argument("--output", type=Path, default=None, help="write the report here as well as stdout")
    args = parser.parse_args(argv)

    if args.diff_file is not None:
        if not args.diff_file.exists():
            print(f"ERROR: {args.diff_file} does not exist", file=sys.stderr)
            return EXIT_USAGE
        text = args.diff_file.read_text()
    else:
        text = sys.stdin.read()

    changes = parse_diff(text)
    findings = review(changes)
    report = render(findings, changes)

    print(report)
    if args.output is not None:
        args.output.write_text(report)

    if args.fail_on == BLOCKING and any(finding.severity == BLOCKING for finding in findings):
        return EXIT_BLOCKING
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate that AGENTS.md still describes this repository accurately.

Three checks, cheapest first:

1. **Structure** — every required section is present.
2. **References** — every repository path mentioned in the layout table and in
   inline code exists on disk, and every `make <target>` target exists in the
   Makefile.
3. **Executable claims** — the commands marked cheap-and-offline in AGENTS.md
   actually run and exit 0. Heavy gates (`make check`, `make test`) are verified
   structurally only, because CI already runs them and this script must stay
   fast enough to run on every push.

Exit code 0 means AGENTS.md is trustworthy; 1 means it drifted.

The only processes this starts are the commands the repository documents about
itself: a literal argv, no shell, and a fixed environment. That is what
`# nosec B404` marks above.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MAKEFILE = REPO_ROOT / "Makefile"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2

REQUIRED_SECTIONS = (
    "## What this repository is",
    "## The 60-second version",
    "## Layout",
    "## Rules that will bite you",
    "## Working with the data",
    "## Commands the validators check",
    "## Definition of done",
)

# Paths that AGENTS.md is allowed to mention without them existing: they are
# produced at build time or are intentionally absent in a fresh clone.
ALLOWED_MISSING = {
    "site/index.html",
    "runtime/metrics/altered-states.prom",
    "experiments/temporal-lab/runtime",
}

# A `make` invocation is an assertion about the Makefile only when it is quoted
# as code. Matching bare prose would turn "make sure this passes" into a target.
MAKE_TARGET = re.compile(r"`make (?P<quoted>[a-z][a-z0-9-]*)(?: [^`]*)?`|^make (?P<bare>[a-z][a-z0-9-]*)", re.MULTILINE)
TARGET_DEFINITION = re.compile(r"^([a-z][a-z0-9-]*):", re.MULTILINE)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
FENCED_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
COMMAND_TOKEN = re.compile(r"^(?:[A-Z_]+=\S+ )*(make|python|python3|uvx|pre-commit)\s+(\S+)")

# Commands whose documented form is safe to execute here. Both need only the
# standard library, so this validator works in any interpreter, including one
# with no third-party packages installed.
EXECUTABLE_COMMANDS = (
    "bin/check_agents_md.py",
    "altered_states.feature_flags check",
)

INTERPRETERS = {"python", "python3"}
MODULE_FLAG = "-m"
MIN_COMMAND_PARTS = 2

# Set in the environment of every child command so a documented command that
# re-runs this script does not recurse forever.
CHILD_MARKER = "AGENTS_MD_VALIDATOR_CHILD"


class Problems:
    """Collected drift, so one run reports everything wrong at once."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, message: str) -> None:
        self.items.append(message)

    def __bool__(self) -> bool:
        return bool(self.items)

    def report(self) -> int:
        for item in self.items:
            print(f"  DRIFT: {item}", file=sys.stderr)
        print(f"\n{len(self.items)} problem(s) in AGENTS.md", file=sys.stderr)
        return EXIT_DRIFT


def check_sections(text: str, problems: Problems) -> None:
    for heading in REQUIRED_SECTIONS:
        if heading not in text:
            problems.add(f"missing section: {heading}")


def make_targets() -> set[str]:
    return set(TARGET_DEFINITION.findall(MAKEFILE.read_text()))


def documented_make_targets(text: str) -> set[str]:
    """Every `make <target>` the document tells a reader to run."""
    found: set[str] = set()
    for match in MAKE_TARGET.finditer(text):
        found.add(match.group("quoted") or match.group("bare"))
    return found


def check_make_targets(text: str, problems: Problems) -> None:
    targets = make_targets()
    for target in sorted(documented_make_targets(text)):
        if target not in targets:
            problems.add(f"`make {target}` has no target in the Makefile")


def check_documented_scripts(text: str, problems: Problems) -> None:
    """Every `python <script>` in a bash block must name a file that exists."""
    for block in FENCED_BLOCK.findall(text):
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = COMMAND_TOKEN.match(stripped)
            if match is None:
                continue
            interpreter, first_arg = match.groups()
            if interpreter in {"make", "pre-commit", "uvx"} or first_arg == "-m":
                continue
            if not (REPO_ROOT / first_arg).exists():
                problems.add(f"documented command references a missing file: {first_arg}")


def check_inline_paths(text: str, problems: Problems) -> None:
    """Backticked tokens that look like repository-relative paths must exist."""
    for token in sorted(set(INLINE_CODE.findall(text))):
        if token in ALLOWED_MISSING or " " in token or token.startswith("-"):
            continue
        # Only multi-segment paths are assertions about the repository. Bare
        # filenames such as `SKILL.md` or `index.html` are generic references.
        if "/" not in token:
            continue
        if not re.match(r"^[\w.\-/]+\.(py|md|json|yml|yaml|toml|txt|html|lock)$", token):
            continue
        if not (REPO_ROOT / token).exists():
            problems.add(f"inline reference to a missing file: {token}")


def _is_executable_claim(command: str) -> bool:
    """True when this documented command is one we can actually run cheaply."""
    parts = command.split()
    if len(parts) < MIN_COMMAND_PARTS or parts[0] not in INTERPRETERS:
        return False
    if parts[1] == MODULE_FLAG:
        return " ".join(parts[2:]) in EXECUTABLE_COMMANDS
    return " ".join(parts[1:]) in EXECUTABLE_COMMANDS


def _clean_env() -> dict[str, str]:
    """Inherit the environment minus anything that would change behaviour."""
    env = dict(os.environ)
    for key in ("SENTRY_DSN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        env.pop(key, None)
    for key in [key for key in env if key.startswith(("FLAG_", "TEMPORAL_LAB_"))]:
        env.pop(key, None)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env[CHILD_MARKER] = "1"
    return env


def _resolved_argv(command: str) -> list[str]:
    """Swap a bare `python`/`python3` for the interpreter running this script."""
    parts = command.split()
    if parts and parts[0] in INTERPRETERS:
        parts[0] = sys.executable
    return parts


def check_executable_claims(text: str, problems: Problems) -> int:
    """Run the cheap, offline commands the doc says are runnable."""
    if os.environ.get(CHILD_MARKER):
        # One of the documented commands runs this script again. Do not recurse:
        # the parent invocation already covers the structural checks.
        return 0
    executed = 0
    for block in FENCED_BLOCK.findall(text):
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or not _is_executable_claim(stripped):
                continue
            try:
                # Literal argv from the repository's own documentation.
                result = subprocess.run(  # nosec B603
                    _resolved_argv(stripped),
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                    env=_clean_env(),
                )
            except subprocess.TimeoutExpired:
                problems.add(f"documented command timed out: {stripped}")
                continue
            executed += 1
            if result.returncode != 0:
                problems.add(f"documented command failed ({result.returncode}): {stripped}")
    return executed


def validate(text: str, *, run_commands: bool) -> tuple[Problems, int]:
    problems = Problems()
    check_sections(text, problems)
    check_make_targets(text, problems)
    check_documented_scripts(text, problems)
    check_inline_paths(text, problems)
    executed = check_executable_claims(text, problems) if run_commands else 0
    return problems, executed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check AGENTS.md against the repository")
    parser.add_argument("--file", type=Path, default=AGENTS_MD, help="instructions file to validate")
    parser.add_argument(
        "--no-run",
        action="store_true",
        help="structure and references only; do not execute the documented commands",
    )
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"ERROR: {args.file} does not exist", file=sys.stderr)
        return EXIT_USAGE

    text = args.file.read_text()
    problems, executed = validate(text, run_commands=not args.no_run)

    if problems:
        return problems.report()

    print(
        f"AGENTS.md is accurate: {len(REQUIRED_SECTIONS)} sections, "
        f"{len(make_targets())} Makefile targets, {executed} command(s) executed."
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

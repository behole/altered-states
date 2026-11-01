#!/usr/bin/env python3
"""One-command installer for the Altered States skill tree.

Copies or symlinks every installable skill (the 11 substances, the router,
and the overlay lines under skills/combos/ and skills/tolerance/) into the
platform-correct skills directory.

Platform defaults (see --help for the same table):

    darwin    ~/.claude/skills
    linux     ~/.config/opencode/skills
    other     no default -- pass --dest

Safety: the default mode is a DRY RUN. It prints the per-skill plan
(source -> resolved destination) and exits 0 without touching the
filesystem. Only ``--apply`` performs the copy (or ``--link`` symlink).
``--dest`` redirects the root, so tests and manual runs never write to a
real home directory. The tool never touches the network or reads any file
outside the skills tree it installs.

Usage:
    python3 bin/install_skills.py                 # plan only (dry run)
    python3 bin/install_skills.py --apply         # copy into the real homes
    python3 bin/install_skills.py --apply --link  # symlink instead of copy
    python3 bin/install_skills.py --apply --dest /tmp/home/skills
    python3 bin/install_skills.py --list          # just enumerate what installs

Exit codes: 0 = plan printed or install completed, 1 = unknown/missing
--skill name, 2 = usage error (bad flags, unsupported platform without
--dest, or a dest that would overwrite the source tree).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"

# Every installable unit: (skill name on the CLI, source path relative to
# skills/, destination name under the skills home). The router installs as
# altered-states-router so its name never collides with a substance skill.
DEFAULT_INSTALLS: tuple[tuple[str, str, str], ...] = (
    ("psilocybin", "psilocybin", "psilocybin"),
    ("lsd", "lsd", "lsd"),
    ("mdma", "mdma", "mdma"),
    ("2c-b", "2c-b", "2c-b"),
    ("dmt", "dmt", "dmt"),
    ("ayahuasca", "ayahuasca", "ayahuasca"),
    ("5-meo-dmt", "5-meo-dmt", "5-meo-dmt"),
    ("mescaline", "mescaline", "mescaline"),
    ("ketamine", "ketamine", "ketamine"),
    ("salvia", "salvia", "salvia"),
    ("ibogaine", "ibogaine", "ibogaine"),
    ("candy-flip", "combos/candy-flip", "candy-flip"),
    ("hippy-flip", "combos/hippy-flip", "hippy-flip"),
    ("tolerance/psilocybin", "tolerance/psilocybin", "psilocybin-tolerance"),
    ("tolerance/lsd", "tolerance/lsd", "lsd-tolerance"),
    ("tolerance/ketamine", "tolerance/ketamine", "ketamine-tolerance"),
    ("afterglow", "afterglow", "afterglow"),
    ("router", "router", "altered-states-router"),
)

PLATFORM_TABLE = (
    "Platform default destinations\n"
    "    darwin    ~/.claude/skills\n"
    "    linux     ~/.config/opencode/skills\n"
    "    other     none -- pass --dest explicitly\n"
)


def planned_installs(
    root: Path, names: list[str] | None
) -> tuple[list[tuple[str, Path, Path]], list[str]]:
    """Resolve (cli-name, source, destination) triples, or list failures."""
    if names is None:
        selected: list[tuple[str, str, str]] = list(DEFAULT_INSTALLS)
    else:
        by_name = {name: entry for name, entry, _ in DEFAULT_INSTALLS}
        missing = [n for n in names if n not in by_name]
        if missing:
            return [], missing
        selected = [entry for entry in DEFAULT_INSTALLS if entry[0] in set(names)]

    resolved: list[tuple[str, Path, Path]] = []
    missing_dirs: list[str] = []
    for name, rel_src, dest in selected:
        source = root / rel_src
        if not (source / "SKILL.md").is_file():
            missing_dirs.append(f"{name} ({source})")
            continue
        resolved.append((name, source, Path(dest)))
    return resolved, missing_dirs


def do_install(
    plan: list[tuple[str, Path, Path]], dest_root: Path, symlink: bool
) -> tuple[list[str], list[str]]:
    """Execute the plan; returns (action lines, problems). Dest is created."""
    lines: list[str] = []
    problems: list[str] = []
    dest_root.mkdir(parents=True, exist_ok=True)
    for name, source, dest in plan:
        target = dest_root / dest
        rel = target.relative_to(dest_root)
        try:
            if target.is_symlink() or target.exists():
                if target.is_symlink():
                    target.unlink()
                else:
                    shutil.rmtree(target)
                lines.append(f"  replaced existing {rel}")
            if symlink:
                target.symlink_to(source, target_is_directory=True)
            else:
                shutil.copytree(source, target, symlinks=False)
            lines.append(f"  {name} -> {rel}")
        except OSError as exc:  # pragma: no cover - only on real FS errors
            problems.append(f"{rel}: {exc}")
    return lines, problems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("One command that installs every Altered States skill "
                     "into the platform-dest skills directory; dry run by default."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=PLATFORM_TABLE,
    )
    parser.description = PLATFORM_TABLE + (
        "Mode (default: dry run -- nothing is written until you opt in):\n"
        "    (no flag)          print the per-skill source -> destination plan, exit 0\n"
        "    --apply            perform the copy (or symlink) into the resolved target\n"
        "    --link             with --apply: symlink the dirs instead of copying them\n"
        "\n"
        "Scope and destination:\n"
        "    --skill NAME       install only the named skill(s); repeatable.\n"
        "                       Names: the 11 substances, router, candy-flip,\n"
        "                       hippy-flip, tolerance/<sub>, afterglow\n"
        "    --dest PATH        destination skills root (overrides the platform table)\n"
        "    --list             print the default install set and exit\n"
        "\n"
        "The router installs under the name altered-states-router so its alias\n"
        "can never collide with a substance skill directory."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually install (default is a dry run that writes nothing)",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="with --apply: symlink each skill dir instead of copying it",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="destination skills root; overrides the platform default",
    )
    parser.add_argument(
        "--skill",
        action="append",
        metavar="NAME",
        help="install only this skill (repeatable); see --list for names",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the default install set and exit without installing",
    )
    args = parser.parse_args(argv)

    if args.list:
        print_default_set()
        print(PLATFORM_TABLE, end="")
        return 0

    plan, missing = planned_installs(SKILLS_DIR, args.skill)
    if missing:
        report_missing(missing)
        return 1

    dest = resolve_dest(args.dest)
    print_plan(plan, dest)

    if not args.apply:
        print(
            "Dry run complete -- nothing was written. Re-run with --apply "
            "(add --link for symlinks; --dest PATH to redirect)."
        )
        return 0

    return do_apply(plan, dest, symlink=args.link)


def print_default_set() -> None:
    print("Default install set (name -> skills-relative source -> dest name):")
    for name, rel_src, dest in DEFAULT_INSTALLS:
        print(f"  {name}: skills/{rel_src} -> {dest}")


def report_missing(missing: list[str]) -> None:
    for name in missing:
        print(f"error: unknown or missing skill: {name}", file=sys.stderr)
    print("Run --list to see the available skill names.", file=sys.stderr)


def resolve_dest(dest: Path | None) -> Path:
    """The destination root: --dest wins, else the platform table."""
    if dest is not None:
        return dest
    resolved = platform_default(sys.platform, Path.home())
    if resolved is not None:
        return resolved
    print(
        "error: no platform default for this OS; pass --dest explicitly",
        file=sys.stderr,
    )
    raise SystemExit(2)


def print_plan(plan: list[tuple[str, Path, Path]], dest: Path) -> None:
    print(f"Skills source: {SKILLS_DIR}")
    print(f"Resolved destination: {dest}")
    print()
    for name, source, dest_name in plan:
        print(f"  {name}: {source} -> {dest / dest_name}")
    print()


def do_apply(
    plan: list[tuple[str, Path, Path]], dest: Path, symlink: bool
) -> int:
    if dest.resolve() == SKILLS_DIR.resolve():
        print("error: refusing to install the skills tree into itself", file=sys.stderr)
        return 2
    lines, problems = do_install(plan, dest, symlink=symlink)
    for line in lines:
        print(line)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    print()
    print(f"Installed {len(lines)} skill dir(s) into {dest}.")
    return 0


def platform_default(sysname: str, home: Path) -> Path | None:
    """The one function that maps an OS to a skills home. See PLATFORM_TABLE."""
    if sysname.startswith("darwin"):
        return home / ".claude" / "skills"
    if sysname.startswith("linux"):
        return home / ".config" / "opencode" / "skills"
    return None


if __name__ == "__main__":
    raise SystemExit(main())

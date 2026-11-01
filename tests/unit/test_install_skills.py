"""Offline unit tests for bin/install_skills.py.

Everything runs against a tmp --dest: the default dry run must write
nothing, --apply --dest copies the full skill set (including router,
2c-b, combos, tolerance, afterglow), --link symlinks resolve, and an
unknown --skill exits nonzero naming the missing skill.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALL = REPO / "bin" / "install_skills.py"
SKILLS = REPO / "skills"


def run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALL), *argv],
        capture_output=True,
        text=True,
        check=False,
    )


# --- dry run is the default ---------------------------------------------------


def test_bare_invocation_is_plan_only(tmp_path: Path) -> None:
    result = run_cli("--dest", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    # plan names source -> resolved target per skill
    assert "psilocybin" in result.stdout
    assert "--dest" in result.stdout or str(tmp_path) in result.stdout
    assert "Dry run complete" in result.stdout
    assert "nothing was written" in result.stdout
    # nothing was created
    assert list(tmp_path.iterdir()) == []


def test_plan_prints_resolved_target_per_skill(tmp_path: Path) -> None:
    result = run_cli("--dest", str(tmp_path), "--skill", "2c-b")
    assert result.returncode == 0
    assert f"{SKILLS / '2c-b'} -> {tmp_path / '2c-b'}" in result.stdout


def test_help_contains_platform_table() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "darwin" in result.stdout and "~/.claude/skills" in result.stdout
    assert "linux" in result.stdout and "~/.config/opencode/skills" in result.stdout
    for flag in ("--apply", "--link", "--dest", "--skill", "--list"):
        assert flag in result.stdout, f"--help missing {flag}"


def test_list_prints_default_set() -> None:
    result = run_cli("--list")
    assert result.returncode == 0
    for name in ("2c-b", "router", "candy-flip", "tolerance/ketamine", "afterglow"):
        assert name in result.stdout, f"--list missing {name}"


# --- --apply copy mode ---------------------------------------------------------


def test_apply_copy_installs_full_skill_set(tmp_path: Path) -> None:
    result = run_cli("--apply", "--dest", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    expected = [
        "psilocybin",
        "2c-b",
        "altered-states-router",
        "candy-flip",
        "hippy-flip",
        "psilocybin-tolerance",
        "lsd-tolerance",
        "ketamine-tolerance",
        "afterglow",
    ]
    for name in expected:
        assert (tmp_path / name / "SKILL.md").is_file(), name
    # byte-equal copy
    src = SKILLS / "psilocybin" / "SKILL.md"
    assert (tmp_path / "psilocybin" / "SKILL.md").read_bytes() == src.read_bytes()


def test_apply_reinstall_replaces_without_doubling(tmp_path: Path) -> None:
    assert run_cli("--apply", "--dest", str(tmp_path)).returncode == 0
    first = (tmp_path / "2c-b" / "SKILL.md").read_text()
    result = run_cli("--apply", "--dest", str(tmp_path), "--skill", "2c-b")
    assert result.returncode == 0
    assert "replaced existing" in result.stdout
    assert (tmp_path / "2c-b" / "SKILL.md").read_text() == first
    assert not (tmp_path / "2c-b" / "SKILL.md" / "SKILL.md").exists()


# --- --apply --link symlink mode -----------------------------------------------


def test_apply_link_symlinks_resolve(tmp_path: Path) -> None:
    result = run_cli("--apply", "--link", "--dest", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    link = tmp_path / "lsd"
    assert link.is_symlink()
    assert link.resolve() == (SKILLS / "lsd").resolve()
    assert (link / "SKILL.md").is_file()


# --- failure paths --------------------------------------------------------------


def test_unknown_skill_exits_nonzero_naming_it(tmp_path: Path) -> None:
    result = run_cli("--apply", "--dest", str(tmp_path), "--skill", "bogus-substance")
    assert result.returncode == 1
    assert "bogus-substance" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_apply_refuses_dest_equal_to_skills_tree() -> None:
    result = run_cli("--apply", "--dest", str(SKILLS))
    assert result.returncode == 2
    assert "skills tree" in result.stderr


def test_apply_refuses_dest_inside_skills_tree(tmp_path: Path) -> None:
    # Not an exact match: a directory strictly inside skills/ would let the
    # installer rmtree-replace same-named targets under the real source tree.
    inside = SKILLS / "combos" / "nested-dest"
    result = run_cli("--apply", "--dest", str(inside))
    assert result.returncode == 2
    assert "inside skills/" in result.stderr
    assert not inside.exists()

"""Offline unit tests for bin/check_skills.py (the skill-structure validator).

Covers the clean-tree pass, nested-layout discovery (combos/tolerance), the
seeded-mutation failure paths (each must exit nonzero naming file + section),
and the --new-skill authoring-checklist mode. All runs use stdlib subprocesses
and tmp copies of the real skills/ tree — no tree is ever mutated in place.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECK = REPO / "bin" / "check_skills.py"
SKILLS = REPO / "skills"


def run_validator(skills_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), "--skills-dir", str(skills_dir)],
        capture_output=True,
        text=True,
        check=False,
    )


def run_cli(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECK), *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def copied_skills(tmp_path: Path) -> Path:
    target = tmp_path / "skills"
    shutil.copytree(SKILLS, target)
    return target


def count_skill_files(root: Path) -> int:
    return len(list(root.rglob("SKILL.md")))


# --- clean tree ---------------------------------------------------------------


def test_clean_tree_passes_with_all_skill_files() -> None:
    result = run_validator(SKILLS)
    assert result.returncode == 0, result.stdout + result.stderr
    total = count_skill_files(SKILLS)
    # per-skill OK lines, including version, one per discovered file
    ok_lines = [line for line in result.stdout.splitlines() if ": OK" in line]
    assert len(ok_lines) == total
    assert total >= 18  # 13 top-level (incl. router + afterglow) + 2 combos + 3 tolerance


def test_nested_overlay_layouts_are_discovered() -> None:
    """skills/combos/*/SKILL.md and skills/tolerance/*/SKILL.md are validated
    as full skills even though no SKILL.md sits directly in the line dir."""
    result = run_validator(SKILLS)
    assert result.returncode == 0, result.stdout
    for name in (
        "combos/candy-flip/SKILL.md",
        "combos/hippy-flip/SKILL.md",
        "tolerance/psilocybin/SKILL.md",
        "tolerance/lsd/SKILL.md",
        "tolerance/ketamine/SKILL.md",
        "afterglow/SKILL.md",
    ):
        matched = [line for line in result.stdout.splitlines() if name in line and ": OK" in line]
        assert matched, f"{name} not validated as a skill: {result.stdout}"


def test_tolerance_readme_is_a_policy_doc_not_a_skill() -> None:
    """Discovery is rglob('SKILL.md')-only, so skills/tolerance/README.md is
    neither validated nor flagged — and it genuinely exists as a line-policy
    doc (this is not a vacuous absence check)."""
    assert (SKILLS / "tolerance" / "README.md").is_file()
    result = run_validator(SKILLS)
    assert result.returncode == 0
    assert "tolerance/README.md" not in result.stdout


def test_combo_skills_routable_by_router_aliases() -> None:
    """candy-flip-altered-state / hippy-flip-altered-state resolve via the
    nested combo dirs — the seeded-alias mutation proves resolution is real."""
    result = run_validator(SKILLS)
    assert result.returncode == 0
    assert "candy-flip-altered-state" not in result.stdout  # no unresolved-alias failures


# --- mutation helpers (all operate on a tmp copy of the tree) ------------------

MUTATIONS = [
    # (description, mutator, expected fragments in failure output)
    (
        "safety override removed",
        lambda p: _delete_section(p, "2c-b/SKILL.md", "Safety Override"),
        ["2c-b/SKILL.md", "Safety Override"],
    ),
    (
        "front-matter key removed",
        lambda p: _delete_line(p, "lsd/SKILL.md", 'version: "1.5"'),
        ["lsd/SKILL.md", "front matter"],
    ),
    (
        "dimension table row removed",
        lambda p: _delete_row(p, "mescaline/SKILL.md"),
        ["mescaline/SKILL.md"],
    ),
    (
        "dose arc removed",
        lambda p: _delete_section(p, "ayahuasca/SKILL.md", "Dose Arc"),
        ["ayahuasca/SKILL.md", "Dose Arc"],
    ),
    (
        "router alias renamed to a nonexistent skill",
        lambda p: _replace_line(p, "router/SKILL.md", "candy-flip-altered-state", "ghost-alias-altered-state"),
        ["router/SKILL.md", "ghost-alias-altered-state"],
    ),
    (
        "dose figure planted in a combo overlay",
        lambda p: _replace_line(p, "combos/hippy-flip/SKILL.md", "The Interaction", "take 120 mg of warmth"),
        ["combos/hippy-flip/SKILL.md"],
    ),
]

MUTATION_IDS = [m[0] for m in MUTATIONS]


def _delete_section(tree: Path, rel: str, heading_word: str) -> None:
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, skipping = [], False
    for line in lines:
        if line.startswith("## ") and heading_word in line:
            skipping = True
            continue
        if skipping and line.startswith("## "):
            skipping = False
        if not skipping:
            out.append(line)
    path.write_text("".join(out), encoding="utf-8")


def _delete_line(tree: Path, rel: str, needle: str) -> None:
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(x for x in lines if needle not in x), encoding="utf-8")


def _replace_line(tree: Path, rel: str, needle: str, replacement: str) -> None:
    path = tree / rel
    text = path.read_text(encoding="utf-8")
    assert needle in text, f"fixture drift: {needle!r} not in {rel}"
    path.write_text(text.replace(needle, replacement), encoding="utf-8")


def _delete_row(tree: Path, rel: str) -> None:
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, dropped = [], False
    for line in lines:
        if line.startswith("| 7 |"):
            dropped = True
            continue
        out.append(line)
    assert dropped, f"fixture drift: no '| 7 |' row in {rel}"
    path.write_text("".join(out), encoding="utf-8")


# --- dimension-table column integrity (VAL-TOOL-001) ---------------------------


def _delete_dimension_column(tree: Path, rel: str) -> None:
    """Delete the last column of the dimension table (header AND data rows)."""
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, table_cells, dropped = [], [], 0
    for line in lines:
        if line.strip().startswith("|"):
            stripped = line.rstrip("\n").strip().strip("|")
            cells = [c.strip() for c in stripped.split("|")]
            if cells[0] != "---" and len(cells) > 2:
                dropped += 1
                new_cells = cells[:-1]
                table_cells.append(len(new_cells))
                line = "| " + " | ".join(new_cells) + " |\n"  # noqa: PLW2901
        out.append(line)
    assert dropped, f"fixture drift: no dimension table found in {rel}"
    # both header and every data row lost exactly one cell
    assert len(set(table_cells)) == 1, table_cells
    path.write_text("".join(out), encoding="utf-8")


def _delete_dimension_header_cells(tree: Path, rel: str) -> None:
    """Delete intensity header cells only: header row shrinks, data rows keep
    their full cell count."""
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, header_seen = [], False
    for line in lines:
        if not header_seen and line.strip().startswith("| #"):
            line = "| # | Dimension |\n"  # noqa: PLW2901
            header_seen = True
        out.append(line)
    assert header_seen, f"fixture drift: no '| #' header row in {rel}"
    path.write_text("".join(out), encoding="utf-8")


_DIM_MUTATORS = [_delete_dimension_column, _delete_dimension_header_cells]


@pytest.mark.parametrize("mutator", _DIM_MUTATORS, ids=["full-column-deletion", "header-cell-only"])
def test_seeded_dimension_column_deletion_fails(tmp_path: Path, mutator: Callable[..., None]) -> None:
    """Deleting an intensity/dimension table COLUMN — fully (header + rows) or
    just the header cells — must exit nonzero citing file + dimensions section."""
    tree = copied_skills(tmp_path)
    mutator(tree, "mescaline/SKILL.md")
    result = run_validator(tree)
    assert result.returncode != 0, f"validator passed with a column deleted:\n{result.stdout}"
    assert "mescaline/SKILL.md" in result.stdout
    assert "dimension" in result.stdout.lower()


# --- seeded mutations (failure paths must fire) --------------------------------


@pytest.mark.parametrize("mutation", MUTATIONS, ids=MUTATION_IDS, indirect=False)
def test_seeded_mutation_fails_named_and_sectioned(
    tmp_path: Path, mutation: tuple[str, Callable[[Path], None], list[str]]
) -> None:
    _, mutator, expected_fragments = mutation
    tree = copied_skills(tmp_path)
    mutator(tree)
    result = run_validator(tree)
    assert result.returncode != 0, f"validator passed with the mutation planted:\n{result.stdout}"
    for fragment in expected_fragments:
        assert fragment in result.stdout, f"failure output does not cite {fragment!r}:\n{result.stdout}"


def test_seeded_dimension_row_fails_reporting_row(tmp_path: Path) -> None:
    tree = copied_skills(tmp_path)
    _delete_row(tree, "mescaline/SKILL.md")
    result = run_validator(tree)
    assert result.returncode != 0
    # cites file AND the failing section
    assert "mescaline/SKILL.md" in result.stdout
    assert "dimension" in result.stdout.lower()


# --- expected-scale registry (VAL-TOOL-001 run-3 gap: consistent whole-column
# deletions are size-coherent and slip past the width checks; the header labels
# are the only witness) -------------------------------------------------------


def _delete_labeled_column(tree: Path, rel: str, label: str) -> None:
    """Delete the dimension-table column whose header label matches
    `label` — from the header row, separator, AND every data row — so the
    resulting table is internally consistent (header count == row count)."""
    path = tree / rel
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out, in_table, idx, dropped = [], False, None, 0
    for line in lines:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.rstrip("\n").strip().strip("|").split("|")]
            if not in_table:
                if len(cells) > 2 and label in (c.lower() for c in cells):
                    in_table = True
                    idx = next(i for i, c in enumerate(cells) if c.lower() == label)
                    dropped += 1
                    line = "| " + " | ".join(cells[:idx] + cells[idx + 1 :]) + " |\n"  # noqa: PLW2901
            elif len(cells) > 1:
                assert idx is not None
                dropped += 1
                line = "| " + " | ".join(cells[:idx] + cells[idx + 1 :]) + " |\n"  # noqa: PLW2901
        else:
            in_table = False
            idx = None
        out.append(line)
    assert dropped >= 8, f"fixture drift: column {label!r} lost from only {dropped} table lines in {rel}"
    path.write_text("".join(out), encoding="utf-8")


def _rename_column(tree: Path, rel: str, label: str, new_label: str) -> None:
    _replace_line(tree, rel, label, new_label)


def test_scale_registry_catches_consistent_medium_column_deletion(tmp_path: Path) -> None:
    """The VAL-TOOL-001 run-3 repro: delete the Medium column from header,
    separator AND all 7 data rows of a 2c-b fixture copy. The table is
    coherent by size — only the registered labels catch it."""
    tree = copied_skills(tmp_path)
    _delete_labeled_column(tree, "2c-b/SKILL.md", "medium")
    result = run_validator(tree)
    assert result.returncode != 0, f"validator passed with Medium deleted:\n{result.stdout}"
    assert "2c-b/SKILL.md" in result.stdout
    assert "dimension" in result.stdout.lower()
    assert "fix:" in result.stdout


def test_scale_registry_catches_overlay_column_deletion(tmp_path: Path) -> None:
    """Overlay-line tables are registered too: deleting the afterglow
    Hours 24-48 column consistently must exit nonzero."""
    tree = copied_skills(tmp_path)
    _delete_labeled_column(tree, "afterglow/SKILL.md", "hours 24-48")
    result = run_validator(tree)
    assert result.returncode != 0, f"validator passed with a horizon column deleted:\n{result.stdout}"
    assert "afterglow/SKILL.md" in result.stdout
    assert "dimension" in result.stdout.lower()


def test_scale_registry_catches_inconsistent_column_rename(tmp_path: Path) -> None:
    """Renaming a registered scale label is an unexpected column AND a
    missing one at once."""
    tree = copied_skills(tmp_path)
    _rename_column(tree, "tolerance/lsd/SKILL.md", "Day-two shift", "Week-two shift")
    result = run_validator(tree)
    assert result.returncode != 0, f"validator passed with a renamed scale column:\n{result.stdout}"
    assert "tolerance/lsd/SKILL.md" in result.stdout
    assert "unexpected" in result.stdout.lower()


def test_scale_registry_covers_every_table_carrying_skill_file() -> None:
    """Every live skill file whose dimension section is a table must have a
    registry entry, so no future table deletes columns unregistered."""
    from importlib import util as _util

    spec = _util.spec_from_file_location("check_skills_mod", CHECK)
    assert spec and spec.loader
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    registry: set[str] = set(mod.EXPECTED_TABLE_SCALES)
    for path in SKILLS.rglob("SKILL.md"):
        text = path.read_text(encoding="utf-8")
        dim_sections = [ln for ln in text.splitlines() if "Phenomenological Dimensions" in ln and ln.startswith("#")]
        if not dim_sections:
            continue
        rel = path.relative_to(SKILLS.parent)
        assert f"{rel}" in registry, f"{rel} has a dimension table but no EXPECTED_TABLE_SCALES entry"
    assert registry >= {"skills/afterglow/SKILL.md", "skills/tolerance/ketamine/SKILL.md"}


def test_scale_registry_live_labels_match_actual_files() -> None:
    """No false positives: each registry entry's labels (lowercased) appear
    verbatim in the live file's dimension-table header."""
    from importlib import util as _util

    spec = _util.spec_from_file_location("check_skills_mod", CHECK)
    assert spec and spec.loader
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for rel, labels in mod.EXPECTED_TABLE_SCALES.items():
        text = (SKILLS / Path(rel).relative_to("skills")).read_text(encoding="utf-8")
        for label in labels:
            assert label in text.lower(), f"{rel}: registry label {label!r} not in live file"


# --- authoring-guide mode ------------------------------------------------------


def test_new_skill_mode_prints_authoring_checklist() -> None:
    result = run_cli("--new-skill", "skills/example/SKILL.md")
    assert result.returncode == 0
    for token in ("Safety Override", "tags:", "version:", "Dose Arc", "altered-states"):
        assert token in result.stdout


def test_validator_is_stdlib_only() -> None:
    source = CHECK.read_text(encoding="utf-8")
    banned = ["import requests", "import yaml", "import http", "urllib", "socket", "subprocess"]
    for token in banned:
        assert token not in source, f"validator must be stdlib-offline; found {token!r}"

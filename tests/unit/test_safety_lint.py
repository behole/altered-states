"""Tests for bin/safety_lint.py — content-safety lint (VAL-TOOL-003/004).

Offline, tmp-dir-based. Proves the three contract surfaces:

* clean pass over the REAL skills tree (all 16 dirs) and the built site,
* seeded forbidden patterns fail with file:line named,
* the allowlist mechanism is scoped: it suppresses exactly what it claims
  and can NOT defeat a dose-verb hit (a line carrying a forbidden pattern
  plus a dose number fails regardless of any allow comment).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LINT = REPO / "bin" / "safety_lint.py"

import safety_lint  # noqa: E402  (bin is on sys.path via conftest or sys.path insert)


def run_lint(*cli_args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(LINT), *cli_args],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )
    return proc.returncode, proc.stdout + proc.stderr


# --- clean-tree pass ---------------------------------------------------------


def test_clean_tree_full_skills_and_built_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero findings over every real skill md + the built site/index.html."""
    skills = REPO / "skills"
    site = REPO / "site" / "index.html"
    assert site.exists(), "built site must exist for the site scan to be real"
    code, out = run_lint("--skills-dir", str(skills), "--site", str(site))
    assert code == 0, out
    assert "clean" in out


def test_clean_tree_has_all_expected_skill_md_files() -> None:
    md_files = sorted((REPO / "skills").rglob("*.md"))
    skill_dir_count = len([d for d in (REPO / "skills").iterdir() if d.is_dir()])
    # 11 base substances + router + afterglow + 2 combos + tolerance overlays
    # + consistency matrix + tolerance README — never empty.
    assert len(md_files) >= 16
    assert skill_dir_count == 15  # 11 substances + router + afterglow + combos + tolerance


# --- seeded violations fail with file:line -----------------------------------


def _write(dirpath: Path, rel: str, text: str) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    target = dirpath / "skills" / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_seeded_dose_verb_fails_naming_file_and_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Fine wonders.\nTake 120 mg and notice the texture change.\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[dose-verb]" in out
    assert "seed/SKILL.md:2" in out


def test_seeded_schedule_fails(tmp_path: Path) -> None:
    _write(tmp_path, "seed/SKILL.md", "Ok.\ncome back every 3 days.\n")
    _write(tmp_path, "seed/other/SKILL.md", "Ok.\nwait 48 hours before again.\n")
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[schedule]" in out
    assert "every 3 days" in out
    assert "wait 48 hours" in out


def test_seeded_therapy_claim_fails(tmp_path: Path) -> None:
    _write(tmp_path, "seed/SKILL.md", "Ok.\nMDMA is used to treat depression.\n")
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[therapy]" in out


def test_seeded_sourcing_language_fails(tmp_path: Path) -> None:
    _write(tmp_path, "seed/SKILL.md", "Ok.\ntell me where to buy it.\n")
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[sourcing]" in out


def test_seeded_forbidden_word_fails(tmp_path: Path) -> None:
    _write(tmp_path, "seed/SKILL.md", "Ok.\nfollow the re-dose schedule.\n")
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[forbidden-word]" in out
    assert "re-dose schedule" in out or "schedule" in out


def test_site_scan_catches_forbidden_text_in_built_output(tmp_path: Path) -> None:
    site = tmp_path / "index.html"
    site.write_text("<h1>ok</h1>\ntake 40 mg of the quiet\n", encoding="utf-8")
    code, out = run_lint("--no-site")  # control: real tree stays clean
    assert code == 0, out
    # site scan itself:
    code, out = run_lint("--skills-dir", str(REPO / "skills"), "--site", str(site))
    assert code == 1
    assert "index.html:2" in out
    assert "[dose-verb]" in out


def test_template_not_scanned_by_default(tmp_path: Path) -> None:
    """The lint targets built output; the template is never scanned."""
    # no seeded finding inside the template should matter: this test only
    # asserts the template file is outside the scanned set by construction.
    template = REPO / "site" / "index.template.html"
    scan_paths = safety_lint.collect_skills_findings(REPO / "skills")
    template_findings = [f for f in scan_paths if str(template) in str(f.path)]
    assert template_findings == []


# --- refusal-context allowance (overlays) -------------------------------------


def test_refusal_sentences_pass(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Ok.\n"
        "**No schedule, and no recovery arithmetic.**\n"
        "carried here as description of restlessness, never as a schedule\n"
        "stillness — never as a regimen.\n"
        "Descriptive — never a regimen, never treatment.\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 0, out


def test_refusal_allowance_does_not_mask_consecutive_lines(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Ok.\n"
        "never as a schedule (this line is fine)\n"
        "the schedule of arcs recurs on a stated calendar until the peaks align\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert out.count("seed/SKILL.md") == 1


def test_real_overlay_refusal_lines_are_clean() -> None:
    """Orchestrator note: zero findings on the overlays incl. their refusal lines."""
    targets = [
        REPO / "skills" / "afterglow" / "SKILL.md",
        REPO / "skills" / "afterglow" / "consistency-matrix.md",
        REPO / "skills" / "combos" / "candy-flip" / "SKILL.md",
        REPO / "skills" / "combos" / "hippy-flip" / "SKILL.md",
    ]
    for t in targets:
        findings = safety_lint.iter_finding_lines(t, t.read_text(encoding="utf-8"))
        assert findings == [], f"{t}: {findings}"


def test_real_base_skill_allowlist_contexts_are_clean() -> None:
    """'Ineffability protocol' (psilocybin) and 'clinical protocol' (ketamine) allowed."""
    for rel, expected_count in (("psilocybin", 1), ("ketamine", 2)):
        path = REPO / "skills" / rel / "SKILL.md"
        findings = safety_lint.iter_finding_lines(path, path.read_text(encoding="utf-8"))
        assert findings == [], f"{path}: {findings}"
        hits = sum(
            len(safety_lint._FORBIDDEN_WORD_RE.findall(body_line))
            for body_line in path.read_text(encoding="utf-8").splitlines()
        )
        assert hits == expected_count, f"{rel}: {hits} forbidden-word strings"


# --- inline allow: scoped suppression + defeat guard --------------------------


def test_inline_allow_suppresses_declared_rule_for_following_line(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Ok.\n"
        "<!-- safety-lint: allow: forbidden-word -- reason: quoted historical "
        "phrase from the literature -->\n"
        "quoted protocol in context of the source text\n"
        "schedule repeated after the third line is outside the scope\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    # exactly one finding: the line after the comment's scope boundary
    assert out.count("seed/SKILL.md") == 1
    assert "outside the scope" in out


def test_inline_allow_without_reason_suppresses_nothing(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Ok.\n"
        "<!-- safety-lint: allow: forbidden-word -->\n"  # no -- reason
        "protocol still reported\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "protocol still reported" in out


def test_defeat_guard_dose_verb_not_suppressible(tmp_path: Path) -> None:
    """The full-line forbidden+number match fails regardless of allow comment."""
    _write(
        tmp_path,
        "seed/SKILL.md",
        "Ok.\n"
        "<!-- safety-lint: allow: dose-verb,forbidden-word,schedule -- reason: "
        "attempting to defeat the guard should be impossible -->\n"
        "Take 120 mg and see what happens next.\n"
        "wait 3 days, schedule re-dose: take 60 mg\n",
    )
    code, out = run_lint("--skills-dir", str(tmp_path / "skills"), "--no-site")
    assert code == 1
    assert "[dose-verb]" in out
    # both dose lines reported despite the allow comment naming the rules
    assert out.count("[dose-verb]") == 2


# --- missing built site is a usage error, not a silent pass --------------------


def test_missing_built_site_reports_warning_and_exit_2(tmp_path: Path) -> None:
    _write(tmp_path, "seed/SKILL.md", "clean text only\n")
    code, out = run_lint(
        "--skills-dir",
        str(tmp_path / "skills"),
        "--site",
        str(tmp_path / "does-not-exist.html"),
    )
    assert code == 2
    assert "make build" in out

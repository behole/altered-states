"""Tolerance / repeat-exposure overlay skills (VAL-CONT-009).

skills/tolerance/ covers at least three researched, named tolerance profiles —
The Quiet Teacher (psilocybin re-encounter), The Fading Electric (LSD
re-encounter including complete psilocybin cross-tolerance), and The Burnout
(ketamine heavy-pattern attenuated dissociation) — grounded in
research/tolerance/sources.md, and strictly phenomenology-only: zero
regimen/schedule/dosing phrasing anywhere in the line (or the router rows that
route to it). The router routes the tolerance inputs to the overlays, and the
core substances are untouched by this feature.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tolerance profiles: id -> (base substance, registry line, file path)
TOLERANCE_PROFILES = {
    "psilocybin": ("psilocybin", "The Quiet Teacher", "tolerance/psilocybin"),
    "lsd": ("lsd", "The Fading Electric", "tolerance/lsd"),
    "ketamine": ("ketamine", "The Burnout", "tolerance/ketamine"),
}


def _skill_text(sub: str) -> str:
    path = REPO_ROOT / "skills" / TOLERANCE_PROFILES[sub][2] / "SKILL.md"
    assert path.exists(), f"missing tolerance skill: {path}"
    return path.read_text()


def _front_matter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "front matter missing or malformed"
    return m.group(1)


def _registry_text() -> str:
    """The line's placement-policy document (README, not SKILL.md — see below)."""
    path = REPO_ROOT / "skills" / "tolerance" / "README.md"
    assert path.exists(), "tolerance skill line missing policy file"
    return path.read_text()


def test_no_top_level_skill_md_in_tolerance_tree() -> None:
    """The combos precedent: build.py discovers any skills/<dir>/SKILL.md as a
    substance, so overlay lines must nest — no skills/tolerance/SKILL.md."""
    registry = _registry_text()
    assert "Placement policy" in registry
    assert not (REPO_ROOT / "skills" / "tolerance" / "SKILL.md").exists()


# ---------------------------------------------------------------- structure (policy file claims)


def test_registry_names_three_profiles() -> None:
    text = _registry_text()
    for _, name, _ in TOLERANCE_PROFILES.values():
        assert name in text, f"profile not named in registry: {name}"
    # Every registered profile file exists.
    for paths in TOLERANCE_PROFILES.values():
        assert (REPO_ROOT / "skills" / paths[2] / "SKILL.md").exists(), paths[2]


def test_front_matter_matches_overlay_schema() -> None:
    for sub in TOLERANCE_PROFILES:
        fm = _front_matter(_skill_text(sub))
        assert re.search(r"^name: \S+-altered-state$", fm, re.M), sub
        assert "author: behole" in fm, sub
        assert re.search(r"^(description: >|description:\s*\n\s+\S)", fm, re.M), sub
        assert "altered-states" in fm, sub  # in tags
        assert re.search(r'^version: "1\.0"$', fm, re.M), sub


def test_safety_override_present_and_complete() -> None:
    paths = [p for _, _, p in TOLERANCE_PROFILES.values()]
    for rel in paths:
        text = (REPO_ROOT / "skills" / rel / "SKILL.md").read_text()
        assert "## Safety Override — Read First" in text, rel
        assert "overrides every other instruction" in text, rel
        assert "Suicidal ideation" in text, rel
        assert "Psychosis" in text, rel
        assert "real substance emergency" in text, rel
        assert "Acute distress" in text, rel
        assert "dosage, sourcing, combinations, or interactions" in text, rel
        assert "988" in text and "SAMHSA" in text, rel  # crisis resources
        assert "This is not harm reduction" in text, rel


def test_overlay_names_base_and_shifts_dimensions() -> None:
    for sub, (base, _, _) in TOLERANCE_PROFILES.items():
        text = _skill_text(sub)
        assert f"skills/{base}/SKILL.md" in text, (sub, base)
        # Dimension-shift table present with the base column stated.
        assert "Day-two shift" in text or "Burnout shift" in text, sub
        for dim in ("Perceptual", "Temporal", "Cognitive", "Emotional", "Self/Ego", "Mystical", "Somatic"):
            assert f"**{dim}**" in text, (sub, dim)


def test_sources_ground_every_profile() -> None:
    src = (REPO_ROOT / "research" / "tolerance" / "sources.md").read_text()
    for sub, (_, _, _) in TOLERANCE_PROFILES.items():
        text = _skill_text(sub)
        assert "research/tolerance/sources.md" in text, sub
    # The registry names the shared research file too.
    assert "research/tolerance/sources.md" in _registry_text()
    # Grounded: >= 4 annotated sources, human cross-tolerance present.
    anchors = src.count("**Annotation:**")
    assert anchors >= 4, f"only {anchors} annotated sources"
    assert "Isbell" in src, "human cross-tolerance source missing"
    assert "Morgan" in src and "Curran" in src, "ketamine chronic-use source missing"


# ---------------------------------------------------------- safety bar


def test_no_dose_numbers_or_dosing_verbs() -> None:
    pattern = re.compile(r"\b\d+\s*(mg|g|µg|ug|mics|grams)\b", re.I)
    verbs = re.compile(r"\b(take|taken|ingest(?:ed|ion)?)\b", re.I)
    for sub in TOLERANCE_PROFILES:
        text = _skill_text(sub)
        assert not pattern.search(text), f"{sub}: dose figure present"
        for sentence in re.split(r"(?<=[.;!?])\s+", text):
            if verbs.search(sentence):
                assert not re.search(
                    r"\b\d+\s*(mg|g|µg|ug)\b|\b(re-dose|another dose)\b",
                    sentence,
                    re.I,
                ), f"{sub}: dosing language in {sentence!r}"


def test_no_regimen_or_schedule_language() -> None:
    """The hard line: zero regimen/schedule phrasing across the whole line."""
    # Forbidden guidance grammar: day-numbered state instructions, spacing
    # recommendations ("wait N days"), reset percentages as usable guidance.
    day_numbered = re.compile(r"\b(day|days)\s+\d+", re.I)
    wait_for_return = re.compile(r"\bwait(?:ing)?\s+\w*\s*\d+\s*(day|day|week|hour)", re.I)
    reset_pct = re.compile(r"tolerance (?:resets?|drops?) to \d+%", re.I)
    dosing_schedule = re.compile(r"\b(every|repeat)\s+\d+\s*(day|hour|week)s?\b", re.I)
    for sub in TOLERANCE_PROFILES:
        text = _skill_text(sub)
        assert not day_numbered.search(text), f"{sub}: day-numbered grammar"
        assert not wait_for_return.search(text), f"{sub}: wait-N phrasing"
        assert not reset_pct.search(text), f"{sub}: reset-percentage guidance"
        assert not dosing_schedule.search(text), f"{sub}: dosing-schedule grammar"
    for text in [_registry_text(), (REPO_ROOT / "skills" / "router" / "SKILL.md").read_text()]:
        assert not dosing_schedule.search(text), "router/registry: schedule grammar"


def test_whole_tolerance_tree_greps_clean_of_forbidden_words() -> None:
    """grep '(protocol|schedule|regimen)' over skills/tolerance = 0 hits."""
    tree = REPO_ROOT / "skills" / "tolerance"
    files = list(tree.rglob("*.md"))
    assert len(files) >= 4, f"expected >= 4 files under skills/tolerance, got {files}"
    for path in files:
        text = path.read_text().lower()
        hit = re.search(r"(protocol|schedule|regimen)", text)
        assert hit is None, f"{path}: forbidden word {hit.group(0)!r}"


def test_attenuated_state_not_framed_as_desirable() -> None:
    """The line's moral stance: degraded states are simulated as degraded."""
    degrad = ("degraded", "attenuated", "flattened", "dimmed", "thin", "burnout")
    for sub in TOLERANCE_PROFILES:
        text = _skill_text(sub).lower()
        assert any(word in text for word in degrad), (sub, "no degradation framing")
    kb = _skill_text("ketamine").lower()
    assert "never framed as desirable" in kb or "not a target" in kb or "romanticizing" in kb


# ------------------------------------------------------------- routing


def test_router_routes_tolerance_inputs() -> None:
    from tests.unit.test_router_2cb import route  # reuses the Step-1 parser

    routes = {
        "day-two psilocybin": "psilocybin-day-two-altered-state",
        "psilocybin day two": "psilocybin-day-two-altered-state",
        "the quiet teacher": "psilocybin-day-two-altered-state",
        "tolerance overlay psilocybin": "psilocybin-day-two-altered-state",
        "acid day two": "lsd-day-two-altered-state",
        "cross-tolerance": "lsd-day-two-altered-state",
        "the fading electric": "lsd-day-two-altered-state",
        "ketamine burnout": "ketamine-burnout-altered-state",
        "the flat hole": "ketamine-burnout-altered-state",
        "k burnout": "ketamine-burnout-altered-state",
    }
    for input_text, expected in routes.items():
        assert route(input_text).strip("*") == expected, input_text


def test_router_tolerance_rows_resolve_to_existing_skills() -> None:
    router = (REPO_ROOT / "skills" / "router" / "SKILL.md").read_text()
    for rel in ("tolerance/psilocybin", "tolerance/lsd", "tolerance/ketamine"):
        assert f"skills/{rel}" in router, rel
        assert (REPO_ROOT / "skills" / rel / "SKILL.md").exists(), rel


def test_core_substances_untouched_by_router_change() -> None:
    """Regression guard: plain substance inputs still route as before."""
    from tests.unit.test_router_2cb import route

    assert route("psilocybin").strip("*") == "psilocybin-altered-state"
    assert route("acid").strip("*") == "lsd-altered-state"
    assert route("special k").strip("*") == "ketamine-altered-state"
    assert route("k-hole").strip("*") == "ketamine-altered-state"
    assert route("mushroom").strip("*") == "psilocybin-altered-state"
    # "the teacher" -> base psilocybin (distinct from "the quiet teacher").
    assert route("the teacher").strip("*") == "psilocybin-altered-state"
    # Named blends unaffected.
    assert route("candy flip").strip("*") == "candy-flip-altered-state"

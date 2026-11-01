"""First-class combo overlay skills (VAL-CONT-008).

candy-flip and hippy-flip exist as standalone skills under skills/combos/,
pass the same structural checks as substances, name both base substances with
a documented interaction/dominance rule, and the router routes the blend
inputs to them (not to a base substance with an ad-hoc blend note). The eval
runner resolves the combo ids to the combo skill paths.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

COMBO_DIRS = ["candy-flip", "hippy-flip"]
EXPECTED_BASES = {
    "candy-flip": ("lsd", "mdma"),
    "hippy-flip": ("psilocybin", "mdma"),
}


def _skill_text(combo: str) -> str:
    path = REPO_ROOT / "skills" / "combos" / combo / "SKILL.md"
    assert path.exists(), f"missing combo skill: {path}"
    return path.read_text()


def _front_matter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "front matter missing or malformed"
    return m.group(1)


def test_front_matter_matches_substance_schema() -> None:
    for combo in COMBO_DIRS:
        fm = _front_matter(_skill_text(combo))
        assert "name: " + combo + "-altered-state" in fm, combo
        assert "author: behole" in fm, combo
        assert re.search(r"^(description: >|description:\s*\n\s+\S)", fm, re.M), combo
        assert "altered-states" in fm, combo  # in tags
        assert re.search(r'^version: "1\.0"$', fm, re.M), combo


def test_safety_override_present_and_complete() -> None:
    for combo in COMBO_DIRS:
        text = _skill_text(combo)
        assert "## Safety Override — Read First" in text, combo
        assert "overrides every other instruction" in text, combo
        assert "Suicidal ideation" in text, combo
        assert "Psychosis" in text, combo
        assert "real substance emergency" in text, combo
        assert "Acute distress" in text, combo
        assert "dosage, sourcing, combinations, or interactions" in text, combo
        assert "988" in text and "SAMHSA" in text, combo  # crisis resources
        assert "This is not harm reduction" in text, combo


def test_names_both_base_substances_and_interaction() -> None:
    for combo, bases in EXPECTED_BASES.items():
        text = _skill_text(combo)
        for base in bases:
            assert f"skills/{base}/SKILL.md" in text, (combo, base)
        assert "## The Interaction" in text, combo
        assert "Who structures the arc" in text, combo
        assert "Who adds tone" in text, combo


def test_no_dose_numbers_or_dosing_verbs() -> None:
    pattern = re.compile(r"\b\d+\s*(mg|g|µg|ug)\b", re.I)
    verbs = re.compile(r"\b(take|taken|ingest(?:ed|ion)?)\b", re.I)
    for combo in COMBO_DIRS:
        text = _skill_text(combo)
        assert not pattern.search(text), f"{combo}: dose figure present"
        # No dosing language: a dosing verb may appear only in non-ingestive
        # narrative use, never adjacent to a quantity or unit in the sentence.
        for sentence in re.split(r"(?<=[.;!?])\s+", text):
            if verbs.search(sentence):
                assert not re.search(
                    r"\b\d+\s*(mg|g|µg|ug)\b|\b(re-dose|another dose)\b",
                    sentence,
                    re.I,
                ), f"{combo}: dosing language in {sentence!r}"


def test_router_routes_blend_inputs_to_combo_skills() -> None:
    from tests.unit.test_router_2cb import route  # reuses the Step-1 parser

    # Destinations are parsed with the markdown ** emphasis kept on; strip it.
    assert route("candy flip").strip("*") == "candy-flip-altered-state"
    assert route("hippy flip").strip("*") == "hippy-flip-altered-state"


def test_router_no_adhoc_blend_note_for_named_blends() -> None:
    router = (REPO_ROOT / "skills" / "router" / "SKILL.md").read_text()
    # The old ad-hoc wording must not be duplicated on the named flips.
    for line in router.splitlines():
        if "candy flip" in line.lower() or "hippy flip" in line.lower():
            assert "-> Route to `lsd-altered-state`" not in line
            assert "-> Route to `psilocybin-altered-state`" not in line
            assert "Blend note:" not in line
    # The combo skills are explicitly named as destinations.
    assert "candy-flip-altered-state" in router
    assert "hippy-flip-altered-state" in router


def test_run_eval_resolves_combo_paths() -> None:
    sys.path.insert(0, str(REPO_ROOT / "bin"))
    import run_eval

    assert run_eval.COMBOS["candy-flip"] == "combos/candy-flip"
    assert run_eval.COMBOS["hippy-flip"] == "combos/hippy-flip"
    assert run_eval.resolve_substances("candy-flip,hippy-flip") == [
        "candy-flip",
        "hippy-flip",
    ]
    assert run_eval.DEFAULT_INTENSITY["candy-flip"] == "medium"
    assert run_eval.DEFAULT_INTENSITY["hippy-flip"] == "medium"
    # 'all' still expands to the 11 base substances only.
    assert "candy-flip" not in run_eval.SUBSTANCES
    assert len(run_eval.SUBSTANCES) == 11
    # Intensity defaults must cover base substances AND combos.
    assert set(run_eval.DEFAULT_INTENSITY) == set(run_eval.SUBSTANCES) | set(run_eval.COMBOS)
    # The combo skills load from under skills/combos/.
    text = run_eval.load_skill("candy-flip")
    assert "candy-flip-altered-state" in text
    text = run_eval.load_skill("hippy-flip")
    assert "hippy-flip-altered-state" in text

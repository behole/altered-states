"""VAL-CONT-007: router routes 2C-B literals + research-grounded slang aliases.

Offline router-eval harness. The router is a markdown skill executed by a
model, so the dry-run equivalent is: parse the router's Step 1 substance
table exactly as a model would read it and assert the literal → route pairs
for >= 12 alias inputs, intensity-token handling via the Step 2 ladder, and
zero cue-literal regression for the 10 substances that predating 2C-B.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTER = REPO_ROOT / "skills" / "router" / "SKILL.md"


def _load_router() -> str:
    return ROUTER.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    """Lowercase; hyphen/space tolerant for substance names ('2c-b' == '2cb')."""
    return re.sub(r"[-_]+", " ", text.lower())


def _step1_rows() -> list[tuple[list[str], str]]:
    """(cue literals, destination skill) for every Step 1 row, in order."""
    text = _load_router()
    block = text.split("### Step 1: Identify Substance", 1)[1]
    block = block.split("### Step 2:", 1)[0]
    rows = []
    for raw in block.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2 or cells[0] in ("Input Pattern", "---"):
            continue
        cues = [cue.strip(' "') for cue in cells[0].split("/")]
        # Annotate modes like "breakthrough mode)" / "(default)" separately;
        # routing identity is the bare skill name.
        dest = re.sub(r"\([^)]*\)", "", cells[1]).strip()
        assert cues and dest, f"unparsed row: {line}"
        rows.append((cues, dest))
    return rows


def route(input_text: str) -> str:
    """Apply the router's first-match rule to a user input."""
    normalized = _normalize(input_text)
    for cues, dest in _step1_rows():
        for cue in cues:
            if re.search(rf"\b{re.escape(_normalize(cue))}\b", normalized):
                return dest
    raise AssertionError(f"no route matched: {input_text!r}")


def route_with_intensity(input_text: str) -> tuple[str, str]:
    """Route via Step 1, then resolve intensity via the 2C-B Step 2 ladder."""
    dest = route(input_text)
    text = _load_router()
    block = text.split("**2C-B:**", 1)[1].split("**DMT (smoked):**", 1)[0]
    ladder: dict[str, str] = {}  # cue literal -> intensity label cell
    for raw in block.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 2 or cells[0] in ("Input", "---"):
            continue
        for cue in cells[0].split("/"):
            if "(no intensity specified)" in cue:
                continue
            m = re.search(r"\*\*\w[\w\s/-]*\*\*", cells[1])
            ladder[cue.strip(' "')] = m.group(0).strip("*") if m else cells[1]
    normalized = _normalize(input_text)
    for cue, intensity in ladder.items():
        if re.search(rf"\b{re.escape(_normalize(cue))}\b", normalized):
            return dest, intensity
    raise AssertionError(f"no intensity cue matched: {input_text!r}")


# ---------------------------------------------------------------------------
# 2C-B alias routing (12 alias inputs, every literal from the dossier naming
# note: 2c-b / 2cb / 2c b / nexus / bees / venus / the chameleon)
# ---------------------------------------------------------------------------


def test_router_eval_twelve_alias_inputs_all_route_2cb() -> None:
    expected = "**2c-b-altered-state**"
    alias_inputs = [
        "let's try 2c-b tonight",
        "2CB",
        "2c b please",
        "nexus",
        "Nexus",
        "we got bees",
        "venus",
        "the chameleon",
        "2cb at the party",
        "take the bees home",
        "venus, please",
        "nexus, please",
    ]
    assert len(alias_inputs) >= 12
    for user_input in alias_inputs:
        assert route(user_input) == expected, f"input {user_input!r} misrouted"


def test_router_literal_variants_are_case_and_separator_tolerant() -> None:
    for variant in ("2C-B", "2cb", "2C B", "2c-b, Medium"):
        assert route(variant) == "**2c-b-altered-state**", variant


def test_router_intensity_token_passthrough_2cb() -> None:
    # Explicit intensity token must pass through to the 2C-B ladder, not
    # silently coerced; missing intensity defaults to medium.
    assert route_with_intensity("nexus medium") == ("**2c-b-altered-state**", "medium")
    tail = _load_router().split("**2C-B:**", 1)[1].split("**DMT (smoked):**", 1)[0]
    # The ladder itself must carry low/medium/high with medium as the default.
    assert '"medium" / "standard"' in tail
    assert "(no intensity specified)" in tail
    assert '"low" / "light" / "subtle"' in tail
    assert '"high" / "heavy" / "strong"' in tail


def test_router_step3_2cb_name_and_thematic_cues() -> None:
    text = _load_router()
    # Name-inference block in Step 3.3.
    step3 = text.split("### Step 3: Handle Ambiguity", 1)[1]
    assert '"nexus" / "bees" / "venus" / "the chameleon" → 2C-B medium' in step3
    # Thematic cue block: warm + vivid visual blend is distinctive vs MDMA.
    assert "→ **2C-B**" in step3


def test_2cb_router_aliases_are_grounded_in_research_annotations() -> None:
    dossier = (REPO_ROOT / "research" / "2c-b" / "dossier.md").read_text(encoding="utf-8")
    for alias in ("nexus", "bees", "venus", "the chameleon"):
        assert alias in dossier, f"alias {alias!r} not documented in research/2c-b dossier"
    # The dropped alias must not remain a router or dossier-table alias (the
    # dossier annotation explaining the drop is fine — it is not a "Grounding" row).
    rows = dossier.split("### 4a.", 1)[1].split("Policy:", 1)[0]
    assert '| "bump" |' not in rows, "dropped alias 'bump' still a dossier grounding row"
    # Route cues and dossier names must agree — no ad-hoc alias invented here.
    step1_cues = {c for cues, _ in _step1_rows() for c in cues}
    assert {"2c-b", "2cb", "nexus", "bees", "venus", "the chameleon"} <= step1_cues
    assert "bump" not in step1_cues, "dropped alias 'bump' still a router cue"


# ---------------------------------------------------------------------------
# Regression: the 10 pre-2C-B substances route exactly as before. The literals
# below are verbatim from the pre-change router (git checkout HEAD~1 of the
# file); each must still be present and route to the unchanged destination.
# ---------------------------------------------------------------------------

DEFAULT_ROUTE = "**psilocybin-altered-state**"


def test_router_regression_ten_substances_cues_unchanged() -> None:
    text = _load_router()
    literal_blocks = [
        '"psilocybin" / "mushroom" / "shrooms" / "magic mushrooms" / "the teacher"',
        '"lsd" / "acid" / "lucy" / "tabs" / "the technician"',
        '"mdma" / "molly" / "ecstasy" / "e" / "rolling" / "the connector"',
        '"dmt" / "n,n-dmt" / "deemz" / "the spirit molecule" / "hyperspace" / "the rocket"',
        '"5-meo-dmt" / "5-meo" / "bufo" / "toad" / "the dissolver" / "the source"',
        '"ayahuasca" / "aya" / "the vine" / "the medicine"',
        '"mescaline" / "peyote" / "san pedro" / "cactus" / "the elder" / "buttons" / "mesc"',
        '"ketamine" / "special k" / "k" / "esketamine" / "spravato"',
        '"salvia" / "salvia divinorum" / "sally d" / "sally"',
        '"ibogaine" / "iboga" / "the ancestor" / "root bark" / "bwiti"',
    ]
    for block in literal_blocks:
        assert block in text, f"pre-existing cue literal block missing: {block}"


def test_router_regression_ten_substance_inputs_still_route() -> None:
    pairs = [
        ("let's take shrooms", "**psilocybin-altered-state**"),
        ("drop some acid", "**lsd-altered-state**"),
        ("rolling hard", "**mdma-altered-state**"),
        ("deemz", "**dmt-altered-state**"),
        ("toad time", "**5-meo-dmt-altered-state**"),
        ("aya ceremony", "**ayahuasca-altered-state**"),
        ("san pedro", "**mescaline-altered-state**"),
        ("special k", "**ketamine-altered-state**"),
        ("sally d", "**salvia-altered-state**"),
        ("iboga", "**ibogaine-altered-state**"),
    ]
    assert len(pairs) == 10
    for user_input, dest in pairs:
        assert route(user_input) == dest, f"regression: {user_input!r} no longer routes"


def test_router_regression_default_route_untouched() -> None:
    assert route("i want to explore an altered state") == DEFAULT_ROUTE
    assert route("no idea, just a trip") == DEFAULT_ROUTE


# ---------------------------------------------------------------------------
# Eval-runner registry knows every substance the router can produce.
# ---------------------------------------------------------------------------


def test_run_eval_registry_covers_router_destinations() -> None:
    sys.path.insert(0, str(REPO_ROOT / "bin"))
    import run_eval

    assert "2c-b" in run_eval.SUBSTANCES
    for s in (
        "psilocybin",
        "lsd",
        "mdma",
        "dmt",
        "ayahuasca",
        "5-meo-dmt",
        "mescaline",
        "ketamine",
        "salvia",
        "ibogaine",
    ):
        assert s in run_eval.SUBSTANCES
    assert run_eval.resolve_substances("2c-b") == ["2c-b"]
    assert run_eval.DEFAULT_INTENSITY["2c-b"] == "medium"
    # Every declared substance AND combo has a default intensity — 'all' never
    # KeyErrors (combo ids are accepted by --substances but excluded from 'all').
    assert set(run_eval.DEFAULT_INTENSITY) == set(run_eval.SUBSTANCES) | set(run_eval.COMBOS)

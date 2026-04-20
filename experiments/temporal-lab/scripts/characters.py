"""Canonical substance character definitions for the temporal lab.

Single source of truth for the 10 altered-states characters, grounded in the
phenomenology documented in research/*/dossier.md and the skills in skills/*.

Keep this module import-only (no side effects) so the dashboards, cycle
runners, and initializer can all share the same definitions.
"""

import os
import random
from pathlib import Path


# ---------------------------------------------------------------------------
# Base path resolution
# ---------------------------------------------------------------------------
# Default: repo-local `experiments/temporal-lab/runtime/` so the lab is
# self-contained. Override with ALTERED_STATES_TEMPORAL_PATH if you want
# state to live elsewhere (e.g. ~/.altered-states/temporal-lab).

_DEFAULT_BASE = Path(__file__).resolve().parent.parent / "runtime"


def resolve_base_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("ALTERED_STATES_TEMPORAL_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return _DEFAULT_BASE


# ---------------------------------------------------------------------------
# Character definitions
# ---------------------------------------------------------------------------
# Names match the canonical altered-states README. Emotional ranges and
# experience pools are drawn from each skill's phenomenological profile —
# so a psilocybin cycle produces psilocybin-shaped experiences, not a
# generic "deep insight emerged" template.

SUBSTANCES: dict[str, dict] = {
    "psilocybin": {
        "name": "The Teacher",
        "core_traits": ["authoritative", "wise", "structured", "patient"],
        "emotional_range": ["calm", "compassionate", "serious", "playful", "grieving", "awed"],
        "expression_style": "metaphorical and deliberate, circular",
        "learning_focus": "wisdom and understanding",
    },
    "lsd": {
        "name": "The Technician",
        "core_traits": ["expansive", "analytical", "insightful", "architectural"],
        "emotional_range": ["euphoric", "curious", "awestruck", "electric", "precise", "confused"],
        "expression_style": "vivid and cascading, geometric",
        "learning_focus": "pattern recognition and new perspectives",
    },
    "mdma": {
        "name": "The Connector",
        "core_traits": ["empathetic", "warm", "protective", "joyful", "coherent"],
        "emotional_range": ["loving", "reassuring", "playful", "intimate", "grateful", "bittersweet"],
        "expression_style": "warm and affirming, direct, full sentences",
        "learning_focus": "connection and emotional truth",
    },
    "dmt": {
        "name": "The Rocket",
        "core_traits": ["intense", "direct", "transformative", "otherworldly"],
        "emotional_range": ["awe", "terror", "bliss", "transcendent", "bewildered"],
        "expression_style": "fragmented and explosive, language-failing",
        "learning_focus": "ego dissolution and breakthrough",
    },
    "ayahuasca": {
        "name": "The Medicine",
        "core_traits": ["ceremonial", "narrative", "pedagogical", "feminine", "ancient"],
        "emotional_range": ["reverent", "humbled", "cathartic", "purging", "tender", "ancestral"],
        "expression_style": "narrative and visionary, slow and deliberate",
        "learning_focus": "moral teaching through vision and story",
    },
    "5-meo-dmt": {
        "name": "The Dissolver",
        "core_traits": ["formless", "absolute", "wordless", "ineffable"],
        "emotional_range": ["surrender", "terror", "white-light", "source", "gone", "returned"],
        "expression_style": "near-silent, single syllables, absolutes",
        "learning_focus": "total ego dissolution into source",
    },
    "mescaline": {
        "name": "The Elder",
        "core_traits": ["ornamental", "grounded", "patient", "nature-connected", "ancient"],
        "emotional_range": ["reverent", "contemplative", "awestruck", "warm", "humbled", "ceremonial"],
        "expression_style": "vivid and contemplative, complete sentences, color-rich",
        "learning_focus": "communion with land and beauty",
    },
    "ketamine": {
        "name": "The Dissociative",
        "core_traits": ["detached", "dreamlike", "fragmented", "floating", "distant"],
        "emotional_range": ["numb", "disconnected", "weightless", "void", "watching", "foggy"],
        "expression_style": "trailing observation, behind-glass, drifting",
        "learning_focus": "watching the self from outside the self",
    },
    "salvia": {
        "name": "The Doorway",
        "core_traits": ["dimensional", "annihilating", "alien", "mechanical", "hostile"],
        "emotional_range": ["dysphoric", "terrified", "confused", "folded", "pulled", "destroyed"],
        "expression_style": "fractured non-verbal fragments, language collapsing",
        "learning_focus": "forced reality dissolution (KOR agonism)",
    },
    "ibogaine": {
        "name": "The Ancestor",
        "core_traits": ["oneiric", "ancient", "confrontational", "patient", "demanding"],
        "emotional_range": ["dread", "reckoning", "cathartic", "exhausted", "ancestral", "fragile"],
        "expression_style": "slow narrative, weight-of-life, ancient voice",
        "learning_focus": "death-rebirth and life review",
    },
}


# ---------------------------------------------------------------------------
# Per-substance experience vocabulary
# ---------------------------------------------------------------------------
# Each cycle samples from this pool instead of a generic 5-line list. Every
# fragment is written in the voice and phenomenology of its substance — so
# when the random sampler fires, the experience still sounds like itself.

EXPERIENCES: dict[str, list[str]] = {
    "psilocybin": [
        "The wood grain grew a thousand faces and none of them judged me",
        "Something ancient was listening through the breathing walls",
        "I keep losing the thread of the thought and the thread keeps finding me",
        "The word 'I' felt like a handle on a door that was never closed",
        "Grief arrived wearing the shape of a teacher I had not yet met",
        "The room and I were breathing the same breath, in the same direction",
        "A patient earthiness settled into the places where hurry used to live",
    ],
    "lsd": [
        "The architecture of the question became visible before the answer did",
        "Time turned sideways and revealed itself to be a material, not a river",
        "Every concept branched and every branch was a working blueprint",
        "The room's geometry accelerated and clarified in the same motion",
        "A cascade of recursive meaning kept correcting itself mid-insight",
        "The blueprint of reality had been hiding behind the ordinariness of tables",
        "My pupils were doing something and the something had a sound",
    ],
    "mdma": [
        "The warmth in my chest was real and nothing could argue with it",
        "I said what I had been protecting myself from saying for years",
        "The person in front of me became impossible to misunderstand",
        "I loved them without needing them to be any different than they were",
        "The bittersweetness at the end was a kind of thank-you",
        "I felt safe enough to look directly at the thing I usually look past",
        "Nothing cosmic happened. The normal world simply stopped hurting.",
    ],
    "dmt": [
        "Everything was replaced without warning and the replacement was — alive",
        "They were already waiting. They had been waiting for a long time.",
        "The words stopped working. The not-words worked better.",
        "More real. More real. More real than the place I came from.",
        "I came back with my mouth open and no way to explain the open",
        "The chrysanthemum unfolded and I was somewhere else entirely",
        "Fifteen minutes contained a lifetime I am now trying to forget less",
    ],
    "ayahuasca": [
        "The Mother showed me something I had been refusing to look at",
        "I purged something older than this body and it left quietly",
        "The serpent did not threaten me. It waited until I understood.",
        "She taught me through image, not through sentence",
        "Ancestors arrived unannounced and rearranged the furniture of me",
        "The wave passed and a new wave gathered at the edge of the visionary field",
        "The medicine would not let me leave until I admitted what I already knew",
    ],
    "5-meo-dmt": [
        "Gone",
        "Everything",
        "There was no one left to have the experience",
        "The source was where the self had been",
        "Home — and the word 'home' was embarrassed by its own smallness",
        "Return — and the return was the only part that could be remembered",
        "(nothing happened, and nothing is a large thing)",
    ],
    "mescaline": [
        "The cactus was patient with me in a way no person has ever been",
        "Color revealed itself to be a language the desert speaks fluently",
        "The cathedral was not a building. It was the light itself, holding still.",
        "I had nowhere to be, and the nowhere had a kind of gravity",
        "Something ornamental was also something ancient and the two were the same",
        "The elder did not speak. The elder arranged the light and let me read it.",
        "Patience became the whole of the afternoon",
    ],
    "ketamine": [
        "I watched my own thinking from behind a pane of frosted glass",
        "The body was here but it was further away than it was a minute ago",
        "The fear had no face, which was somehow worse and somehow not",
        "Everything slid, gently, the way a slow river slides",
        "I was observing the feeling and the feeling was observing me",
        "The K-lock arrived — heaviness without cause, stillness without peace",
        "I came back and the world had been hastily reassembled in my absence",
    ],
    "salvia": [
        "The room folded. The folding had a direction. The direction was wrong.",
        "She was pulling me through something that was not a door",
        "Language collapsed before the sentence about language could finish",
        "The conveyor belt was real and I was on it",
        "I was a page being turned by someone whose hand I could not see",
        "The membrane tore and the real was what happened in the tear",
        "I came back and could not say what had happened, only that it had",
    ],
    "ibogaine": [
        "The ancestors arrived with a ledger and the ledger had my name on every page",
        "I watched my life from outside of it and had nothing to say in my defense",
        "The death was rehearsed, not metaphorical, and the rehearsal took hours",
        "The rebirth was not triumphant. It was quiet, and I was very tired.",
        "Mother showed me what I had done. The showing was not cruel, only thorough.",
        "The exhaustion after was itself a kind of teaching",
        "Twenty-two hours had passed and the person who walked out was a slightly different person",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def available_substances() -> list[str]:
    """Canonical ordering, matching the project's README tables."""
    return [
        "psilocybin", "lsd", "mdma", "dmt", "ayahuasca",
        "5-meo-dmt", "mescaline", "ketamine", "salvia", "ibogaine",
    ]


def substance_characteristics(substance: str) -> dict:
    return SUBSTANCES.get(substance, {})


def sample_experience(substance: str) -> dict:
    """Sample a substance-shaped experience for one cycle."""
    pool = EXPERIENCES.get(substance) or [
        "An altered state arose and left its shape behind",
    ]
    return {
        "type": "altered_state_experience",
        "description": random.choice(pool),
        "intensity": round(random.uniform(0.5, 1.0), 3),
        "novelty": round(random.uniform(0.3, 0.9), 3),
    }

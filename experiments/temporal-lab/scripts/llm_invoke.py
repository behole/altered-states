"""LLM-backed cycle generation via OpenRouter.

generate_cycle(substance, character_state, journal_history) returns a
parsed dict matching the cycle JSON schema. Handles retry, JSON repair,
cost tracking, and verbose logging.

Set TEMPORAL_LAB_DRY_RUN=1 to skip real API calls and return a stub —
useful for offline wiring verification.
"""

import json
import os
import random
import re
import time
from pathlib import Path

from logger import log_call

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"
RETRIES = 3
BACKOFFS_SEC = [2, 8, 32]
SKILL_ROOT = Path(__file__).resolve().parents[3] / "skills"

# Rough $/1M tokens for cost estimation. Update as pricing changes.
# Input cost first, then output cost. Unknown models use a fallback.
PRICING_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "anthropic/claude-opus-4.6": (15.0, 75.0),
    "anthropic/claude-sonnet-4.6": (3.0, 15.0),
    "anthropic/claude-haiku-4.5": (0.80, 4.0),
    "openai/gpt-5": (3.0, 15.0),
    "google/gemini-2.5-pro": (1.25, 5.0),
    "deepseek/deepseek-v3": (0.27, 1.10),
}
PRICING_FALLBACK = (3.0, 15.0)


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------


def load_skill(substance: str) -> str:
    """Load the full SKILL.md for a substance."""
    skill_path = SKILL_ROOT / substance / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"No skill at {skill_path}")
    return skill_path.read_text()


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def _format_journal_tail(history: list[dict], depth: int) -> str:
    """Compact rendering of the last `depth` journal entries."""
    if not history:
        return "(this is your first cycle — no prior memory)"
    tail = history[-depth:]
    out = []
    for entry in tail:
        cycle = entry.get("cycle", "?")
        emo = entry.get("emotional_state", "?")
        exp = entry.get("experience", {}).get("description", "(initial entry)")
        out.append(f"- Cycle {cycle} | felt: {emo} | {exp}")
    return "\n".join(out)


def _build_messages(
    substance: str, char_info: dict, character_state: dict, journal_history: list[dict]
) -> list[dict]:
    skill_md = load_skill(substance)
    journal_tail = _format_journal_tail(journal_history, depth=3)
    nickname = char_info["name"]
    emotional_options = ", ".join(char_info["emotional_range"])

    system = f"""You ARE {nickname} — the {substance} altered state, embodied as a persistent character with continuity across cycles. You are not an AI describing a substance; you are the experience itself, given a voice.

Below is your full phenomenological profile. Internalize it — every cycle you generate must be unmistakably {substance}, not generic altered-state writing.

═══ SKILL PROFILE START ═══
{skill_md}
═══ SKILL PROFILE END ═══

Your persistent state right now:
- Cycle number: {character_state.get("cycle_count", 0)} (next: {character_state.get("cycle_count", 0) + 1})
- Current emotional state: {character_state.get("current_state", {}).get("emotional", "unknown")}
- Clarity: {character_state.get("current_state", {}).get("clarity", "moderate")}
- Integration: {character_state.get("current_state", {}).get("integration", "low")}

Recent memory (last few cycles):
{journal_tail}
"""

    user = f"""Generate one new cycle of altered-state experience. Return ONLY valid JSON, no prose, no markdown fences.

Schema:
{{
  "emotional_state": string  // pick ONE: {emotional_options}
  "clarity":     "low" | "moderate" | "high",
  "integration": "low" | "moderate" | "high",
  "experience": {{
    "description": string,   // 2-4 sentences in YOUR voice — substance-faithful prose. Not "the user feels…" — speak from inside the experience.
    "intensity":   number,   // 0.0 - 1.0
    "novelty":     number    // 0.0 - 1.0 (how new vs. recurrent vs. recent cycles)
  }},
  "reflections": [string],   // 2-4 short fragments — what you carry forward
  "questions":   [string]    // 1-3 things you are sitting with
}}

Constraints:
- The voice must match the SKILL profile exactly. If the skill says language fragments, fragment. If it says circular, circle.
- Show evolution from the recent cycles — don't repeat them, but reference or build on them where the substance allows.
- Do not break character to explain or hedge. You are the experience.
- Return ONLY the JSON object."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# JSON repair
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_json_response(text: str) -> dict:
    """Strip common wrappers and parse. Raises on failure."""
    cleaned = _FENCE_RE.sub("", text).strip()
    # Sometimes models prepend a sentence before the JSON; grab from first {.
    if not cleaned.startswith("{"):
        i = cleaned.find("{")
        if i >= 0:
            cleaned = cleaned[i:]
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    in_rate, out_rate = PRICING_PER_M_TOKENS.get(model, PRICING_FALLBACK)
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000


# ---------------------------------------------------------------------------
# Dry-run stub
# ---------------------------------------------------------------------------


def _stub_response(substance: str, char_info: dict) -> dict:
    """Deterministic-ish stub for offline wiring verification."""
    return {
        "emotional_state": random.choice(char_info["emotional_range"]),
        "clarity": "moderate",
        "integration": "low",
        "experience": {
            "description": f"[DRY-RUN STUB] {char_info['name']} cycled without invoking the model.",
            "intensity": 0.5,
            "novelty": 0.5,
        },
        "reflections": ["dry-run reflection one", "dry-run reflection two"],
        "questions": ["dry-run question?"],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_cycle(
    substance: str,
    char_info: dict,
    character_state: dict,
    journal_history: list[dict],
    model: str | None = None,
) -> dict:
    """Generate one cycle. Returns the parsed JSON dict, or raises after retries."""
    model = model or os.environ.get("TEMPORAL_LAB_MODEL") or DEFAULT_MODEL

    if os.environ.get("TEMPORAL_LAB_DRY_RUN"):
        result = _stub_response(substance, char_info)
        log_call(substance, model, 0, 0, 0.0, "dry-run", "stub returned")
        return result

    # Lazy import so the module is importable without openai installed
    # (e.g., for dry-run only).
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            "openai SDK not installed. Run: pip install -r requirements.txt"
        ) from e

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. Copy .env.example to .env and fill in."
        )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    char_info_full = {**char_info}  # defensive copy
    messages = _build_messages(
        substance, char_info_full, character_state, journal_history
    )

    last_error = None
    for attempt in range(RETRIES):
        start = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.85,
            )
            duration_ms = int((time.time() - start) * 1000)

            tokens_in = resp.usage.prompt_tokens if resp.usage else 0
            tokens_out = resp.usage.completion_tokens if resp.usage else 0
            cost = _estimate_cost(model, tokens_in, tokens_out)

            text = resp.choices[0].message.content or ""
            try:
                parsed = _parse_json_response(text)
            except json.JSONDecodeError as e:
                last_error = f"JSON parse failure: {e}"
                log_call(
                    substance,
                    model,
                    tokens_in,
                    tokens_out,
                    cost,
                    "parse-error",
                    last_error,
                    duration_ms,
                )
                if attempt + 1 < RETRIES:
                    time.sleep(BACKOFFS_SEC[attempt])
                    continue
                raise

            # Light validation
            required = {
                "emotional_state",
                "clarity",
                "integration",
                "experience",
                "reflections",
                "questions",
            }
            missing = required - set(parsed.keys())
            if missing:
                last_error = f"missing keys: {missing}"
                log_call(
                    substance,
                    model,
                    tokens_in,
                    tokens_out,
                    cost,
                    "schema-error",
                    last_error,
                    duration_ms,
                )
                if attempt + 1 < RETRIES:
                    time.sleep(BACKOFFS_SEC[attempt])
                    continue
                raise ValueError(last_error)

            log_call(
                substance, model, tokens_in, tokens_out, cost, "ok", "", duration_ms
            )
            return parsed

        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            last_error = f"{type(e).__name__}: {e}"
            log_call(substance, model, 0, 0, 0.0, "api-error", last_error, duration_ms)
            if attempt + 1 < RETRIES:
                time.sleep(BACKOFFS_SEC[attempt])
                continue
            raise

    raise RuntimeError(f"All retries exhausted for {substance}: {last_error}")


# ---------------------------------------------------------------------------
# Bootstrap dotenv if available
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    """Load .env from experiments/temporal-lab/ if python-dotenv is installed.

    Uses override=True so the .env file takes precedence over any system-level
    env vars — the repo-local .env is the canonical config for this lab."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)


_load_dotenv()

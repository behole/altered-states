"""LLM-backed cycle generation via any OpenAI-compatible provider.

generate_cycle(substance, char_info, character_state, journal_history) returns a
parsed Cycle dict. Handles retry, JSON repair, cost tracking, and verbose logging.

Set TEMPORAL_LAB_DRY_RUN=1 to skip real API calls and return a stub —
useful for offline wiring verification.

Provider is configured via env vars (see .env.example):

  LLM_BASE_URL  — OpenAI-compatible endpoint
  LLM_API_KEY   — API key
  LLM_MODEL     — model ID
  LLM_JSON_MODE — "native" (response_format json_object) or "prompt"
                  (rely on the "Return ONLY JSON" instruction)

Legacy vars still work as fallbacks: OPENROUTER_API_KEY,
DEEPSEEK_API_KEY, TEMPORAL_LAB_MODEL. When LLM_BASE_URL is unset the
endpoint is auto-detected: OpenRouter if an OpenRouter key is present or
the model looks like an OpenRouter slug ("provider/model" or ":free"),
else DeepSeek. Free endpoints (OpenRouter ":free" models, Groq free
tier, Gemini free tier) are $0 — just point the env at them.
"""

import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, TypedDict, cast

from characters import CharacterProfile
from logger import CallRecord, log_call

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
RETRIES = 3
BACKOFFS_SEC = [2, 8, 32]
SKILL_ROOT = Path(__file__).resolve().parents[3] / "skills"

# Generation parameters for one cycle.
TEMPERATURE = 0.85
MAX_TOKENS = 8192

# How to ask the provider for JSON. "native" uses response_format; "prompt"
# relies on the instruction in the prompt alone.
NATIVE_JSON_MODE = "native"
PROMPT_JSON_MODE = "prompt"

# Every cycle must carry these keys before it is accepted.
REQUIRED_CYCLE_KEYS = frozenset({"emotional_state", "clarity", "integration", "experience", "reflections", "questions"})

# Rough $/1M tokens for cost estimation. Update as pricing changes.
# Input cost first, then output cost. Unknown models use a fallback.
PRICING_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    # DeepSeek (paid fallback)
    "deepseek-v4-pro": (0.50, 2.00),
    "deepseek-reasoner": (0.50, 2.00),
    "deepseek-chat": (0.14, 0.28),
    # Groq paid rates (free tier is $0 — the "__free__" row covers it)
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "gpt-oss-120b": (0.15, 0.60),
    # OpenRouter ":free" models and other free endpoints are always $0
    "__free__": (0.0, 0.0),
}
PRICING_FALLBACK = (3.0, 15.0)


class Experience(TypedDict):
    """The felt content of one cycle."""

    description: str
    intensity: float
    novelty: float


class Cycle(TypedDict):
    """One generated cycle, matching the journal schema."""

    emotional_state: str
    clarity: str
    integration: str
    experience: Experience
    reflections: list[str]
    questions: list[str]


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


def _format_journal_tail(history: list[dict[str, Any]], depth: int) -> str:
    """Compact rendering of the last `depth` journal entries."""
    if not history:
        return "(this is your first cycle — no prior memory)"
    out = []
    for entry in history[-depth:]:
        cycle = entry.get("cycle", "?")
        emotional = entry.get("emotional_state", "?")
        experience = entry.get("experience")
        if isinstance(experience, dict):
            description = experience.get("description", "(initial entry)")
        else:
            description = str(experience) if experience else "(initial entry)"
        out.append(f"- Cycle {cycle} | felt: {emotional} | {description}")
    return "\n".join(out)


def _build_messages(
    substance: str,
    char_info: CharacterProfile,
    character_state: dict[str, Any],
    journal_history: list[dict[str, Any]],
) -> list[dict[str, str]]:
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


def _parse_json_response(text: str) -> dict[str, Any]:
    """Strip common wrappers and parse. Raises on failure."""
    cleaned = _FENCE_RE.sub("", text).strip()
    # Sometimes models prepend a sentence before the JSON; grab from first {.
    if not cleaned.startswith("{"):
        i = cleaned.find("{")
        if i >= 0:
            cleaned = cleaned[i:]
    parsed: dict[str, Any] = json.loads(cleaned)
    return parsed


def _parse_and_validate(text: str) -> tuple[Cycle | None, str]:
    """Parse and schema-check one completion.

    Returns `(cycle, "")` on success or `(None, problem)` on failure.
    """
    try:
        parsed = _parse_json_response(text)
    except json.JSONDecodeError as e:
        return None, f"JSON parse failure: {e}"
    missing = REQUIRED_CYCLE_KEYS - set(parsed.keys())
    if missing:
        return None, f"missing keys: {missing}"
    return cast(Cycle, parsed), ""


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model.endswith(":free"):
        return 0.0
    in_rate, out_rate = PRICING_PER_M_TOKENS.get(model, PRICING_FALLBACK)
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000


# ---------------------------------------------------------------------------
# Dry-run stub
# ---------------------------------------------------------------------------


def _stub_response(substance: str, char_info: CharacterProfile) -> Cycle:
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
# Provider client
# ---------------------------------------------------------------------------


def _default_base_url(model: str) -> str:
    """Pick a sensible default endpoint when LLM_BASE_URL is unset."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return "https://openrouter.ai/api/v1"
    if "/" in model or model.endswith(":free"):
        return "https://openrouter.ai/api/v1"
    return DEFAULT_BASE_URL


def _resolve_config(model: str | None) -> tuple[str, str, str]:
    """Resolve (model, base_url, json_mode) from arguments and environment."""
    resolved_model = model or os.environ.get("LLM_MODEL") or os.environ.get("TEMPORAL_LAB_MODEL") or DEFAULT_MODEL
    base_url = os.environ.get("LLM_BASE_URL") or _default_base_url(resolved_model)
    json_mode = os.environ.get("LLM_JSON_MODE", NATIVE_JSON_MODE)
    return resolved_model, base_url, json_mode


def _make_client(base_url: str) -> Any:
    """Build an OpenAI-compatible client, or raise with an actionable message."""
    # Lazy import so the module is importable without openai installed
    # (e.g., for dry-run only).
    try:
        from openai import OpenAI  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("openai SDK not installed. Run: pip install -r requirements.txt") from e

    api_key = (
        os.environ.get("LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "No API key set. Set LLM_API_KEY (or OPENROUTER_API_KEY / DEEPSEEK_API_KEY) — see .env.example."
        )

    return OpenAI(base_url=base_url, api_key=api_key)


def _completion_kwargs(model: str, messages: list[dict[str, str]], json_mode: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    if json_mode == NATIVE_JSON_MODE:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_cycle(
    substance: str,
    char_info: CharacterProfile,
    character_state: dict[str, Any],
    journal_history: list[dict[str, Any]],
    model: str | None = None,
) -> Cycle:
    """Generate one cycle. Returns the parsed JSON dict, or raises after retries."""
    resolved_model, base_url, json_mode = _resolve_config(model)

    if os.environ.get("TEMPORAL_LAB_DRY_RUN"):
        result = _stub_response(substance, char_info)
        log_call(CallRecord(substance, resolved_model, 0, 0, 0.0, "dry-run", "stub returned"))
        return result

    client = _make_client(base_url)
    messages = _build_messages(substance, char_info, character_state, journal_history)

    last_error: str | None = None
    for attempt in range(RETRIES):
        start = time.time()
        kwargs = _completion_kwargs(resolved_model, messages, json_mode)
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            last_error = f"{type(e).__name__}: {e}"
            log_call(CallRecord(substance, resolved_model, 0, 0, 0.0, "api-error", last_error, duration_ms))
            # Some free endpoints 400 on response_format — drop it and retry
            # the remaining attempts in instruction-only JSON mode.
            if json_mode == NATIVE_JSON_MODE:
                json_mode = PROMPT_JSON_MODE
            if attempt + 1 >= RETRIES:
                raise
            time.sleep(BACKOFFS_SEC[attempt])
            continue

        duration_ms = int((time.time() - start) * 1000)
        tokens_in = resp.usage.prompt_tokens if resp.usage else 0
        tokens_out = resp.usage.completion_tokens if resp.usage else 0
        cost = _estimate_cost(resolved_model, tokens_in, tokens_out)
        cycle, problem = _parse_and_validate(resp.choices[0].message.content or "")

        if cycle is not None:
            log_call(CallRecord(substance, resolved_model, tokens_in, tokens_out, cost, "ok", "", duration_ms))
            return cycle

        status = "parse-error" if problem.startswith("JSON parse failure") else "schema-error"
        log_call(CallRecord(substance, resolved_model, tokens_in, tokens_out, cost, status, problem, duration_ms))
        last_error = problem
        if attempt + 1 >= RETRIES:
            raise ValueError(problem)
        time.sleep(BACKOFFS_SEC[attempt])

    raise RuntimeError(f"All retries exhausted for {substance}: {last_error}")


# ---------------------------------------------------------------------------
# Bootstrap dotenv if available
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    """Load .env from experiments/temporal-lab/ if python-dotenv is installed.

    Uses override=True so the .env file takes precedence over any system-level
    env vars — the repo-local .env is the canonical config for this lab.
    """
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)


_load_dotenv()

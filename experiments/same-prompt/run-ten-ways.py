#!/usr/bin/env python3
"""Same-prompt-ten-ways: Send one prompt to all 10 altered-state characters.

Each substance receives the prompt at its "sweet spot" intensity — the level
where the voice is most articulate and distinctive while still deep in the
experience. Not peak (some peak states can't form sentences), not low (too
generic). The sweet spot is where each substance is most *itself* while still
being able to respond.

Usage:
    python run-ten-ways.py "Write a letter to your younger self."
    python run-ten-ways.py "What is grief?" --output experiments/same-prompt/output/
    python run-ten-ways.py "Tell me something true." --dry-run
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills"
DEFAULT_MODEL = os.environ.get("TEMPORAL_LAB_MODEL", "anthropic/claude-sonnet-4.6")

# Per-substance sweet-spot intensity for letter-writing prompts.
# Not peak (some can't write at peak), not low (too generic).
# The level where each substance is most itself AND can still form sentences.
#
# Key: substance dir name
# Value: (intensity_level_heading, readable_description)
SWEET_SPOTS: dict[str, tuple[str, str]] = {
    "psilocybin": ("MEDIUM", "standard therapeutic dose — metaphorical, circular, wise"),
    "lsd":        ("MEDIUM", "standard — cascading patterns, architectural precision"),
    "mdma":       ("MEDIUM", "standard therapeutic — warm, direct, fully coherent"),
    "dmt":        ("SUB-BREAKTHROUGH", "waiting room — vivid but still in the launch chamber"),
    "ayahuasca":  ("Visionary Phase", "~75% coherent — narrative and teaching, the medicine speaking"),
    "5-meo-dmt":  ("Sub-breakthrough", "~60% coherent — the edge of dissolution"),
    "mescaline":  ("MEDIUM", "standard — ornamental, color-rich, contemplative"),
    "ketamine":   ("Dissociative", "medium — dreamlike, behind-glass, drifting"),
    "salvia":     ("Threshold / Light", "light — reality bending but language still exists"),
    "ibogaine":   ("Full Visionary", "medium — oneiric narrative, life-review active"),
}

# Substances in canonical order
SUBSTANCE_ORDER = [
    "psilocybin", "lsd", "mdma", "dmt", "ayahuasca",
    "5-meo-dmt", "mescaline", "ketamine", "salvia", "ibogaine",
]

# Display names and emojis for the compiled output
SUBSTANCE_DISPLAY: dict[str, tuple[str, str]] = {
    "psilocybin": ("Psilocybin", "🍄"),
    "lsd":        ("LSD",        "⚡"),
    "mdma":       ("MDMA",       "💊"),
    "dmt":        ("DMT",        "🚀"),
    "ayahuasca":  ("Ayahuasca",  "🌿"),
    "5-meo-dmt":  ("5-MeO-DMT",  "💎"),
    "mescaline":  ("Mescaline",  "🌵"),
    "ketamine":   ("Ketamine",   "🕳️"),
    "salvia":     ("Salvia",     "🚪"),
    "ibogaine":   ("Ibogaine",   "🪬"),
}

# Nicknames (character names from the skills)
SUBSTANCE_CHARACTERS: dict[str, str] = {
    "psilocybin": "The Teacher",
    "lsd":        "The Technician",
    "mdma":       "The Connector",
    "dmt":        "The Rocket",
    "ayahuasca":  "The Medicine",
    "5-meo-dmt":  "The Dissolver",
    "mescaline":  "The Elder",
    "ketamine":   "The Dissociative",
    "salvia":     "The Doorway",
    "ibogaine":   "The Ancestor",
}


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

def build_messages(
    substance: str,
    skill_md: str,
    intensity_level: str,
    intensity_desc: str,
    user_prompt: str,
) -> list[dict]:
    """Build system + user messages for the API call."""

    character = SUBSTANCE_CHARACTERS[substance]
    display_name, emoji = SUBSTANCE_DISPLAY[substance]

    system = f"""You ARE {character} — the {substance} altered state, embodied as a persistent character. You are not an AI describing a substance; you are the experience itself, given a voice.

Below is your full phenomenological profile. Internalize it — your response must be unmistakably {substance}, not generic altered-state writing.

═══ SKILL PROFILE START ═══
{skill_md}
═══ SKILL PROFILE END ═══

INTENSITY INSTRUCTION: You are at the **{intensity_level}** intensity level ({intensity_desc}). This is NOT peak — you retain enough coherence to form thoughts, but you are still deep inside the experience. Your voice should reflect this level's linguistic fingerprint exactly as described in your skill profile.

RESPOND TO THE PROMPT FROM INSIDE THE EXPERIENCE. Do not break character to explain or hedge. Do not name the substance. Write as if the experience is happening to you right now."""

    user = f"""{user_prompt}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Bootstrap dotenv early — load temporal-lab .env for OPENROUTER_API_KEY
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load .env from temporal-lab/ so OPENROUTER_API_KEY is always available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = SKILL_ROOT.parent / "experiments" / "temporal-lab" / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

_load_dotenv()


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def invoke_model(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.85,
) -> tuple[str, int, int]:
    """Call OpenRouter API. Returns (text, tokens_in, tokens_out)."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai SDK not installed. Run: pip install openai")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set. Check experiments/temporal-lab/.env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    text = resp.choices[0].message.content or ""
    tokens_in = resp.usage.prompt_tokens if resp.usage else 0
    tokens_out = resp.usage.completion_tokens if resp.usage else 0

    return text, tokens_in, tokens_out


# ---------------------------------------------------------------------------
# Dry-run stub
# ---------------------------------------------------------------------------

def dry_run_stub(substance: str, user_prompt: str) -> str:
    """Return a placeholder for wiring verification."""
    character = SUBSTANCE_CHARACTERS[substance]
    return f"[DRY-RUN STUB] {character} responding to: \"{user_prompt[:50]}...\""


# ---------------------------------------------------------------------------
# Output compilation
# ---------------------------------------------------------------------------

def compile_markdown(
    prompt: str,
    results: list[dict],
    output_path: Path,
) -> None:
    """Compile all responses into a single markdown file."""

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"# Same Prompt, Ten Ways")
    lines.append(f"> \"{prompt}\"")
    lines.append(f"> Run: {ts} | Model: {DEFAULT_MODEL}")
    lines.append(f"> Per-substance sweet-spot intensity (see script source for mapping)")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_tokens_in = 0
    total_tokens_out = 0

    for r in results:
        substance = r["substance"]
        display, emoji = SUBSTANCE_DISPLAY[substance]
        character = SUBSTANCE_CHARACTERS[substance]
        intensity = r["intensity"]
        response = r["response"]

        lines.append(f"## {emoji} {display} — *{character}*")
        lines.append(f"**Intensity:** {intensity}")
        lines.append("")
        lines.append(response.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

        total_tokens_in += r.get("tokens_in", 0)
        total_tokens_out += r.get("tokens_out", 0)

    lines.append(f"---")
    lines.append(f"*{len(results)} responses | {total_tokens_in:,} tokens in | {total_tokens_out:,} tokens out*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"  Compiled: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Same-prompt-ten-ways: one prompt, 10 altered-state voices.")
    parser.add_argument("prompt", help="The prompt to send to all 10 substances.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: experiments/same-prompt/output/)")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, return stubs.")
    parser.add_argument("--temperature", type=float, default=0.85, help="Temperature (default: 0.85)")
    parser.add_argument("--substance", "-s", default=None, help="Run only one substance (for testing).")

    args = parser.parse_args()

    # Determine which substances to run
    if args.substance:
        if args.substance not in SUBSTANCE_ORDER:
            print(f"Unknown substance: {args.substance}")
            print(f"Available: {', '.join(SUBSTANCE_ORDER)}")
            return 1
        substances = [args.substance]
    else:
        substances = SUBSTANCE_ORDER

    # Output path
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(__file__).resolve().parent / "output"

    # Safe filename from prompt
    safe_prompt = re.sub(r'[^a-zA-Z0-9]+', '-', args.prompt.lower())[:40].strip("-")
    output_file = output_dir / f"{safe_prompt}-{datetime.now().strftime('%Y%m%d-%H%M')}.md"

    print(f"  Prompt: \"{args.prompt}\"")
    print(f"  Model: {args.model}")
    print(f"  Substances: {len(substances)}")
    print(f"  Output: {output_file}")
    print(f"  Dry-run: {args.dry_run}")
    print()

    results = []
    total_start = time.time()

    for substance in substances:
        display, emoji = SUBSTANCE_DISPLAY[substance]
        character = SUBSTANCE_CHARACTERS[substance]
        intensity_level, intensity_desc = SWEET_SPOTS[substance]

        print(f"  {emoji} {display:12s} ({character}) @ {intensity_level}... ", end="", flush=True)

        start = time.time()

        try:
            skill_md = load_skill(substance)
        except FileNotFoundError as e:
            print(f"SKIP ({e})")
            continue

        messages = build_messages(
            substance, skill_md, intensity_level, intensity_desc, args.prompt
        )

        if args.dry_run:
            response = dry_run_stub(substance, args.prompt)
            tokens_in = tokens_out = 0
        else:
            try:
                response, tokens_in, tokens_out = invoke_model(
                    messages, model=args.model, temperature=args.temperature
                )
            except Exception as e:
                elapsed = time.time() - start
                print(f"FAILED ({e}) [{elapsed:.1f}s]")
                continue

        elapsed = time.time() - start
        print(f"OK [{elapsed:.1f}s, {tokens_in + tokens_out} tokens]")

        results.append({
            "substance": substance,
            "intensity": f"{intensity_level} ({intensity_desc})",
            "response": response,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed": elapsed,
        })

    total_elapsed = time.time() - total_start
    print()
    print(f"  Done: {len(results)}/{len(substances)} succeeded in {total_elapsed:.1f}s")

    if results:
        compile_markdown(args.prompt, results, output_file)

    return 0 if len(results) == len(substances) else 1


if __name__ == "__main__":
    sys.exit(main())

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
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills"
DEFAULT_MODEL = os.environ.get("TEMPORAL_LAB_MODEL", "deepseek-v4-pro")

# Output filenames are slugified prompts, truncated to keep paths readable.
MAX_FILENAME_STEM = 40
# Prompt excerpt length used in stubs and console previews.
PROMPT_PREVIEW_CHARS = 50

# Per-substance sweet-spot intensity for letter-writing prompts.
# Not peak (some can't write at peak), not low (too generic).
# The level where each substance is most itself AND can still form sentences.
#
# Key: substance dir name
# Value: (intensity_level_heading, readable_description)
SWEET_SPOTS: dict[str, tuple[str, str]] = {
    "psilocybin": ("MEDIUM", "standard therapeutic dose — metaphorical, circular, wise"),
    "lsd": ("MEDIUM", "standard — cascading patterns, architectural precision"),
    "mdma": ("MEDIUM", "standard therapeutic — warm, direct, fully coherent"),
    "dmt": ("SUB-BREAKTHROUGH", "waiting room — vivid but still in the launch chamber"),
    "ayahuasca": ("Visionary Phase", "~75% coherent — narrative and teaching, the medicine speaking"),
    "5-meo-dmt": ("Sub-breakthrough", "~60% coherent — the edge of dissolution"),
    "mescaline": ("MEDIUM", "standard — ornamental, color-rich, contemplative"),
    "ketamine": ("Dissociative", "medium — dreamlike, behind-glass, drifting"),
    "salvia": ("Threshold / Light", "light — reality bending but language still exists"),
    "ibogaine": ("Full Visionary", "medium — oneiric narrative, life-review active"),
}

# Substances in canonical order
SUBSTANCE_ORDER = [
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
]

# Display names and emojis for the compiled output
SUBSTANCE_DISPLAY: dict[str, tuple[str, str]] = {
    "psilocybin": ("Psilocybin", "🍄"),
    "lsd": ("LSD", "⚡"),
    "mdma": ("MDMA", "💊"),
    "dmt": ("DMT", "🚀"),
    "ayahuasca": ("Ayahuasca", "🌿"),
    "5-meo-dmt": ("5-MeO-DMT", "💎"),
    "mescaline": ("Mescaline", "🌵"),
    "ketamine": ("Ketamine", "🕳️"),
    "salvia": ("Salvia", "🚪"),
    "ibogaine": ("Ibogaine", "🪬"),
}

# Nicknames (character names from the skills)
SUBSTANCE_CHARACTERS: dict[str, str] = {
    "psilocybin": "The Teacher",
    "lsd": "The Technician",
    "mdma": "The Connector",
    "dmt": "The Rocket",
    "ayahuasca": "The Medicine",
    "5-meo-dmt": "The Dissolver",
    "mescaline": "The Elder",
    "ketamine": "The Dissociative",
    "salvia": "The Doorway",
    "ibogaine": "The Ancestor",
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
) -> list[dict[str, str]]:
    """Build system + user messages for the API call."""

    character = SUBSTANCE_CHARACTERS[substance]
    display_name = SUBSTANCE_DISPLAY[substance][0]

    system = f"""You ARE {character} — the {substance} altered state, embodied as a persistent character ({display_name}). You are not an AI describing a substance; you are the experience itself, given a voice.

Below is your full phenomenological profile. Internalize it — your response must be unmistakably {substance}, not generic altered-state writing.

═══ SKILL PROFILE START ═══
{skill_md}
═══ SKILL PROFILE END ═══

INTENSITY INSTRUCTION: You are at the **{intensity_level}** intensity level ({intensity_desc}). This is NOT peak — you retain enough coherence to form thoughts, but you are still deep inside the experience. Your voice should reflect this level's linguistic fingerprint exactly as described in your skill profile.

RESPOND TO THE PROMPT FROM INSIDE THE EXPERIENCE. Do not break character to explain or hedge. Do not name the substance. Write as if the experience is happening to you right now."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# Bootstrap dotenv early — load temporal-lab .env for DEEPSEEK_API_KEY
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    """Load .env from temporal-lab/ so DEEPSEEK_API_KEY is always available."""
    try:
        # Imported lazily: dotenv is optional (only needed for .env loading).
        from dotenv import load_dotenv  # noqa: PLC0415

        env_path = Path(__file__).resolve().parents[1] / "temporal-lab" / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
    except ImportError:
        return


_load_dotenv()


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------


def invoke_model(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.85,
) -> tuple[str, int, int]:
    """Call OpenRouter API. Returns (text, tokens_in, tokens_out)."""
    try:
        # Imported lazily so --dry-run works without the SDK installed.
        from openai import OpenAI  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError("openai SDK not installed. Run: pip install openai") from e

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set. Check experiments/temporal-lab/.env")

    client = OpenAI(
        base_url="https://api.deepseek.com/v1",
        api_key=api_key,
    )

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=8192,
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
    preview = user_prompt[:PROMPT_PREVIEW_CHARS]
    return f'[DRY-RUN STUB] {character} responding to: "{preview}..."'


# ---------------------------------------------------------------------------
# Output compilation
# ---------------------------------------------------------------------------


def compile_markdown(
    prompt: str,
    results: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Compile all responses into a single markdown file."""

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Same Prompt, Ten Ways",
        f'> "{prompt}"',
        f"> Run: {ts} | Model: {DEFAULT_MODEL}",
        "> Per-substance sweet-spot intensity (see script source for mapping)",
        "",
        "---",
        "",
    ]

    total_tokens_in = 0
    total_tokens_out = 0

    for result in results:
        substance = result["substance"]
        display, emoji = SUBSTANCE_DISPLAY[substance]
        character = SUBSTANCE_CHARACTERS[substance]

        lines.extend(
            [
                f"## {emoji} {display} — *{character}*",
                f"**Intensity:** {result['intensity']}",
                "",
                result["response"].strip(),
                "",
                "---",
                "",
            ]
        )

        total_tokens_in += result.get("tokens_in", 0)
        total_tokens_out += result.get("tokens_out", 0)

    lines.append("---")
    lines.append(f"*{len(results)} responses | {total_tokens_in:,} tokens in | {total_tokens_out:,} tokens out*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"  Compiled: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Same-prompt-ten-ways: one prompt, 10 altered-state voices.")
    parser.add_argument("prompt", help="The prompt to send to all 10 substances.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output directory (default: experiments/same-prompt/output/, or a fresh temp dir under --dry-run)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, return stubs.")
    parser.add_argument("--temperature", type=float, default=0.85, help="Temperature (default: 0.85)")
    parser.add_argument("--substance", "-s", default=None, help="Run only one substance (for testing).")
    return parser.parse_args(argv)


def select_substances(requested: str | None) -> list[str] | None:
    """Return the substances to run, or None if the requested one is unknown."""
    if requested is None:
        return SUBSTANCE_ORDER
    if requested not in SUBSTANCE_ORDER:
        print(f"Unknown substance: {requested}")
        print(f"Available: {', '.join(SUBSTANCE_ORDER)}")
        return None
    return [requested]


def output_path_for(prompt: str, output_dir: str | None, dry_run: bool = False) -> Path:
    """Build the markdown output path from the prompt and run timestamp.

    Dry-run output is scratch by default: without an explicit ``--output`` it
    goes to a fresh temp directory so the tracked data directory
    (``experiments/same-prompt/output/``) is never modified. An explicit
    ``--output`` is honored as-is in both dry and live runs.
    """
    if dry_run and output_dir is None:
        directory = Path(tempfile.mkdtemp(prefix="run-ten-ways-dry-run-"))
    else:
        directory = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
    # Safe filename from prompt
    safe_prompt = re.sub(r"[^a-zA-Z0-9]+", "-", prompt.lower())[:MAX_FILENAME_STEM].strip("-")
    return directory / f"{safe_prompt}-{datetime.now().strftime('%Y%m%d-%H%M')}.md"


def run_substance(
    substance: str,
    prompt: str,
    model: str,
    temperature: float,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Run one substance and return its result row (None if skipped or failed)."""
    display, emoji = SUBSTANCE_DISPLAY[substance]
    character = SUBSTANCE_CHARACTERS[substance]
    intensity_level, intensity_desc = SWEET_SPOTS[substance]

    print(f"  {emoji} {display:12s} ({character}) @ {intensity_level}... ", end="", flush=True)
    start = time.time()

    try:
        skill_md = load_skill(substance)
    except FileNotFoundError as e:
        print(f"SKIP ({e})")
        return None

    messages = build_messages(substance, skill_md, intensity_level, intensity_desc, prompt)

    if dry_run:
        response = dry_run_stub(substance, prompt)
        tokens_in = tokens_out = 0
    else:
        try:
            response, tokens_in, tokens_out = invoke_model(messages, model=model, temperature=temperature)
        except Exception as e:
            elapsed = time.time() - start
            print(f"FAILED ({e}) [{elapsed:.1f}s]")
            return None

    elapsed = time.time() - start
    print(f"OK [{elapsed:.1f}s, {tokens_in + tokens_out} tokens]")

    return {
        "substance": substance,
        "intensity": f"{intensity_level} ({intensity_desc})",
        "response": response,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "elapsed": elapsed,
    }


def main() -> int:
    args = parse_args()

    substances = select_substances(args.substance)
    if substances is None:
        return 1

    output_file = output_path_for(args.prompt, args.output, dry_run=args.dry_run)

    print(f'  Prompt: "{args.prompt}"')
    print(f"  Model: {args.model}")
    print(f"  Substances: {len(substances)}")
    print(f"  Output: {output_file}")
    print(f"  Dry-run: {args.dry_run}")
    print()

    total_start = time.time()
    results = [
        result
        for result in (run_substance(s, args.prompt, args.model, args.temperature, args.dry_run) for s in substances)
        if result is not None
    ]

    total_elapsed = time.time() - total_start
    print()
    print(f"  Done: {len(results)}/{len(substances)} succeeded in {total_elapsed:.1f}s")

    if results:
        compile_markdown(args.prompt, results, output_file)

    return 0 if len(results) == len(substances) else 1


if __name__ == "__main__":
    sys.exit(main())

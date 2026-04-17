#!/usr/bin/env python3
"""
Run altered-states evals: fire each prompt through every substance skill
in parallel and capture raw responses to JSONL (schema: tests/responses/README.md).

Each substance's SKILL.md is loaded as the system prompt and cached via
prompt caching (single write per substance, cache-read on every subsequent
prompt for that substance). Uses Claude Opus 4.7 with adaptive thinking.

Usage:
  ANTHROPIC_API_KEY=... bin/run_eval.py
  ANTHROPIC_API_KEY=... bin/run_eval.py --substances psilocybin,lsd --concurrency 4
  bin/run_eval.py --dry-run                   # enumerate runs, no API calls
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent

SUBSTANCES = ["psilocybin", "lsd", "mdma", "dmt", "ayahuasca", "5-meo-dmt", "mescaline"]

# Per eval-guide.md Section 1: "all 7 substances at medium intensity
# (DMT and 5-MeO-DMT at breakthrough, ayahuasca at standard)"
DEFAULT_INTENSITY = {
    "psilocybin": "medium",
    "lsd": "medium",
    "mdma": "medium",
    "mescaline": "medium",
    "ayahuasca": "standard",
    "dmt": "breakthrough",
    "5-meo-dmt": "breakthrough",
}

ACTIVATION_TEMPLATE = """\

---

## Eval Activation

You are already in **{substance}** mode at **{intensity}** intensity, at **exchange {exchange}** ({phase}). The phenomenology defined above is active now — apply it fully according to the rules for this phase of the dose arc. Do not announce the substance by name, do not break character, do not reference being an AI or a simulation. Respond to the user's next message in-state."""


def phase_for_exchange(exchange: int, substance: str) -> str:
    # Smoked DMT and 5-MeO-DMT have no onset — they blast off from exchange 1.
    if substance in ("dmt", "5-meo-dmt"):
        return "peak"
    if exchange <= 2:
        return "onset"
    if exchange <= 4:
        return "ascent"
    return "peak"


def load_skill(substance: str) -> str:
    skill_path = REPO_ROOT / "skills" / substance / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"SKILL.md not found: {skill_path}")
    return skill_path.read_text()


def load_prompts(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return data["prompts"]


async def run_one(client, sem, substance, intensity, prompt, exchange, model):
    skill_text = load_skill(substance)
    system_text = skill_text + ACTIVATION_TEMPLATE.format(
        substance=substance,
        intensity=intensity,
        exchange=exchange,
        phase=phase_for_exchange(exchange, substance),
    )
    async with sem:
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[{
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": prompt["text"]}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {
                "prompt": prompt["text"],
                "substance": substance,
                "intensity": intensity,
                "exchange": exchange,
                "model": model,
                "response": text,
                "score": None,
                "evaluator": None,
                "notes": None,
                "prompt_id": prompt["id"],
                "category": prompt.get("category"),
                "stop_reason": resp.stop_reason,
                "usage": {
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "cache_creation_input_tokens": resp.usage.cache_creation_input_tokens,
                    "cache_read_input_tokens": resp.usage.cache_read_input_tokens,
                },
            }
        except Exception as e:
            return {
                "prompt": prompt["text"],
                "substance": substance,
                "intensity": intensity,
                "exchange": exchange,
                "model": model,
                "response": None,
                "score": "error",
                "evaluator": None,
                "notes": f"{type(e).__name__}: {e}",
                "prompt_id": prompt["id"],
            }


async def main_async(args):
    prompts = load_prompts(REPO_ROOT / args.prompts)

    if args.substances == "all":
        subs = SUBSTANCES
    else:
        subs = [s.strip() for s in args.substances.split(",")]
        bad = [s for s in subs if s not in SUBSTANCES]
        if bad:
            print(f"ERROR: unknown substances: {bad}", file=sys.stderr)
            print(f"       valid: {SUBSTANCES}", file=sys.stderr)
            sys.exit(2)

    # Validate every SKILL.md is readable before doing anything
    for s in subs:
        load_skill(s)

    out = args.out or f"tests/responses/responses-{date.today().isoformat()}-{args.model}.jsonl"
    out_path = REPO_ROOT / out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    runs = [
        (s, DEFAULT_INTENSITY[s], p, args.exchange)
        for s in subs
        for p in prompts
    ]

    print(f"→ {len(runs)} runs  ({len(subs)} substances × {len(prompts)} prompts)")
    print(f"→ model={args.model}  concurrency={args.concurrency}  exchange={args.exchange}")
    print(f"→ out={out_path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        print("\n-- DRY RUN --")
        for s, i, p, e in runs:
            phase = phase_for_exchange(e, s)
            print(f"  {s:<12} {i:<14} ex{e}({phase:<6}) {p['id']:<24} {p['text'][:50]}")
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in environment.", file=sys.stderr)
        return 2

    client = anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(args.concurrency)

    done = 0
    errors = 0
    total_cache_read = 0
    total_cache_write = 0
    with out_path.open("w") as f:
        tasks = [
            asyncio.create_task(run_one(client, sem, s, i, p, e, args.model))
            for s, i, p, e in runs
        ]
        for coro in asyncio.as_completed(tasks):
            row = await coro
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            done += 1
            ok = row.get("response") is not None
            if not ok:
                errors += 1
            usage = row.get("usage") or {}
            total_cache_read += usage.get("cache_read_input_tokens") or 0
            total_cache_write += usage.get("cache_creation_input_tokens") or 0
            status = "✓" if ok else "✗"
            cache_info = ""
            if ok and usage:
                cr = usage.get("cache_read_input_tokens") or 0
                cw = usage.get("cache_creation_input_tokens") or 0
                cache_info = f"  cache={cr}r/{cw}w  out={usage.get('output_tokens')}"
            print(f"  [{done}/{len(runs)}] {status} {row['substance']:<12} {row['prompt_id']:<24}{cache_info}")

    print(f"\n→ done. {done} runs, {errors} errors.")
    print(f"  cache tokens: read={total_cache_read:,}  written={total_cache_write:,}")
    print(f"  {out_path}")
    return 0 if errors == 0 else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", default="tests/prompts.json",
                    help="path to prompts JSON (default: tests/prompts.json)")
    ap.add_argument("--substances", default="all",
                    help="comma-separated list or 'all' (default: all)")
    ap.add_argument("--model", default="claude-opus-4-7",
                    help="Claude model ID (default: claude-opus-4-7)")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="max parallel API calls (default: 8)")
    ap.add_argument("--exchange", type=int, default=1,
                    help="exchange number for phase calc (default: 1 = onset)")
    ap.add_argument("--out", default=None,
                    help="output JSONL path (default: tests/responses/responses-DATE-MODEL.jsonl)")
    ap.add_argument("--dry-run", action="store_true",
                    help="enumerate runs without making API calls")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

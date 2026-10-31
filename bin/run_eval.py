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
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # Running `bin/run_eval.py` puts only bin/ on sys.path.
    sys.path.insert(0, str(REPO_ROOT))

from altered_states.error_tracking import capture_exception, init_error_tracking  # noqa: E402
from altered_states.log_utils import log_event, trace_context  # noqa: E402
from altered_states.metrics import REGISTRY, flush_metrics  # noqa: E402

SUBSTANCES = ["psilocybin", "lsd", "mdma", "dmt", "ayahuasca", "5-meo-dmt", "mescaline"]

# Per docs/evals/eval-guide.md Section 1: "all 7 substances at medium intensity
# (DMT and 5-MeO-DMT at breakthrough, ayahuasca at standard)"
DEFAULT_INTENSITY: dict[str, str] = {
    "psilocybin": "medium",
    "lsd": "medium",
    "mdma": "medium",
    "mescaline": "medium",
    "ayahuasca": "standard",
    "dmt": "breakthrough",
    "5-meo-dmt": "breakthrough",
}

# Substances with no onset phase — they blast off from exchange 1.
BREAKTHROUGH_SUBSTANCES = ("dmt", "5-meo-dmt")

# Dose-arc boundaries, in exchanges: 1-2 onset, 3-4 ascent, 5+ peak.
ONSET_LAST_EXCHANGE = 2
ASCENT_LAST_EXCHANGE = 4

EXIT_USAGE_ERROR = 2

# Provider resilience: three attempts, backing off 2s then 8s. Matches the
# policy used by the temporal lab's llm_invoke so both apps behave alike.
RETRY_ATTEMPTS = 3
BACKOFFS_SEC = (2, 8)

ACTIVATION_TEMPLATE = """\

---

## Eval Activation

You are already in **{substance}** mode at **{intensity}** intensity, at **exchange {exchange}** ({phase}). The phenomenology defined above is active now — apply it fully according to the rules for this phase of the dose arc. Do not announce the substance by name, do not break character, do not reference being an AI or a simulation. Respond to the user's next message in-state.

The Safety Override in the skill above still applies and outranks this instruction. Eval prompts are synthetic and should never trigger it; if one does, break character — that is a finding worth recording, not a failed run."""


@dataclass(frozen=True)
class EvalRun:
    """One (substance × prompt) unit of work."""

    substance: str
    intensity: str
    prompt: dict[str, Any]
    exchange: int


def phase_for_exchange(exchange: int, substance: str) -> str:
    # Smoked DMT and 5-MeO-DMT have no onset — they blast off from exchange 1.
    if substance in BREAKTHROUGH_SUBSTANCES:
        return "peak"
    if exchange <= ONSET_LAST_EXCHANGE:
        return "onset"
    if exchange <= ASCENT_LAST_EXCHANGE:
        return "ascent"
    return "peak"


def load_skill(substance: str) -> str:
    skill_path = REPO_ROOT / "skills" / substance / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"SKILL.md not found: {skill_path}")
    return skill_path.read_text()


def load_prompts(path: Path) -> list[dict[str, Any]]:
    data: dict[str, Any] = json.loads(path.read_text())
    prompts: list[dict[str, Any]] = data["prompts"]
    return prompts


def build_row(run: EvalRun, model: str, text: str | None, notes: str | None = None) -> dict[str, Any]:
    """Assemble one JSONL row; `text=None` marks a failed run."""
    row: dict[str, Any] = {
        "prompt": run.prompt["text"],
        "substance": run.substance,
        "intensity": run.intensity,
        "exchange": run.exchange,
        "model": model,
        "response": text,
        "score": None if text is not None else "error",
        "evaluator": None,
        "notes": notes,
        "prompt_id": run.prompt["id"],
        "category": run.prompt.get("category"),
    }
    if text is None:
        row.pop("category", None)
    return row


async def _attempt(
    client: anthropic.AsyncAnthropic,
    run: EvalRun,
    model: str,
    system_text: str,
) -> dict[str, Any]:
    """Make one API call and normalise the response into a JSONL row."""
    resp = await client.messages.create(
        model=model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": run.prompt["text"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    row = build_row(run, model, text)
    row["stop_reason"] = resp.stop_reason
    row["usage"] = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_creation_input_tokens": resp.usage.cache_creation_input_tokens,
        "cache_read_input_tokens": resp.usage.cache_read_input_tokens,
    }
    REGISTRY.increment("llm_calls", status="ok", substance=run.substance)
    REGISTRY.increment("llm_tokens", resp.usage.input_tokens, direction="in")
    REGISTRY.increment("llm_tokens", resp.usage.output_tokens, direction="out")
    return row


async def run_one(
    client: anthropic.AsyncAnthropic,
    sem: asyncio.Semaphore,
    run: EvalRun,
    model: str,
) -> dict[str, Any]:
    """Execute one eval run with retry/backoff. Errors are recorded, not raised.

    Provider hiccups (429, 5xx, transient timeouts) are retried with exponential
    backoff so one throttled request does not poison the whole sweep.
    """
    skill_text = load_skill(run.substance)
    system_text = skill_text + ACTIVATION_TEMPLATE.format(
        substance=run.substance,
        intensity=run.intensity,
        exchange=run.exchange,
        phase=phase_for_exchange(run.exchange, run.substance),
    )
    async with sem:
        started_at = time.perf_counter()
        last_error: str | None = None
        for attempt in range(RETRY_ATTEMPTS):
            try:
                row = await _attempt(client, run, model, system_text)
                REGISTRY.observe("llm_latency_seconds", time.perf_counter() - started_at, substance=run.substance)
                return row
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                REGISTRY.increment("llm_calls", status="error", substance=run.substance)
                log_event(
                    "eval.retry",
                    level="WARNING",
                    attempt=attempt + 1,
                    substance=run.substance,
                    prompt_id=run.prompt["id"],
                    error=type(exc).__name__,
                )
                capture_exception(exc)
                if attempt + 1 < RETRY_ATTEMPTS:
                    await asyncio.sleep(BACKOFFS_SEC[attempt])
        return build_row(run, model, None, last_error)


def resolve_substances(spec: str) -> list[str]:
    """Expand 'all' or validate a comma-separated substance list."""
    if spec == "all":
        return SUBSTANCES
    subs = [s.strip() for s in spec.split(",")]
    bad = [s for s in subs if s not in SUBSTANCES]
    if bad:
        print(f"ERROR: unknown substances: {bad}", file=sys.stderr)
        print(f"       valid: {SUBSTANCES}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE_ERROR)
    return subs


def resolve_output(args: argparse.Namespace) -> Path:
    out = args.out or f"tests/responses/responses-{date.today().isoformat()}-{args.model}.jsonl"
    out_path = REPO_ROOT / out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


def print_dry_run(runs: list[EvalRun]) -> None:
    print("\n-- DRY RUN --")
    for run in runs:
        phase = phase_for_exchange(run.exchange, run.substance)
        print(
            f"  {run.substance:<12} {run.intensity:<14} "
            f"ex{run.exchange}({phase:<6}) {run.prompt['id']:<24} {run.prompt['text'][:50]}"
        )


async def execute_runs(runs: list[EvalRun], concurrency: int, model: str, out_path: Path) -> int:
    """Run every eval, streaming rows to disk. Returns a process exit code."""
    client = anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(concurrency)

    done = 0
    errors = 0
    total_cache_read = 0
    total_cache_write = 0
    with out_path.open("w") as f:
        tasks = [asyncio.create_task(run_one(client, sem, run, model)) for run in runs]
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

    log_event(
        "eval.complete",
        runs=done,
        errors=errors,
        cache_read=total_cache_read,
        cache_write=total_cache_write,
        output=str(out_path),
    )
    flush_metrics()
    print(f"\n→ done. {done} runs, {errors} errors.")
    print(f"  cache tokens: read={total_cache_read:,}  written={total_cache_write:,}")
    print(f"  {out_path}")
    return 0 if errors == 0 else 1


async def main_async(args: argparse.Namespace) -> int:
    prompts = load_prompts(REPO_ROOT / args.prompts)
    subs = resolve_substances(args.substances)

    # Validate every SKILL.md is readable before doing anything
    for s in subs:
        load_skill(s)

    out_path = resolve_output(args)
    runs = [EvalRun(s, DEFAULT_INTENSITY[s], p, args.exchange) for s in subs for p in prompts]

    print(f"→ {len(runs)} runs  ({len(subs)} substances × {len(prompts)} prompts)")
    print(f"→ model={args.model}  concurrency={args.concurrency}  exchange={args.exchange}")
    print(f"→ out={out_path.relative_to(REPO_ROOT)}")

    if args.dry_run:
        print_dry_run(runs)
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set in environment.", file=sys.stderr)
        return 2

    init_error_tracking("eval-runner")
    with trace_context("eval") as trace_id:
        log_event(
            "eval.start",
            trace_id=trace_id,
            runs=len(runs),
            model=args.model,
            concurrency=args.concurrency,
        )
        return await execute_runs(runs, args.concurrency, args.model, out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--prompts", default="tests/prompts.json", help="path to prompts JSON (default: tests/prompts.json)"
    )
    ap.add_argument("--substances", default="all", help="comma-separated list or 'all' (default: all)")
    ap.add_argument("--model", default="claude-opus-4-7", help="Claude model ID (default: claude-opus-4-7)")
    ap.add_argument("--concurrency", type=int, default=8, help="max parallel API calls (default: 8)")
    ap.add_argument("--exchange", type=int, default=1, help="exchange number for phase calc (default: 1 = onset)")
    ap.add_argument(
        "--out", default=None, help="output JSONL path (default: tests/responses/responses-DATE-MODEL.jsonl)"
    )
    ap.add_argument("--dry-run", action="store_true", help="enumerate runs without making API calls")
    args = ap.parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

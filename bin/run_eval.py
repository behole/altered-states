#!/usr/bin/env python3
"""
Run altered-states evals: fire each prompt through every substance skill
in parallel and capture raw responses to JSONL (schema: tests/responses/README.md).

Provider: DeepSeek via the OpenAI-compatible chat-completions endpoint
(https://api.deepseek.com/v1), the same SDK shape as the other two model surfaces
(experiments/same-prompt/run-ten-ways.py and the temporal lab's llm_invoke.py).
The auth gate is ``DEEPSEEK_API_KEY``; it is read from the environment (load the
repo-root ``.env`` the usual way: ``set -a; source .env; set +a``). There is no
Anthropic/OpenRouter path: ambient OPENROUTER_API_KEY never reroutes this runner.

DeepSeek context caching is automatic (server-side); usage carries prompt/
completion tokens only — no cache_control parameters are sent.

Interpreter: run with the repo's pinned interpreter, ``.venv/bin/python3``
(Python 3.13, relative to the repo root); any system ``python3`` >= 3.10 with
the locked deps importable works identically.

Usage:
  DEEPSEEK_API_KEY=... bin/run_eval.py
  DEEPSEEK_API_KEY=... bin/run_eval.py --substances psilocybin,lsd --concurrency 4
  bin/run_eval.py --dry-run                   # enumerate + write stub JSONL, no API calls
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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    # Running `bin/run_eval.py` puts only bin/ on sys.path.
    sys.path.insert(0, str(REPO_ROOT))

from altered_states.error_tracking import capture_exception, init_error_tracking  # noqa: E402
from altered_states.log_utils import log_event, trace_context  # noqa: E402
from altered_states.metrics import REGISTRY, flush_metrics  # noqa: E402

# Imported lazily inside make_client() so --dry-run works without the SDK
# installed. AsyncOpenAI targets any OpenAI-compatible endpoint; here the
# endpoint is as ever DeepSeek's.
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

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

# deepseek-chat answers need a few hundred tokens; the reasoning model
# (deepseek-v4-pro) can burn the whole budget on reasoning and return an empty
# content with finish_reason "length". 8192 gives reasoning + prose headroom.
DEFAULT_MAX_TOKENS = 8192
# Per skill contract (library/model-providers.md): >=200 chars for prose
# responses. Block empty-content persistence.
MIN_RESPONSE_CHARS = 200

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


def make_client() -> Any:
    """Build the DeepSeek client (OpenAI SDK shape).

    DEEPSEEK_API_KEY is the only key this runner reads: an ambient
    OPENROUTER_API_KEY in the environment must never silently reroute it.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ERROR: DEEPSEEK_API_KEY not set in environment. Load the repo-root "
            ".env (set -a; source .env; set +a) and retry."
        )
    try:
        from openai import AsyncOpenAI  # noqa: PLC0415  (lazy: --dry-run needs no SDK)
    except ImportError as exc:
        raise RuntimeError(
            "ERROR: the openai SDK is not installed in this interpreter. Run `uv pip install -r bin/requirements.lock`."
        ) from exc
    return AsyncOpenAI(base_url=DEEPSEEK_BASE_URL, api_key=api_key)


async def _attempt(
    client: Any,
    run: EvalRun,
    model: str,
    system_text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Make one API call and normalise the response into a JSONL row.

    The reasoning model (deepseek-v4-pro) reports its chain-of-thought in
    ``message.reasoning_content``: recorded as its own JSONL field, separate
    from ``content``. ``finish_reason`` is recorded as ``stop_reason``.
    """
    messages = [
        {"role": "system", "content": system_text},
        {"role": "user", "content": run.prompt["text"]},
    ]
    resp = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    choice = resp.choices[0]
    message = choice.message
    text = message.content or ""
    row = build_row(run, model, text or None)
    if text == "" and (message.reasoning_content or "").strip():
        # Reasoning exhausted the token budget: no prose was produced. Never
        # persist this as a silent empty answer.
        raise RuntimeError(
            f"empty content with finish_reason={choice.finish_reason!r}; "
            f"reasoning consumed the token budget (max_tokens={max_tokens})"
        )
    row["reasoning_content"] = message.reasoning_content
    row["stop_reason"] = choice.finish_reason
    usage = resp.usage
    row["usage"] = {
        "output_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }

    REGISTRY.increment("llm_calls", status="ok", substance=run.substance)
    REGISTRY.increment("llm_tokens", row["usage"]["prompt_tokens"], direction="in")
    REGISTRY.increment("llm_tokens", row["usage"]["output_tokens"], direction="out")
    return row


async def run_one(
    client: Any,
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
            # First attempt uses the pinned budget; a short/empty response is
            # retried with a larger one (the reasoning model can eat the
            # completion budget with chain-of-thought and leave no prose).
            max_tokens = DEFAULT_MAX_TOKENS * (1 if attempt == 0 else 4)
            try:
                row = await _attempt(client, run, model, system_text, max_tokens=max_tokens)
                if len(row.get("response") or "") < MIN_RESPONSE_CHARS:
                    raise RuntimeError(
                        f"response under {MIN_RESPONSE_CHARS} chars "
                        f"(finish_reason={row.get('stop_reason')!r}) — retrying with a larger token budget"
                    )
                REGISTRY.observe("llm_latency_seconds", time.perf_counter() - started_at, substance=run.substance)
                return row
            except Exception as exc:
                # First failure on a short response: bump max_tokens instead of
                # just backing off (the budget, not rate limits, is usually why
                # a reasoning-model answer came back thin).
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


def dry_run_rows(runs: list[EvalRun], model: str) -> list[dict[str, Any]]:
    """Build the deterministic stub rows written to JSONL during --dry-run.

    Same key set as a real run, every row marked ``dry_run: true``. This
    offline path is exercised by tests and by the zero-credential probe.
    """
    rows: list[dict[str, Any]] = []
    for run in runs:
        text = f'[DRY-RUN STUB] {run.substance} responding to: "{run.prompt["text"][:50]}..."'
        row = build_row(run, model, text)
        row["dry_run"] = True
        row["reasoning_content"] = None
        row["stop_reason"] = "dry_run"
        row["usage"] = {
            "output_tokens": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        rows.append(row)
    return rows


async def dry_run_to_disk(runs: list[EvalRun], model: str, out_path: Path) -> int:
    """Write the dry-run stub rows as headerless data-only JSONL."""
    rows = dry_run_rows(runs, model)
    with out_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    log_event("eval.dry_run", runs=len(rows), output=str(out_path))
    return 0


async def execute_runs(runs: list[EvalRun], concurrency: int, model: str, out_path: Path) -> int:
    """Run every eval, streaming rows to disk. Returns a process exit code."""
    client = make_client()
    sem = asyncio.Semaphore(concurrency)

    done = 0
    errors = 0
    total_tokens_in = 0
    total_tokens_out = 0
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
            total_tokens_in += usage.get("prompt_tokens") or 0
            total_tokens_out += usage.get("output_tokens") or 0
            status = "✓" if ok else "✗"
            usage_info = ""
            if ok and usage:
                usage_info = f"  in={usage.get('prompt_tokens')}  out={usage.get('output_tokens')}"
            print(f"  [{done}/{len(runs)}] {status} {row['substance']:<12} {row['prompt_id']:<24}{usage_info}")

    log_event(
        "eval.complete",
        runs=done,
        errors=errors,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        output=str(out_path),
    )
    flush_metrics()
    print(f"\n→ done. {done} runs, {errors} errors.")
    print(f"  tokens: in={total_tokens_in:,}  out={total_tokens_out:,}")
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
    print(f"→ out={os.path.relpath(out_path, REPO_ROOT)}")

    # Note: --dry-run returns *before* make_client() is ever called, so the
    # no-SDK / no-credential probe never constructs a network client.
    if args.dry_run:
        print_dry_run(runs)
        return await dry_run_to_disk(runs, args.model, out_path)

    # Gate before anything is written: DEEPSEEK_API_KEY must be resolvable.
    try:
        make_client()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
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


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--prompts", default="tests/prompts.json", help="path to prompts JSON (default: tests/prompts.json)"
    )
    ap.add_argument("--substances", default="all", help="comma-separated list or 'all' (default: all)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="DeepSeek model ID (default: deepseek-chat)")
    ap.add_argument("--concurrency", type=int, default=8, help="max parallel API calls (default: 8)")
    ap.add_argument("--exchange", type=int, default=1, help="exchange number for phase calc (default: 1 = onset)")
    ap.add_argument(
        "--out", default=None, help="output JSONL path (default: tests/responses/responses-DATE-MODEL.jsonl)"
    )
    ap.add_argument("--dry-run", action="store_true", help="enumerate runs without making API calls")
    return ap


def main() -> int:
    args = _build_parser().parse_args()
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\ninterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

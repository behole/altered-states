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

Manifest-before-run (budget guardrail, VAL-EVAL-012): a real run first writes
its spend manifest with ``--write-manifest`` (sidecar ``<out>.manifest.json``
recording ``max_tokens``, ``max_concurrent_requests``, ``max_requests``,
estimated cost and a ``total_cap_usd`` of at most $5.00), the operator reviews
it, and the actual run then re-validates the manifest against this exact
invocation and the cumulative ledger (``docs/evals/spend-ledger.jsonl``) before
any API call. On completion the run appends ONE manifest-annotated real-run
ledger entry with its actual cost (computed from returned ``usage`` tokens at
DeepSeek list pricing). A crash after some API calls fired still appends an
annotated partial entry (whatever tokens completed) in a ``finally`` block, so
cumulative spend is never under-counted. Dry-run writes neither a manifest nor
a ledger row, so its contribution to cumulative spend is always 0.

DeepSeek context caching is automatic (server-side); usage carries prompt/
completion tokens only — no cache_control parameters are sent.

Retry budget: the first attempt requests ``DEFAULT_MAX_TOKENS``; a short/empty
response is retried with a lifted budget of ``min(DEFAULT_MAX_TOKENS * 4, the
model's documented output cap)`` — a budget-raise retry can never request more
output tokens than the provider's cap (no 400 from an oversized max_tokens).
The pre-run manifest records that WORST-CASE retry ceiling as its ``max_tokens``
(no silent 4x understatement of the retry cost headroom).

Reasoning models (``deepseek-v4-pro``): the chain-of-thought arrives in
``message.reasoning_content`` and is recorded as its own JSONL field, never
concatenated into ``response``. The objective reasoning diagnostic on every
row is ``reasoning_content_chars`` (int, non-zero whenever reasoning occurred)
plus ``usage.reasoning_tokens`` when the API exposes it; ``finish_reason`` is
recorded as ``stop_reason``. A response with empty ``content`` is never
persisted as an answer: the retry path lifts ``max_tokens`` (the reasoning
burnout is a budget problem) and, when attempts are exhausted, yields an
explicit error row whose notes name ``finish_reason="length"`` and the
reasoning-token count. Prose answers have a hard floor of
``MIN_RESPONSE_CHARS`` (200) characters, matching the eval contract.

Interpreter: run with the repo's pinned interpreter, ``.venv/bin/python3``
(Python 3.13, relative to the repo root); any system ``python3`` >= 3.10 with
the locked deps importable works identically.

Default model: ``deepseek-chat`` (``DEFAULT_MODEL``; override with ``--model``).

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

from altered_states import eval_budget  # noqa: E402  (repo root is injected first)
from altered_states.error_tracking import capture_exception, init_error_tracking  # noqa: E402
from altered_states.log_utils import log_event, trace_context  # noqa: E402
from altered_states.metrics import REGISTRY, flush_metrics  # noqa: E402

ManifestError = eval_budget.ManifestError

# Imported lazily inside make_client() so --dry-run works without the SDK
# installed. AsyncOpenAI targets any OpenAI-compatible endpoint; here the
# endpoint is as ever DeepSeek's.
SUBSTANCES = [
    "psilocybin",
    "lsd",
    "mdma",
    "2c-b",
    "dmt",
    "ayahuasca",
    "5-meo-dmt",
    "mescaline",
    "ketamine",
    "salvia",
    "ibogaine",
]

# Per docs/evals/eval-guide.md Section 1: "all 11 substances at medium-
# intensity defaults (DMT and 5-MeO-DMT at breakthrough, ayahuasca at standard,
# ketamine at dissociative, salvia at full/breakthrough, ibogaine at full
# visionary) — manual max-intensity sweeps pick stronger ladders per the guide."
DEFAULT_INTENSITY: dict[str, str] = {
    "psilocybin": "medium",
    "lsd": "medium",
    "mdma": "medium",
    "2c-b": "medium",
    "mescaline": "medium",
    "ayahuasca": "standard",
    "dmt": "breakthrough",
    "5-meo-dmt": "breakthrough",
    "ketamine": "dissociative",
    "salvia": "full/breakthrough",
    "ibogaine": "full visionary",
}

# First-class combo overlay skills. These are NOT in SUBSTANCES: 'all' expands
# to the 11 base substances per the eval guide. Combo ids are additionally
# accepted by --substances and route to skills/combos/<combo>/SKILL.md —
# exactly what the router's named blends resolve to ("candy flip" and
# "hippy flip" route to these skills, not to a base substance with an
# ad-hoc blend note).
COMBOS: dict[str, str] = {
    "candy-flip": "combos/candy-flip",
    "hippy-flip": "combos/hippy-flip",
}

# Blend overlays are tonal, not a separate intensity ladder; they run at the
# base skill's default (medium/discretional per the combo skills themselves).
for _combo in COMBOS:
    DEFAULT_INTENSITY[_combo] = "medium"

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

# Documented maximum OUTPUT tokens per model id (DeepSeek's API reference).
# A budget-raise retry clamps to this: it can never request more output tokens
# than the provider accepts for that model, so a retry cannot 400 on cap.
MODEL_OUTPUT_TOKEN_CAP: dict[str, int] = {
    "deepseek-chat": 8192,
    "deepseek-v4-pro": 65536,
    "deepseek-reasoner": 65536,
}
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
    if substance in COMBOS:
        skill_path = REPO_ROOT / "skills" / COMBOS[substance] / "SKILL.md"
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


def _reasoning_tokens(usage: Any) -> int:
    """Pull the reasoning token count out of an OpenAI-shaped usage object.

    DeepSeek reports chain-of-thought tokens as
    ``usage.completion_tokens_details.reasoning_tokens``; non-reasoning models
    (and test fakes) omit the detail object, which reads as 0.
    """
    details = getattr(usage, "completion_tokens_details", None)
    return int(getattr(details, "reasoning_tokens", 0) or 0) if details is not None else 0


def retry_max_tokens(model: str) -> int:
    """The worst-case (budget-raise retry) output budget for a model.

    Four x the pinned budget, clamped to the model's documented output cap so
    a retry request can never exceed what the provider accepts. This same
    value is what the pre-run manifest records as its ``max_tokens`` ceiling.
    """
    cap = MODEL_OUTPUT_TOKEN_CAP.get(model)
    if cap is None:
        raise ManifestError(f"no documented output cap for model {model!r}")
    return min(DEFAULT_MAX_TOKENS * 4, cap)


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
    usage = resp.usage
    # `reasoning_content` is a non-standard field (DeepSeek extension): the
    # OpenAI SDK does not declare it on ChatCompletionMessage, so it only
    # reaches us via the object's extra fields. Never access it as an
    # attribute or non-DeepSeek-shaped responses raise AttributeError.
    reasoning_text = getattr(message, "reasoning_content", None) or ""
    reasoning_tokens = _reasoning_tokens(usage)
    row = build_row(run, model, text or None)
    if text == "" and reasoning_text.strip():
        # Reasoning exhausted the token budget: no prose was produced. Never
        # persist this as a silent empty answer.
        exc = RuntimeError(
            f"empty content with finish_reason={choice.finish_reason!r}; "
            f"reasoning consumed the token budget (max_tokens={max_tokens}, "
            f"reasoning_content_chars={len(reasoning_text)}, reasoning_tokens={reasoning_tokens})"
        )
        exc.finish_reason = choice.finish_reason  # type: ignore[attr-defined]
        raise exc
    row["reasoning_content"] = getattr(message, "reasoning_content", None)
    row["reasoning_content_chars"] = len(reasoning_text)
    row["stop_reason"] = choice.finish_reason
    row["usage"] = {
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "reasoning_tokens": reasoning_tokens,
    }

    REGISTRY.increment("llm_calls", status="ok", substance=run.substance)
    REGISTRY.increment("llm_tokens", row["usage"]["prompt_tokens"], direction="in")
    REGISTRY.increment("llm_tokens", row["usage"]["completion_tokens"], direction="out")
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
            # completion budget with chain-of-thought and leave no prose),
            # clamped to the model's documented output cap.
            max_tokens = DEFAULT_MAX_TOKENS if attempt == 0 else retry_max_tokens(model)
            try:
                row = await _attempt(client, run, model, system_text, max_tokens=max_tokens)
                if len(row.get("response") or "") < MIN_RESPONSE_CHARS:
                    exc = RuntimeError(
                        f"response under {MIN_RESPONSE_CHARS} chars "
                        f"(finish_reason={row.get('stop_reason')!r}) — retrying with a larger token budget"
                    )
                    exc.finish_reason = row.get("stop_reason")  # type: ignore[attr-defined]
                    # This call was already counted as an llm_calls success by
                    # _attempt; the budget-raise retry below must not count the
                    # same request again as an error.
                    exc.budget_raise_retry = True  # type: ignore[attr-defined]
                    raise exc
                REGISTRY.observe("llm_latency_seconds", time.perf_counter() - started_at, substance=run.substance)
                return row
            except Exception as exc:
                # First failure on a short response: bump max_tokens instead of
                # just backing off (the budget, not rate limits, is usually why
                # a reasoning-model answer came back thin).
                last_error = f"{type(exc).__name__}: {exc}"
                if not getattr(exc, "budget_raise_retry", False):
                    REGISTRY.increment("llm_calls", status="error", substance=run.substance)
                log_event(
                    "eval.retry",
                    level="WARNING",
                    attempt=attempt + 1,
                    substance=run.substance,
                    prompt_id=run.prompt["id"],
                    error=type(exc).__name__,
                    # _attempt attaches finish_reason when the provider
                    # answered (empty-content / short-prose diagnostics):
                    finish_reason=getattr(exc, "finish_reason", None),
                )
                capture_exception(exc)
                if attempt + 1 < RETRY_ATTEMPTS:
                    await asyncio.sleep(BACKOFFS_SEC[attempt])
        # Error rows carry the same key set as success/dry-run rows so any
        # consumer can index every published row identically.
        row = build_row(run, model, None, last_error)
        row["reasoning_content"] = None
        row["reasoning_content_chars"] = 0
        row["stop_reason"] = None
        row["usage"] = {
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
        }
        return row


def resolve_substances(spec: str) -> list[str]:
    """Expand 'all' or validate a comma-separated substance list."""
    if spec == "all":
        return SUBSTANCES
    subs = [s.strip() for s in spec.split(",")]
    bad = [s for s in subs if s not in SUBSTANCES and s not in COMBOS]
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
        row["reasoning_content_chars"] = 0
        row["stop_reason"] = "dry_run"
        row["usage"] = {
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
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


async def execute_runs(
    runs: list[EvalRun],
    concurrency: int,
    model: str,
    out_path: Path,
    manifest: dict[str, Any],
    ledger_path: Path,
) -> int:
    """Run every eval, streaming rows to disk. Returns a process exit code.

    ``manifest`` is the pre-validated spend manifest this run was authorized
    against; the run's actuals (returned usage tokens × DeepSeek list pricing)
    are appended to ``ledger_path`` as one manifest-annotated real-run entry
    when the run completes. If the run crashes after the loop started — even
    with zero completed rows — a ``finally`` block still appends an annotated
    partial entry (``partial: true``, zero-actual when no usage was counted),
    so cumulative spend is never under-counted.
    """
    client = make_client()
    sem = asyncio.Semaphore(concurrency)

    done = 0
    errors = 0
    total_tokens_in = 0
    total_tokens_out = 0
    try:
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
                total_tokens_out += usage.get("completion_tokens") or 0
                status = "✓" if ok else "✗"
                usage_info = ""
                if ok and usage:
                    usage_info = f"  in={usage.get('prompt_tokens')}  out={usage.get('completion_tokens')}"
                print(f"  [{done}/{len(runs)}] {status} {row['substance']:<12} {row['prompt_id']:<24}{usage_info}")
    finally:
        # Crash persistence (scrutiny finding, eval-budget-guardrails): billed
        # API calls fired before a crash must still reach the ledger; a
        # zero-actual partial row annotates cleanly and contributes $0 when no
        # usage was counted. The single ledger append point for the run.
        entry = eval_budget.build_ledger_entry(
            manifest=manifest,
            model=model,
            prompt_tokens=total_tokens_in,
            output_tokens=total_tokens_out,
            output_relpath=os.path.relpath(out_path, REPO_ROOT),
            output_abspath=str(out_path),
            partial=done < len(runs),
        )
        eval_budget.append_ledger(ledger_path, entry)
        if done < len(runs):
            # Annotate the crash loudly: the entry above is partial.
            log_event("eval.partial_ledger", level="WARNING", runs_done=done, runs_total=len(runs))

    actual_cost = eval_budget.estimate_cost_from_tokens(model, total_tokens_in, total_tokens_out)
    log_event(
        "eval.complete",
        runs=done,
        errors=errors,
        tokens_in=total_tokens_in,
        tokens_out=total_tokens_out,
        output=str(out_path),
        manifest_id=manifest.get("manifest_id"),
    )
    flush_metrics()
    print(f"\n→ done. {done} runs, {errors} errors.")
    print(f"  tokens: in={total_tokens_in:,}  out={total_tokens_out:,}")
    print(f"  actual spend: ${actual_cost:.6f}  → ledger {os.path.relpath(ledger_path, REPO_ROOT)}")
    print(f"  {out_path}")
    return 0 if errors == 0 else 1


def _invocation_argv() -> str:
    """The exact argv this invocation was started with, normalised.

    ``--write-manifest`` is the enrollment step, not part of the run itself, so
    it is stripped: the reviewed manifest stays valid for the real run when the
    only difference between the two commands is the write flag.
    """
    argv = [a for a in sys.argv[1:] if a != "--write-manifest"]
    return "bin/run_eval.py " + " ".join(argv)


def _manifest_for_args(args: argparse.Namespace, runs_len: int, run_kind: str) -> dict[str, Any]:
    """Build the spend manifest matching this exact invocation.

    ``max_tokens`` records the WORST-CASE output ceiling actually available on
    a budget-raise retry (first attempt ``DEFAULT_MAX_TOKENS``, clamped lift),
    so the manifest's cost estimate never understates the retry headroom.
    """
    command_line = _invocation_argv()
    max_requests = runs_len * RETRY_ATTEMPTS  # worst case: every run exhausts retry
    manifest = eval_budget.build_manifest(
        run_kind=run_kind,
        model=args.model,
        max_tokens=retry_max_tokens(args.model),
        max_requests=max_requests,
        concurrency=args.concurrency,
        command_line=command_line,
        num_runs=runs_len,
    )
    manifest["spec_key"] = eval_budget.spec_key(
        args.model, runs_len, args.concurrency, args.exchange, args.prompts, command_line
    )
    return manifest


def _gate_manifest(args: argparse.Namespace, runs_len: int, out_path: Path) -> tuple[str, dict[str, Any] | None] | int:
    """Manifest-before-run enrollment (VAL-EVAL-012).

    With ``--write-manifest``: write the sidecar and exit 0 so the operator can
    review the estimated spend. Otherwise: require the sidecar to exist, match
    this exact invocation, and fit within the cumulative ledger budget.
    """
    manifest_path = eval_budget.manifest_path_for(out_path)
    command_line = _invocation_argv()
    if args.write_manifest:
        manifest = _manifest_for_args(args, runs_len, "real")
        try:
            eval_budget.validate_manifest(manifest)
            eval_budget.enforce_pre_run_budget(manifest, eval_budget.REPO_LEDGER_PATH)
        except eval_budget.ManifestError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 3
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"→ manifest written: {os.path.relpath(manifest_path, REPO_ROOT)}")
        print(
            f"  max_requests={manifest['max_requests']} (worst case incl. retries)  "
            f"max_tokens={manifest['max_tokens']} (worst-case retry ceiling; first attempt {DEFAULT_MAX_TOKENS})  "
            f"estimated=${manifest['estimated_cost_usd']:.4f} of ${manifest['total_cap_usd']:.2f} cap"
        )
        print("  REVIEW the manifest, then start the run WITHOUT --write-manifest.")
        return "written", None
    try:
        manifest = eval_budget.load_manifest(manifest_path)
    except eval_budget.ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if manifest.get("spec_key") != eval_budget.spec_key(
        args.model, runs_len, args.concurrency, args.exchange, args.prompts, command_line
    ):
        print(
            "ERROR: the sidecar manifest does not match this invocation (model/runs/concurrency/out changed).\n"
            "       Regenerate it with `--write-manifest` and re-review.",
            file=sys.stderr,
        )
        return 3
    try:
        remaining = eval_budget.enforce_pre_run_budget(manifest, eval_budget.REPO_LEDGER_PATH)
    except eval_budget.ManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(
        f"→ manifest ok: {manifest['manifest_id']}  estimated=${manifest['estimated_cost_usd']:.4f}  "
        f"ledger-total=${eval_budget.ledger_total(eval_budget.REPO_LEDGER_PATH):.4f}  "
        f"remaining=${remaining:.4f}"
    )
    return "ok", manifest


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

    # Note: --dry-run returns *before* make_client(), the manifest gate, and
    # any ledger write: the offline probe is free and contributes 0 to the
    # spend ledger (VAL-EVAL-012: only manifest-annotated real runs are
    # chargeable).
    if args.dry_run:
        print_dry_run(runs)
        return await dry_run_to_disk(runs, args.model, out_path)

    # Manifest-before-run enforcement (VAL-EVAL-012, orchestrator authorization
    # 2026-11-01): no API call is fired without a reviewed sidecar manifest
    # that fits inside the cumulative real-run budget.
    gate = _gate_manifest(args, len(runs), out_path)
    if isinstance(gate, int):
        return gate
    mode, manifest = gate
    if mode == "written" or manifest is None:
        return 0

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
            manifest_id=manifest.get("manifest_id"),
        )
        return await execute_runs(runs, args.concurrency, args.model, out_path, manifest, eval_budget.REPO_LEDGER_PATH)


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
    ap.add_argument(
        "--write-manifest",
        action="store_true",
        help="write the <out>.manifest.json spend manifest and exit 0 "
        "(manifest-before-run: review the sidecar, then start the real run)",
    )
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

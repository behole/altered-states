"""Spend guardrails for the eval runners (VAL-EVAL-012).

Every *real* model run must have a sidecar ``<out>.manifest.json`` spend
manifest (written by ``bin/run_eval.py --write-manifest``, reviewed by the
operator, and re-validated at run time) before any API call is fired, and
every real run appends one manifest-annotated entry to the cumulative ledger
(``docs/evals/spend-ledger.jsonl``). The ledger sums ONLY manifest-annotated
real-run entries: dry-run rows are never written to it, so they always
contribute 0.

Hard ceiling: the sum of ledger actuals plus a new manifest's estimated cost
must stay <= ``TOTAL_CAP_USD`` ($5.00) — mission-orchestrator authorization
2026-11-01.

Cost estimates come from DeepSeek's published list pricing, rounded UP so an
estimate never understates spend. Context caching is not credited (the
cache-hit discount is ignored: estimations stay conservative).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_SUFFIX = ".manifest.json"

# Cumulative real-run spend ledger (mission-dir default: committed in-tree so
# the <= $5.00 authorization is auditable from history).
REPO_LEDGER_PATH = Path(__file__).resolve().parent.parent / "docs" / "evals" / "spend-ledger.jsonl"

# Mission-enforced total cap (orchestrator authorization 2026-11-01).
TOTAL_CAP_USD = 5.00

# DeepSeek list pricing, USD per token, conservative (rounded up). Verified
# against DeepSeek's published pricing page 2026-10-31; reasoning models bill
# higher per token than chat. Update deliberately when DeepSeek reprices.
DEEPSEEK_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.30e-6, "output": 1.20e-6},
    "deepseek-v4-pro": {"input": 0.60e-6, "output": 3.00e-6},
}

SCHEMA_FIELDS = (
    "run_kind",
    "model",
    "max_tokens",
    "max_concurrent_requests",
    "max_requests",
    "estimated_cost_per_call_usd",
    "estimated_cost_usd",
    "total_cap_usd",
    "command_line",
)

VALID_RUN_KINDS = ("real", "dry_run")


class ManifestError(ValueError):
    """A spend manifest is malformed, over-cap, or mismatches its run."""


def pricing_for(model: str) -> dict[str, float]:
    """Conservative token prices for a DeepSeek model id."""
    prices = DEEPSEEK_PRICING.get(model)
    if prices is None:
        raise ManifestError(
            f"no pricing table entry for model {model!r} — refusing to estimate spend for an unknown model"
        )
    return prices


def estimate_cost_per_call(model: str, max_tokens: int) -> float:
    """Worst-case billed cost of one request capped at ``max_tokens``.

    Assumes every billed output token is spent (the model never stops early)
    and ignores caching discounts, so the estimate is an upper bound.
    """
    return max_tokens * pricing_for(model)["output"]


def estimate_cost_from_tokens(model: str, prompt_tokens: int, output_tokens: int) -> float:
    """Actual (post-run) billed cost from returned usage tokens."""
    prices = pricing_for(model)
    return prompt_tokens * prices["input"] + output_tokens * prices["output"]


def manifest_path_for(out_path: Path) -> Path:
    """Sidecar for an output JSONL: ``responses.jsonl -> responses.manifest.json``."""
    return out_path.with_name(out_path.stem + MANIFEST_SUFFIX)


def spec_key(model: str, num_runs: int, concurrency: int, exchange: int, prompts_arg: str, command_line: str) -> str:
    """A stable fingerprint of the invocation a manifest was written for."""
    payload = f"{model}|{num_runs}|{concurrency}|{exchange}|{prompts_arg}|{command_line}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def build_manifest(  # noqa: PLR0913 (manifest assembly needs every spend knob)
    *,
    run_kind: str,
    model: str,
    max_tokens: int,
    max_requests: int,
    concurrency: int,
    command_line: str,
    num_runs: int,
) -> dict[str, Any]:
    """Assemble the spend manifest for one (real) run."""
    per_call = estimate_cost_per_call(model, max_tokens)
    total = per_call * max_requests
    return {
        "manifest_id": uuid.uuid4().hex[:12],
        "run_kind": run_kind,
        "model": model,
        "max_tokens": max_tokens,
        "max_concurrent_requests": concurrency,
        "max_requests": max_requests,
        "num_runs": num_runs,
        "estimated_cost_per_call_usd": round(per_call, 6),
        "estimated_cost_usd": round(total, 6),
        "total_cap_usd": TOTAL_CAP_USD,
        "command_line": command_line,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def validate_manifest(manifest: dict[str, Any]) -> None:  # noqa: C901 (field-by-field contract)
    """Enforce the manifest schema and the <= $5.00 cap; raise on violation.

    The checker contract (VAL-EVAL-012): a manifest refusing values over the
    cap — for the per-run cap, the estimated total, and any malformed field.
    """
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    missing = [field for field in SCHEMA_FIELDS if field not in manifest]
    if missing:
        raise ManifestError(f"manifest missing required fields: {missing}")
    if manifest["run_kind"] not in VALID_RUN_KINDS:
        raise ManifestError(f"run_kind must be one of {VALID_RUN_KINDS}, got {manifest['run_kind']!r}")
    for field in ("max_tokens", "max_concurrent_requests", "max_requests"):
        value = manifest[field]
        if not isinstance(value, int) or value <= 0:
            raise ManifestError(f"{field} must be a positive int, got {value!r}")
    for field in ("estimated_cost_per_call_usd", "estimated_cost_usd", "total_cap_usd"):
        value = manifest[field]
        if not isinstance(value, (int, float)) or value < 0:
            raise ManifestError(f"{field} must be a non-negative number, got {value!r}")
    if manifest["run_kind"] != "real":
        return  # dry_run manifests are informational; cap checks apply to spend
    if manifest["total_cap_usd"] > TOTAL_CAP_USD:
        raise ManifestError(f"total_cap_usd exceeds the {TOTAL_CAP_USD:.2f} mission cap")
    if manifest["estimated_cost_usd"] > manifest["total_cap_usd"]:
        raise ManifestError(
            f"estimated_cost_usd ({manifest['estimated_cost_usd']:.4f}) exceeds "
            f"the manifest's own total_cap_usd ({manifest['total_cap_usd']:.4f})"
        )
    if not manifest["command_line"]:
        raise ManifestError("command_line is required for chargeability")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data: dict[str, Any] = json.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise ManifestError(
            f"spend manifest not found: {path}\n"
            "Manifest-before-run is enforced: run `--write-manifest` first, "
            "review the sidecar, then start the real run."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"spend manifest is not valid JSON: {path} ({exc})") from exc
    validate_manifest(data)
    return data


def read_ledger_entries(ledger_path: Path) -> list[dict[str, Any]]:
    if not Path(ledger_path).exists():
        return []
    entries: list[dict[str, Any]] = []
    for i, raw_line in enumerate(Path(ledger_path).read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"ledger line {i} is not valid JSON: {exc}") from exc
    return entries


def chargeable_ledger_entries(ledger_path: Path) -> list[dict[str, Any]]:
    """Ledger entries that count toward the cap.

    Only manifest-annotated real-run entries are chargeable: an entry must
    carry ``run_kind == "real"``, a ``manifest_id``, and an ``actual_cost_usd``.
    Dry-run rows (``run_kind="dry_run"`` or missing annotation) contribute 0
    by construction — they are never summed.
    """
    chargeable = []
    for i, entry in enumerate(read_ledger_entries(ledger_path), start=1):
        if entry.get("run_kind") != "real":
            continue
        if not entry.get("manifest_id") or not entry.get("actual_cost_usd"):
            raise ManifestError(f"ledger line {i} is a real-run entry without manifest annotation")
        chargeable.append(entry)
    return chargeable


def ledger_total(ledger_path: Path) -> float:
    """Cumulative real-run spend to date ($), from manifest-annotated entries only."""
    return round(sum(float(e["actual_cost_usd"]) for e in chargeable_ledger_entries(ledger_path)), 6)


def enforce_pre_run_budget(manifest: dict[str, Any], ledger_path: Path) -> float:
    """Refuse a real run whose estimate would push cumulative spend over the cap.

    Returns the remaining budget after this run's estimate is reserved.
    """
    validate_manifest(manifest)
    if ledger_total(ledger_path) + manifest["estimated_cost_usd"] > TOTAL_CAP_USD + 1e-9:
        raise ManifestError(
            "real run refused: estimated_cost_usd "
            f"{manifest['estimated_cost_usd']:.4f} plus ledger actuals {ledger_total(ledger_path):.4f} "
            f"exceeds the {TOTAL_CAP_USD:.2f} mission cap"
        )
    return TOTAL_CAP_USD - ledger_total(ledger_path)


def append_ledger(ledger_path: Path, entry: dict[str, Any]) -> None:
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_ledger_entry(
    *,
    manifest: dict[str, Any],
    model: str,
    prompt_tokens: int,
    output_tokens: int,
    output_relpath: str,
) -> dict[str, Any]:
    """The post-run actuals record: where the spend figure comes from."""
    return {
        "manifest_id": manifest["manifest_id"],
        "run_kind": "real",
        "model": model,
        "actual_cost_usd": round(estimate_cost_from_tokens(model, prompt_tokens, output_tokens), 6),
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "output": output_relpath,
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

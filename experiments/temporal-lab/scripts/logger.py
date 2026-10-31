"""Verbose logging + cost ledger for the temporal lab.

Three artifacts:

  runtime/logs/YYYY-MM-DD.log   — one redacted JSON line per LLM call
  runtime/logs/cost-ledger.csv  — append-only ledger of every call's cost
  runtime/metrics/altered-states.prom — Prometheus textfile (see metrics.py)

Every record carries the ambient trace id from ``altered_states.log_utils``, so
a whole cron dispatch (all due characters) is greppable as one unit, and every
secret-shaped value is redacted before it reaches disk.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# These scripts are run directly (`python temporal_init.py`), which puts only
# this directory on sys.path. Add the repository root so the shared
# `altered_states` package resolves the same way it does for the root app.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from characters import resolve_base_path  # noqa: E402

from altered_states.log_utils import current_trace_id, redact  # noqa: E402
from altered_states.metrics import REGISTRY, flush_metrics  # noqa: E402

LEDGER_FIELDS = ["ts", "substance", "model", "tokens_in", "tokens_out", "cost_usd", "status", "trace_id"]


class ModelCost(TypedDict):
    """Spend for one model."""

    calls: int
    cost_usd: float


class CostSummary(TypedDict):
    """Spend for a single day."""

    date: str
    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float


class LifetimeCostSummary(TypedDict):
    """Spend across the whole ledger."""

    calls: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    by_model: dict[str, ModelCost]


@dataclass(frozen=True, slots=True)
class CallRecord:
    """One LLM call, as written to the daily log and the cost ledger."""

    substance: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    status: str
    message: str = ""
    duration_ms: int | None = None

    def to_json(self, now: datetime) -> dict[str, object]:
        """Render the record for the JSON-lines log, redacted and trace-tagged."""
        record: dict[str, object] = {
            "ts": now.isoformat(timespec="seconds"),
            "substance": self.substance,
            "model": self.model,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": round(self.cost_usd, 6),
            "status": self.status,
            "duration_ms": self.duration_ms,
            "message": self.message,
        }
        trace_id = current_trace_id()
        if trace_id:
            record["trace_id"] = trace_id
        return redact(record)


def _logs_dir() -> Path:
    d = resolve_base_path() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _metrics_target() -> Path:
    """Prometheus textfile next to the runtime state for this lab instance."""
    target = resolve_base_path() / "metrics" / "altered-states.prom"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def record_metrics(record: CallRecord) -> None:
    """Feed one call into the shared metrics registry."""
    REGISTRY.increment("llm_calls", status=record.status, substance=record.substance)
    if record.status == "ok":
        REGISTRY.increment("llm_tokens", record.tokens_in, direction="in")
        REGISTRY.increment("llm_tokens", record.tokens_out, direction="out")
        REGISTRY.increment("cycles_generated", 1, substance=record.substance)
        if record.duration_ms is not None:
            REGISTRY.observe("llm_latency_seconds", record.duration_ms / 1000, substance=record.substance)


def log_call(record: CallRecord) -> None:
    """Append one structured line to today's log + cost-ledger.csv, then flush metrics."""
    now = datetime.now()
    entry = record.to_json(now)

    log_path = _logs_dir() / f"{now.strftime('%Y-%m-%d')}.log"
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    ledger_path = _logs_dir() / "cost-ledger.csv"
    new = not ledger_path.exists()
    with open(ledger_path, "a", newline="") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(LEDGER_FIELDS)
        writer.writerow(
            [
                entry["ts"],
                record.substance,
                record.model,
                record.tokens_in,
                record.tokens_out,
                entry["cost_usd"],
                record.status,
                entry.get("trace_id", ""),
            ]
        )

    record_metrics(record)
    flush_metrics(_metrics_target(), emit_log=False)


def _read_ledger(ledger_path: Path) -> list[dict[str, str]]:
    if not ledger_path.exists():
        return []
    with open(ledger_path) as f:
        return [row for row in csv.DictReader(f) if row["status"] == "ok"]


def daily_cost_summary(date: str | None = None) -> CostSummary:
    """Return totals for a given YYYY-MM-DD (default: today)."""
    target = date or datetime.now().strftime("%Y-%m-%d")
    totals: CostSummary = {"date": target, "calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
    for row in _read_ledger(_logs_dir() / "cost-ledger.csv"):
        if not row["ts"].startswith(target):
            continue
        totals["calls"] += 1
        totals["tokens_in"] += int(row["tokens_in"] or 0)
        totals["tokens_out"] += int(row["tokens_out"] or 0)
        totals["cost_usd"] += float(row["cost_usd"] or 0)
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return totals


def lifetime_cost_summary() -> LifetimeCostSummary:
    """Return totals across the entire ledger."""
    totals: LifetimeCostSummary = {
        "calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "by_model": {},
    }
    for row in _read_ledger(_logs_dir() / "cost-ledger.csv"):
        totals["calls"] += 1
        totals["tokens_in"] += int(row["tokens_in"] or 0)
        totals["tokens_out"] += int(row["tokens_out"] or 0)
        totals["cost_usd"] += float(row["cost_usd"] or 0)
        model = row["model"]
        per_model = totals["by_model"].setdefault(model, {"calls": 0, "cost_usd": 0.0})
        per_model["calls"] += 1
        per_model["cost_usd"] += float(row["cost_usd"] or 0)
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    for model_totals in totals["by_model"].values():
        model_totals["cost_usd"] = round(model_totals["cost_usd"], 4)
    return totals


def main() -> int:
    """Print cost summaries from the command line."""
    today = daily_cost_summary()
    lifetime = lifetime_cost_summary()
    print(f"Today ({today['date']}): {today['calls']} calls, ${today['cost_usd']:.4f}")
    print(f"Lifetime: {lifetime['calls']} calls, ${lifetime['cost_usd']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Verbose logging + cost ledger for the temporal lab.

Two artifacts:
  runtime/logs/YYYY-MM-DD.log   — one structured line per LLM call
  runtime/logs/cost-ledger.csv  — append-only ledger of every call's cost
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from characters import resolve_base_path


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
        """Render the record for the JSON-lines log."""
        return {
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


def _logs_dir() -> Path:
    d = resolve_base_path() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_call(record: CallRecord) -> None:
    """Append one structured line to today's log + cost-ledger.csv."""
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
            writer.writerow(["ts", "substance", "model", "tokens_in", "tokens_out", "cost_usd", "status"])
        writer.writerow(
            [
                entry["ts"],
                record.substance,
                record.model,
                record.tokens_in,
                record.tokens_out,
                entry["cost_usd"],
                record.status,
            ]
        )


def daily_cost_summary(date: str | None = None) -> CostSummary:
    """Return totals for a given YYYY-MM-DD (default: today)."""
    target = date or datetime.now().strftime("%Y-%m-%d")
    ledger_path = _logs_dir() / "cost-ledger.csv"
    totals: CostSummary = {"date": target, "calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
    if not ledger_path.exists():
        return totals
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            if not row["ts"].startswith(target):
                continue
            if row["status"] != "ok":
                continue
            totals["calls"] += 1
            totals["tokens_in"] += int(row["tokens_in"] or 0)
            totals["tokens_out"] += int(row["tokens_out"] or 0)
            totals["cost_usd"] += float(row["cost_usd"] or 0)
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return totals


def lifetime_cost_summary() -> LifetimeCostSummary:
    """Return totals across the entire ledger."""
    ledger_path = _logs_dir() / "cost-ledger.csv"
    totals: LifetimeCostSummary = {
        "calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "by_model": {},
    }
    if not ledger_path.exists():
        return totals
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            if row["status"] != "ok":
                continue
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

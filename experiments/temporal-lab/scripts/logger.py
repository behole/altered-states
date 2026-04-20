"""Verbose logging + cost ledger for the temporal lab.

Two artifacts:
  runtime/logs/YYYY-MM-DD.log   — one structured line per LLM call
  runtime/logs/cost-ledger.csv  — append-only ledger of every call's cost
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from characters import resolve_base_path


def _logs_dir() -> Path:
    d = resolve_base_path() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_call(
    substance: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    status: str,
    message: str = "",
    duration_ms: int | None = None,
) -> None:
    """Append one structured line to today's log + cost-ledger.csv."""
    now = datetime.now()
    record = {
        "ts": now.isoformat(timespec="seconds"),
        "substance": substance,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost_usd, 6),
        "status": status,
        "duration_ms": duration_ms,
        "message": message,
    }
    log_path = _logs_dir() / f"{now.strftime('%Y-%m-%d')}.log"
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    ledger_path = _logs_dir() / "cost-ledger.csv"
    new = not ledger_path.exists()
    with open(ledger_path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "substance", "model", "tokens_in", "tokens_out", "cost_usd", "status"])
        w.writerow([
            record["ts"], substance, model, tokens_in, tokens_out, record["cost_usd"], status,
        ])


def daily_cost_summary(date: str | None = None) -> dict:
    """Return totals for a given YYYY-MM-DD (default: today)."""
    target = date or datetime.now().strftime("%Y-%m-%d")
    ledger_path = _logs_dir() / "cost-ledger.csv"
    totals = {"date": target, "calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
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


def lifetime_cost_summary() -> dict:
    """Return totals across the entire ledger."""
    ledger_path = _logs_dir() / "cost-ledger.csv"
    totals = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "by_model": {}}
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
            m = row["model"]
            totals["by_model"].setdefault(m, {"calls": 0, "cost_usd": 0.0})
            totals["by_model"][m]["calls"] += 1
            totals["by_model"][m]["cost_usd"] += float(row["cost_usd"] or 0)
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    for m in totals["by_model"]:
        totals["by_model"][m]["cost_usd"] = round(totals["by_model"][m]["cost_usd"], 4)
    return totals

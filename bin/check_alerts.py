#!/usr/bin/env python3
"""Evaluate `alerts/alerts.yaml` against a metrics snapshot.

The alert policy is a file in the repository, not a dashboard someone configured
once. This script is the evaluator: it reads a Prometheus textfile produced by
`altered_states.metrics.flush_metrics()`, compares each signal to its threshold,
and exits non-zero when a `critical` alert fires.

An alert is only ever paging someone, so two things are validated before any
threshold is checked:

* every alert names a runbook, and that file exists;
* every alert names a signal and a threshold, and the severities and comparison
  operators are from a known set.

`--state` persists consecutive-fire counts so `for_runs` means what it says: a
single noisy sample does not page anyone.

Usage:
    python bin/check_alerts.py --snapshot runtime/metrics/altered-states.prom
    python bin/check_alerts.py --snapshot ... --state .alert-state.json
    python bin/check_alerts.py --validate-only          # policy check, no metrics
"""

from __future__ import annotations

import argparse
import json
import operator
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_FILE = REPO_ROOT / "alerts" / "alerts.yaml"

EXIT_OK = 0
EXIT_FIRING = 1
EXIT_POLICY = 2

SEVERITIES = ("critical", "warning", "info")
COMPARATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
}

# `name{label="value",label2="value2"} 12.0`
SERIES_LINE = r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{.*\})?\s+(?P<value>\S+)$"


@dataclass(frozen=True)
class Alert:
    """One threshold in the policy."""

    name: str
    description: str
    signal: str
    comparison: str
    threshold: float
    severity: str
    runbook: str
    for_runs: int

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], defaults: dict[str, Any]) -> Alert:
        merged = {**defaults, **raw}
        return cls(
            name=str(merged["name"]),
            description=str(merged.get("description", "")),
            signal=str(merged["signal"]),
            comparison=str(merged.get("comparison", ">")),
            threshold=float(merged["threshold"]),
            severity=str(merged.get("severity", "warning")),
            runbook=str(merged.get("runbook", "")),
            for_runs=int(merged.get("for_runs", 1)),
        )


@dataclass(frozen=True)
class Result:
    """The outcome of evaluating one alert."""

    alert: Alert
    observed: float | None
    fires: bool
    consecutive: int

    @property
    def description(self) -> str:
        if self.observed is None:
            return f"{self.alert.signal} is absent from the snapshot"
        return f"{self.alert.signal} = {self.observed:g} (threshold {self.alert.comparison} {self.alert.threshold:g})"


def load_policy(path: Path) -> list[Alert]:
    """Parse the policy file. Raises ValueError on malformed content."""
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    defaults = raw.get("defaults", {})
    alerts = [Alert.from_mapping(entry, defaults) for entry in raw.get("alerts", [])]
    if not alerts:
        raise ValueError(f"{path} declares no alerts")
    return alerts


def validate_policy(alerts: list[Alert]) -> list[str]:
    """Every reason this policy would be unusable in an incident."""
    problems: list[str] = []
    seen: set[str] = set()

    for alert in alerts:
        if alert.name in seen:
            problems.append(f"duplicate alert name: {alert.name}")
        seen.add(alert.name)

        if alert.severity not in SEVERITIES:
            problems.append(f"{alert.name}: severity {alert.severity!r} is not one of {SEVERITIES}")
        if alert.comparison not in COMPARATORS:
            problems.append(f"{alert.name}: comparison {alert.comparison!r} is not one of {tuple(COMPARATORS)}")
        if alert.for_runs < 1:
            problems.append(f"{alert.name}: for_runs must be at least 1")
        if not alert.runbook:
            problems.append(f"{alert.name}: no runbook. An alert nobody can act on is noise.")
        elif not (REPO_ROOT / alert.runbook).exists():
            problems.append(f"{alert.name}: runbook {alert.runbook} does not exist")
        if not alert.description:
            problems.append(f"{alert.name}: no description")
    return problems


def parse_snapshot(text: str) -> dict[str, float]:
    """Parse a Prometheus textfile into `{series: value}`.

    Series keys keep their labels, so `a{x="y"}` and `a` are distinct, which is
    what an alert targeting a single label combination needs.
    """
    pattern = re.compile(SERIES_LINE)
    series: dict[str, float] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.match(stripped)
        if match is None:
            continue
        key = match.group("name") + (match.group("labels") or "")
        try:
            series[key] = float(match.group("value"))
        except ValueError:
            continue
    return series


def lookup(series: dict[str, float], signal: str) -> float | None:
    """Resolve an alert's signal against the snapshot.

    An exact series wins. Otherwise all labelled variants of the same metric are
    summed, which is what ``sum(a_metric)`` would do in PromQL: an alert on
    `secret_redactions` fires whether the redaction was by field name or by
    value shape.
    """
    if signal in series:
        return series[signal]
    base = signal.split("{", 1)[0]
    variants = [value for key, value in series.items() if key.split("{", 1)[0] == base]
    return sum(variants) if variants else None


def evaluate(alerts: list[Alert], series: dict[str, float], previous: dict[str, int]) -> list[Result]:
    """Compare each alert's signal to its threshold.

    A missing signal counts as firing for `<` alerts (the build did not run) and
    as not firing otherwise — an absent counter is not evidence of a spike.
    """
    results: list[Result] = []
    for alert in alerts:
        observed = lookup(series, alert.signal)
        if observed is None:
            fires = alert.comparison in {"<", "<="}
        else:
            fires = COMPARATORS[alert.comparison](observed, alert.threshold)
        consecutive = previous.get(alert.name, 0) + 1 if fires else 0
        results.append(
            Result(
                alert=alert,
                observed=observed,
                fires=fires and consecutive >= alert.for_runs,
                consecutive=consecutive,
            )
        )
    return results


def next_state(results: list[Result]) -> dict[str, int]:
    """Consecutive-fire counts to carry into the next evaluation."""
    return {result.alert.name: result.consecutive for result in results if result.consecutive}


def render_text(results: list[Result]) -> str:
    firing = [result for result in results if result.fires]
    lines = [f"Evaluated {len(results)} alert(s): {len(firing)} firing.", ""]
    for result in results:
        marker = "FIRING " if result.fires else "  ok   "
        lines.append(f"{marker} [{result.alert.severity:8s}] {result.alert.name}: {result.description}")
        if result.fires:
            lines.append(f"           {result.alert.description}")
            lines.append(f"           runbook: {result.alert.runbook}")
    return "\n".join(lines)


def render_json(results: list[Result]) -> str:
    """A payload for a webhook consumer."""
    payload = {
        "firing": [
            {
                "name": result.alert.name,
                "severity": result.alert.severity,
                "description": result.alert.description,
                "signal": result.alert.signal,
                "observed": result.observed,
                "threshold": result.alert.threshold,
                "comparison": result.alert.comparison,
                "runbook": result.alert.runbook,
            }
            for result in results
            if result.fires
        ],
        "evaluated": len(results),
    }
    return json.dumps(payload, indent=2)


def _load_state(path: Path | None) -> dict[str, int]:
    if path is None or not path.exists():
        return {}
    try:
        loaded: dict[str, int] = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate alert thresholds against a metrics snapshot")
    parser.add_argument("--policy", type=Path, default=POLICY_FILE, help="alert policy file")
    parser.add_argument("--snapshot", type=Path, default=None, help="Prometheus textfile to evaluate")
    parser.add_argument("--state", type=Path, default=None, help="persist consecutive-fire counts here")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--validate-only", action="store_true", help="check the policy and exit")
    args = parser.parse_args(argv)

    if not args.policy.exists():
        print(f"ERROR: {args.policy} does not exist", file=sys.stderr)
        return EXIT_POLICY

    try:
        alerts = load_policy(args.policy)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {args.policy} is malformed: {exc}", file=sys.stderr)
        return EXIT_POLICY

    problems = validate_policy(alerts)
    if problems:
        for problem in problems:
            print(f"  POLICY: {problem}", file=sys.stderr)
        return EXIT_POLICY

    if args.validate_only:
        print(f"Alert policy is valid: {len(alerts)} alert(s), every one with a runbook.")
        return EXIT_OK

    if args.snapshot is None or not args.snapshot.exists():
        print("ERROR: --snapshot must point at an existing metrics textfile", file=sys.stderr)
        return EXIT_POLICY

    series = parse_snapshot(args.snapshot.read_text())
    results = evaluate(alerts, series, _load_state(args.state))

    print(render_json(results) if args.format == "json" else render_text(results))

    if args.state is not None:
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(next_state(results), indent=2))

    return EXIT_FIRING if any(result.fires and result.alert.severity == "critical" for result in results) else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

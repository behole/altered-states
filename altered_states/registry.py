"""The metrics registry itself, with no dependencies inside this package.

Kept apart from `altered_states.metrics` so that `log_utils` can increment a
counter without importing the module that writes textfiles and emits log
lines. The layering runs one way and only one way:

    registry  <-  log_utils  <-  metrics  <-  application

`metrics` re-exports everything here, so importing `REGISTRY` from either
module works; new code should prefer `altered_states.metrics`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

NAMESPACE = "altered_states"

_HELP: dict[str, str] = {
    "build_runs": "Number of site builds executed.",
    "build_duration_seconds": "Wall-clock duration of a site build.",
    "cycles_generated": "Temporal-lab cycles generated.",
    "llm_calls": "Outbound LLM API calls.",
    "llm_latency_seconds": "Latency of an outbound LLM API call.",
    "llm_tokens": "Tokens exchanged with an LLM provider.",
    "test_cases": "Test cases executed in a run.",
}


class Registry:
    """Counters, gauges, and histograms keyed by name + sorted label pairs."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}

    # -- mutators ---------------------------------------------------------

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Add ``value`` to a monotonic counter."""
        key = (name, self._label_key(labels))
        self._counters[key] = self._counters.get(key, 0.0) + value

    def gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a point-in-time value."""
        self._gauges[(name, self._label_key(labels))] = value

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Record an observation in a histogram."""
        self._histograms.setdefault((name, self._label_key(labels)), []).append(value)

    # -- readers ----------------------------------------------------------

    @staticmethod
    def _label_key(labels: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((str(k), str(v)) for k, v in labels.items()))

    def counter_value(self, name: str, **labels: str) -> float:
        return self._counters.get((name, self._label_key(labels)), 0.0)

    def gauge_value(self, name: str, **labels: str) -> float:
        return self._gauges.get((name, self._label_key(labels)), 0.0)

    def histogram_values(self, name: str, **labels: str) -> list[float]:
        return list(self._histograms.get((name, self._label_key(labels)), []))

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    # -- rendering --------------------------------------------------------

    @staticmethod
    def _render_labels(labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        rendered = ",".join(f'{key}="{value}"' for key, value in labels)
        return "{" + rendered + "}"

    def render_prometheus(self) -> str:
        """Render every series in Prometheus text exposition format."""
        lines: list[str] = []
        for (name, labels), value in sorted(self._counters.items()):
            lines.append(f"# HELP {NAMESPACE}_{name} {_HELP.get(name, name)}")
            lines.append(f"# TYPE {NAMESPACE}_{name} counter")
            lines.append(f"{NAMESPACE}_{name}{self._render_labels(labels)} {value:g}")
        for (name, labels), value in sorted(self._gauges.items()):
            lines.append(f"# TYPE {NAMESPACE}_{name} gauge")
            lines.append(f"{NAMESPACE}_{name}{self._render_labels(labels)} {value:g}")
        for (name, labels), values in sorted(self._histograms.items()):
            lines.append(f"# TYPE {NAMESPACE}_{name} summary")
            total = sum(values)
            lines.append(f"{NAMESPACE}_{name}_sum{self._render_labels(labels)} {total:g}")
            lines.append(f"{NAMESPACE}_{name}_count{self._render_labels(labels)} {len(values)}")
        return "\n".join(lines) + "\n"

    def as_dict(self) -> dict[str, Any]:
        """JSON-friendly snapshot used for the log line.

        Series keys are namespaced exactly like the Prometheus export, so a
        value can be traced from the JSON log line to the textfile.
        """
        return {
            "counters": {
                f"{NAMESPACE}_{name}{self._render_labels(labels)}": value
                for (name, labels), value in self._counters.items()
            },
            "gauges": {
                f"{NAMESPACE}_{name}{self._render_labels(labels)}": value
                for (name, labels), value in self._gauges.items()
            },
            "histograms": {
                f"{NAMESPACE}_{name}{self._render_labels(labels)}": {
                    "count": len(values),
                    "sum": round(sum(values), 6),
                }
                for (name, labels), values in self._histograms.items()
            },
        }


REGISTRY = Registry()

"""In-process metrics registry with Prometheus textfile export.

The repository has no always-on service to scrape, so metrics are accumulated
during a run and flushed twice:

* to a Prometheus textfile, which any node_exporter `textfile` collector on the
  host can pick up, and
* as a JSON summary log line, so a CI job or cron log is self-describing.

Metric names are namespaced with ``altered_states_``. Labels are rendered in
Prometheus exposition format, which keeps the output portable to Grafana,
VictoriaMetrics, or Axiom without a client library.

The counters themselves live in `altered_states.registry` and are re-exported
here, so ``from altered_states.metrics import REGISTRY`` is the supported entry
point.

Usage:
    from altered_states.metrics import REGISTRY, flush_metrics

    REGISTRY.increment("build_runs")
    REGISTRY.observe("build_duration_seconds", 0.41)
    flush_metrics()                     # honours METRICS_TEXTFILE_PATH
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from altered_states.log_utils import log_event
from altered_states.registry import NAMESPACE, REGISTRY, Registry

__all__ = [
    "NAMESPACE",
    "REGISTRY",
    "Registry",
    "dump_json",
    "flush_metrics",
    "textfile_path",
    "timer",
    "write_textfile",
]

DEFAULT_TEXTFILE = "runtime/metrics/altered-states.prom"


def textfile_path() -> Path:
    """Where to write the Prometheus textfile; overridable for tests/CI."""
    return Path(os.environ.get("METRICS_TEXTFILE_PATH", DEFAULT_TEXTFILE))


def write_textfile(path: Path | None = None) -> Path:
    """Flush the registry to a Prometheus textfile and return its path."""
    target = path or textfile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(REGISTRY.render_prometheus())
    return target


def flush_metrics(path: Path | None = None, emit_log: bool = True) -> Path:
    """Write the textfile and (by default) log the snapshot as one JSON line."""
    written = write_textfile(path)
    if emit_log:
        log_event("metrics.flush", path=str(written), metrics=REGISTRY.as_dict())
    return written


@contextmanager
def timer(name: str, **labels: str) -> Iterator[None]:
    """Observe the wall-clock duration of a block in seconds."""
    started_at = time.perf_counter()
    try:
        yield
    finally:
        REGISTRY.observe(name, time.perf_counter() - started_at, **labels)


def dump_json() -> str:
    """Render the registry as indented JSON (used by the CI summary step)."""
    return json.dumps(REGISTRY.as_dict(), indent=2, sort_keys=True)

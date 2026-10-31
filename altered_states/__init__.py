"""Shared runtime support for the Altered States repository.

Both applications import from here:

* ``log_utils``        — structured JSON logging, secret redaction, trace ids
* ``registry``         — the dependency-free counters every other module uses
* ``metrics``          — in-process metrics registry + Prometheus textfile
* ``error_tracking``   — optional Sentry integration (off without SENTRY_DSN)
* ``feature_flags``    — file-backed flags with percentage rollout + staleness

Nothing in this package imports a third-party library at module scope, so it
stays importable in a bare interpreter and during offline dry-runs.
"""

from altered_states.log_utils import (
    current_trace_id,
    log_event,
    log_timed,
    redact,
    redact_text,
    trace_context,
)

__all__ = [
    "current_trace_id",
    "log_event",
    "log_timed",
    "redact",
    "redact_text",
    "trace_context",
]

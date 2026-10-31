"""Structured JSON logging with trace correlation and secret redaction.

Every script in this repository emits machine-readable log lines through
:func:`log_event` so a run can be followed end to end:

    {"ts": "...", "level": "INFO", "event": "site.build", "trace_id": "bld-...",
     "service": "site-builder", "duration_ms": 412, "cycles": 3482}

Two guarantees this module provides:

* **Redaction.** Any field whose *name* looks like a credential, and any
  *value* that matches a known token shape, is replaced before it reaches a
  handler. This is the single choke point — callers never format secrets into
  messages themselves.
* **Trace correlation.** :func:`trace_context` installs a trace id for the
  duration of a block; every nested log line and every outbound request record
  carries it, so one CLI invocation or cron cycle is greppable as a unit.

Usage:
    from log_utils import log_event, trace_context

    with trace_context("build") as trace_id:
        log_event("site.build", trace_id=trace_id, duration_ms=412)
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from altered_states.metrics import REGISTRY

SERVICE = os.environ.get("APP_SERVICE", "altered-states")
DEFAULT_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
REDACTED = "***REDACTED***"

# Field names that must never be written verbatim.
#
# `token(?!s)` deliberately avoids matching token *counts* such as
# `tokens_in` / `tokens_out`, which are safe, useful telemetry. A field named
# `access_token` or `token` is still redacted.
_SENSITIVE_KEYS = re.compile(
    r"(api[_-]?key|apikey|secret|token(?!s)|password|passwd|authorization|bearer|"
    r"credential|session[_-]?id|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)

# Value shapes that look like credentials even under an innocent field name.
_SECRET_VALUES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bsk-or-v1-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

# Trace ids are short, prefixed, and safe to log.
_TRACE_PREFIX_LENGTH = 5
_TRACE_RANDOM_BYTES = 4

_trace_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


def redact_text(value: str) -> str:
    """Replace every credential-shaped substring in ``value``.

    Counts what it scrubbed: a nonzero ``secret_redactions`` counter is the
    alerting signal that a credential reached a log line at all.
    """
    redacted = value
    scrubbed = 0
    for pattern in _SECRET_VALUES:
        redacted, count = pattern.subn(REDACTED, redacted)
        scrubbed += count
    if scrubbed:
        _count_redaction("value")
    return redacted


def is_sensitive_key(key: str) -> bool:
    """True when a field name implies a credential."""
    return bool(_SENSITIVE_KEYS.search(key))


def _count_redaction(kind: str) -> None:
    """Record that a credential was scrubbed from outgoing output."""
    REGISTRY.increment("secret_redactions", kind=kind)


def redact_value(key: str, value: Any) -> Any:
    """Redact one field, recursing into the containers we actually emit."""
    if is_sensitive_key(key):
        _count_redaction("key")
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(key, item) for item in value]
    return value


def redact(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a fully redacted copy of a log record."""
    return {str(key): redact_value(str(key), value) for key, value in record.items()}


# ---------------------------------------------------------------------------
# Trace correlation
# ---------------------------------------------------------------------------


def new_trace_id(prefix: str = "run") -> str:
    """Create a trace id like ``run-7f3c1a2b``: greppable and collision-safe."""
    digest = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    return f"{prefix[:_TRACE_PREFIX_LENGTH]}-{digest[: 2 * _TRACE_RANDOM_BYTES]}"


def current_trace_id() -> str | None:
    """The trace id installed by the innermost :func:`trace_context`, if any."""
    return _trace_var.get()


@contextmanager
def trace_context(prefix: str = "run") -> Iterator[str]:
    """Install a trace id for the duration of the block (nesting is allowed)."""
    trace_id = new_trace_id(prefix)
    token = _trace_var.set(trace_id)
    try:
        yield trace_id
    finally:
        _trace_var.reset(token)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    """RFC 3339 UTC timestamp with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def build_record(event: str, level: str, fields: Mapping[str, Any]) -> dict[str, Any]:
    """Assemble a redacted log record. Pure — safe to unit test."""
    record: dict[str, Any] = {
        "ts": _utc_timestamp(),
        "level": level.upper(),
        "event": event,
        "service": SERVICE,
    }
    trace_id = current_trace_id()
    if trace_id:
        record["trace_id"] = trace_id
    record.update(fields)
    return redact(record)


def log_event(
    event: str,
    *,
    level: str = DEFAULT_LEVEL,
    stream: Any = None,
    **fields: Any,
) -> dict[str, Any]:
    """Write one redacted JSON line and return the record that was written."""
    record = build_record(event, level, fields)
    destination = stream if stream is not None else sys.stderr
    destination.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    destination.flush()
    return record


class JsonFormatter(logging.Formatter):
    """Render ``logging`` records as the same JSON shape as :func:`log_event`."""

    def format(self, record: logging.LogRecord) -> str:
        payload = build_record(record.getMessage(), record.levelname, getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = DEFAULT_LEVEL, log_file: Path | None = None) -> logging.Logger:
    """Attach a JSON handler to the root logger; optionally also write a file."""
    handler: logging.Handler = logging.FileHandler(log_file) if log_file else logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    return root


def log_timed(event: str, started_at: float, **fields: Any) -> dict[str, Any]:
    """Emit an event carrying ``duration_ms`` measured from ``started_at``."""
    duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
    return log_event(event, duration_ms=duration_ms, **fields)


def set_log_fields(target: MutableMapping[str, Any], **fields: Any) -> None:
    """Convenience: merge already-redacted fields into a caller-owned mapping."""
    target.update(redact(fields))

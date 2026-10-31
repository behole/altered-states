"""Optional Sentry error tracking with breadcrumbs, tags, and user context.

The integration is deliberately *off unless configured*: without
``SENTRY_DSN`` every helper is a cheap no-op, so local runs and offline
dry-runs behave exactly as before. When a DSN is present, errors carry the
context an agent or maintainer needs to map a production failure back to a
code path:

* ``service`` and ``environment`` tags,
* the running git release (``APP_RELEASE`` or ``GIT_SHA``),
* the trace id from :mod:`log_utils`, so a Sentry event joins up with the
  matching JSON log line,
* breadcrumbs for every observable step (build phase, outbound API call,
  journal write) with credential-shaped data redacted.

Usage:
    from error_tracking import init_error_tracking, capture_exception, breadcrumb

    init_error_tracking("site-builder")
    breadcrumb("build", "loading journals", {"count": 10})
    try:
        ...
    except Exception as exc:
        capture_exception(exc)
        raise
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from altered_states.log_utils import current_trace_id, redact

INITIALIZED_STATE: dict[str, bool] = {"initialised": False}

# Breadcrumb data is capped so a large payload can never bloat an event.
MAX_BREADCRUMB_VALUE_LENGTH = 300


class SentrySdk(Protocol):
    """The slice of the Sentry SDK surface this module uses.

    Bodies raise rather than elide with ``...``: the methods are never called
    on this type, and an explicit raise keeps static analysis from reading the
    stub as a statement with no effect.
    """

    def init(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def add_breadcrumb(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def set_tag(self, key: str, value: str) -> None:
        raise NotImplementedError

    def set_user(self, user: dict[str, Any]) -> None:
        raise NotImplementedError

    def capture_exception(self, exc: BaseException) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class ErrorTrackingSettings:
    """Everything Sentry needs to attribute an event to this run."""

    dsn: str
    service: str
    environment: str = "production"
    release: str = "unknown"
    traces_sample_rate: float = 0.0
    tags: Mapping[str, str] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return bool(self.dsn)


def settings_from_env(service: str) -> ErrorTrackingSettings:
    """Build settings from the environment; empty DSN means disabled."""
    return ErrorTrackingSettings(
        dsn=os.environ.get("SENTRY_DSN", ""),
        service=service,
        environment=os.environ.get("APP_ENV", "production"),
        release=os.environ.get("APP_RELEASE") or os.environ.get("GIT_SHA") or "unknown",
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        tags={"service": service},
    )


def _load_sdk() -> SentrySdk | None:
    """Import sentry_sdk lazily; it is an optional dependency."""
    try:
        import sentry_sdk  # noqa: PLC0415
    except ImportError:
        return None
    return cast(SentrySdk, sentry_sdk)


def init_error_tracking(
    service: str,
    *,
    settings: ErrorTrackingSettings | None = None,
    sdk: SentrySdk | None = None,
) -> bool:
    """Initialise Sentry. Returns True only when a DSN is configured and applied."""
    resolved = settings or settings_from_env(service)
    if not resolved.enabled:
        return False

    client = sdk if sdk is not None else _load_sdk()
    if client is None:
        return False

    client.init(
        dsn=resolved.dsn,
        environment=resolved.environment,
        release=resolved.release,
        traces_sample_rate=resolved.traces_sample_rate,
        send_default_pii=False,
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )
    # `service` is always tagged — even when settings are constructed in code
    # rather than from the environment — so events are attributable by default.
    client.set_tag("service", resolved.service)
    for key, value in resolved.tags.items():
        client.set_tag(key, value)
    INITIALIZED_STATE["initialised"] = True
    return True


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_BREADCRUMB_VALUE_LENGTH:
        return value[:MAX_BREADCRUMB_VALUE_LENGTH] + "…"
    return value


def breadcrumb(category: str, message: str, data: Mapping[str, Any] | None = None) -> None:
    """Record one step. Redacts and truncates before it leaves the process."""
    if not INITIALIZED_STATE["initialised"]:
        return
    sdk = _load_sdk()
    if sdk is None:
        return
    payload = {key: _truncate(value) for key, value in redact(dict(data or {})).items()}
    trace_id = current_trace_id()
    if trace_id:
        payload["trace_id"] = trace_id
    sdk.add_breadcrumb(category=category, message=message, level="info", data=payload)


def set_user_context(user_id: str, **extra: str) -> None:
    """Attach the acting principal (never an email or other PII by default)."""
    if not INITIALIZED_STATE["initialised"]:
        return
    sdk = _load_sdk()
    if sdk is None:
        return
    sdk.set_user({"id": user_id, **redact(extra)})


def capture_exception(exc: BaseException) -> bool:
    """Report an exception. Returns True when it was actually sent."""
    if not INITIALIZED_STATE["initialised"]:
        return False
    sdk = _load_sdk()
    if sdk is None:
        return False
    sdk.capture_exception(exc)
    return True


def reset_state() -> None:
    """Test helper: forget that initialisation happened."""
    INITIALIZED_STATE["initialised"] = False

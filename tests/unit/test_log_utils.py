"""Unit tests for the shared logging, redaction, and tracing helpers."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from altered_states import log_utils
from altered_states.log_utils import (
    REDACTED,
    build_record,
    configure_logging,
    current_trace_id,
    is_sensitive_key,
    log_event,
    log_timed,
    new_trace_id,
    redact,
    redact_text,
    redact_value,
    trace_context,
)


class TestRedaction:
    @pytest.mark.parametrize(
        "key",
        ["api_key", "API_KEY", "apikey", "token", "authorization", "password", "Secret", "session_id"],
    )
    def test_sensitive_key_names_are_detected(self, key: str) -> None:
        assert is_sensitive_key(key)

    @pytest.mark.parametrize(
        "key", ["count", "substance", "duration_ms", "model", "tokens_in", "tokens_out", "input_tokens"]
    )
    def test_ordinary_key_names_are_not_sensitive(self, key: str) -> None:
        assert not is_sensitive_key(key)

    def test_string_values_are_replaced_for_sensitive_keys(self) -> None:
        assert redact_value("api_key", "anything at all") == REDACTED

    def test_non_sensitive_scalars_pass_through(self) -> None:
        assert redact_value("cycles", 3482) == 3482

    def test_nested_mappings_are_redacted_recursively(self) -> None:
        payload = {"outer": {"api_key": "sk-live-abc", "count": 2}}
        redacted = redact_value("payload", payload)
        assert redacted["outer"]["api_key"] == REDACTED
        assert redacted["outer"]["count"] == 2

    def test_lists_are_redacted_element_wise(self) -> None:
        redacted = redact_value("items", [{"token": "secret"}, {"count": 1}])
        assert redacted[0]["token"] == REDACTED
        assert redacted[1]["count"] == 1

    @pytest.mark.parametrize(
        "value",
        [
            "key sk-abcdefghijklmnop found",
            "Bearer abcdef123456",
            "ghp_abcdefghijklmnopqrst",
            "AKIAIOSFODNN7EXAMPLE",
            "github_pat_abcdefghijklmnopqrstuvwxyz",
        ],
    )
    def test_credential_shaped_substrings_are_scrubbed(self, value: str) -> None:
        scrubbed = redact_text(value)
        assert REDACTED in scrubbed
        assert "sk-abcdefghijklmnop" not in scrubbed

    def test_innocent_text_is_untouched(self) -> None:
        text = "cycle 42 completed in 11.3ms"
        assert redact_text(text) == text

    def test_full_record_redaction_preserves_safe_fields(self) -> None:
        record = {"event": "build.complete", "api_key": "x", "cycles": 5}
        result = redact(record)
        assert result["event"] == "build.complete"
        assert result["cycles"] == 5
        assert result["api_key"] == REDACTED


class TestTraceContext:
    def test_no_trace_id_outside_a_context(self) -> None:
        assert current_trace_id() is None

    def test_trace_id_is_visible_inside_the_block(self) -> None:
        with trace_context("build") as trace_id:
            assert current_trace_id() == trace_id
            assert trace_id.startswith("build-")

    def test_trace_id_is_cleared_after_the_block(self) -> None:
        with trace_context("build"):
            pass
        assert current_trace_id() is None

    def test_nested_contexts_restore_the_outer_trace(self) -> None:
        with trace_context("outer") as outer:
            with trace_context("inner") as inner:
                assert outer != inner
                assert current_trace_id() == inner
            assert current_trace_id() == outer

    def test_trace_ids_are_unique(self) -> None:
        ids = {new_trace_id("run") for _ in range(50)}
        assert len(ids) == 50

    def test_prefix_is_truncated_to_five_characters(self) -> None:
        assert new_trace_id("averylongprefix").startswith("avery-")


class TestRecords:
    def test_record_has_the_contract_fields(self) -> None:
        record = build_record("site.build", "INFO", {"cycles": 3})
        assert record["event"] == "site.build"
        assert record["level"] == "INFO"
        assert record["service"]
        assert "ts" in record
        assert record["cycles"] == 3

    def test_level_is_normalised_to_uppercase(self) -> None:
        assert build_record("x", "warning", {})["level"] == "WARNING"

    def test_trace_id_is_attached_when_available(self) -> None:
        with trace_context("test") as trace_id:
            record = build_record("x", "INFO", {})
        assert record["trace_id"] == trace_id

    def test_record_without_trace_context_omits_the_field(self) -> None:
        assert "trace_id" not in build_record("x", "INFO", {})

    def test_records_are_redacted_before_return(self) -> None:
        record = build_record("x", "INFO", {"api_key": "sk-should-not-appear"})
        assert record["api_key"] == REDACTED


class TestLogEvent:
    def test_writes_exactly_one_json_line(self) -> None:
        stream = io.StringIO()
        log_event("build.start", stream=stream, cycles=1)
        lines = stream.getvalue().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "build.start"

    def test_returned_record_matches_what_was_written(self) -> None:
        stream = io.StringIO()
        returned = log_event("build.done", stream=stream, cycles=7)
        assert json.loads(stream.getvalue()) == returned

    def test_secrets_never_reach_the_stream(self) -> None:
        stream = io.StringIO()
        log_event("auth", stream=stream, api_key="sk-live-123456789", note="Bearer abcdef12345")
        written = stream.getvalue()
        assert "sk-live-123456789" not in written
        assert "abcdef12345" not in written

    def test_log_timed_measures_a_duration(self) -> None:
        import time

        stream = io.StringIO()
        started = time.perf_counter()
        record = log_timed("build.complete", started, stream=stream)
        assert record["duration_ms"] >= 0
        assert "duration_ms" in record


class TestLoggingBridge:
    def test_json_formatter_emits_parseable_output(self, tmp_path: Path) -> None:
        log_file = tmp_path / "app.log"
        logger = configure_logging("INFO", log_file=log_file)
        logger.info("hello")
        for handler in logger.handlers:
            handler.flush()
        payload = json.loads(log_file.read_text().strip())
        assert payload["event"] == "hello"
        assert payload["level"] == "INFO"

    def test_configure_logging_sets_the_requested_level(self, tmp_path: Path) -> None:
        logger = configure_logging("DEBUG", log_file=tmp_path / "app.log")
        assert logger.level == logging.DEBUG

    def test_formatter_redacts_record_fields(self, tmp_path: Path) -> None:
        log_file = tmp_path / "app.log"
        logger = configure_logging("INFO", log_file=log_file)
        logger.info("auth", extra={"fields": {"api_key": "sk-secret-value"}})
        for handler in logger.handlers:
            handler.flush()
        assert "sk-secret-value" not in log_file.read_text()

    def test_module_exposes_the_documented_contract(self) -> None:
        for name in ("log_event", "trace_context", "redact", "REDACTED"):
            assert hasattr(log_utils, name)

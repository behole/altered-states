"""Unit tests for the eval runner's async paths, using a fake Anthropic client."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import run_eval


class FakeUsage:
    def __init__(self, tokens_in: int = 10, tokens_out: int = 20) -> None:
        self.input_tokens = tokens_in
        self.output_tokens = tokens_out
        self.cache_creation_input_tokens = 3
        self.cache_read_input_tokens = 7


class FakeBlock:
    def __init__(self, text: str, kind: str = "text") -> None:
        self.text = text
        self.type = kind


class FakeMessage:
    def __init__(self, text: str = "a response") -> None:
        self.content = [FakeBlock(text), FakeBlock("ignored", kind="thinking")]
        self.stop_reason = "end_turn"
        self.usage = FakeUsage()


class FakeMessages:
    """Records every request and either answers or raises a scripted error."""

    def __init__(self, errors: list[BaseException] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._errors = list(errors or [])

    async def create(self, **kwargs: Any) -> FakeMessage:
        self.calls.append(kwargs)
        if self._errors:
            raise self._errors.pop(0)
        return FakeMessage()


class FakeClient:
    def __init__(self, errors: list[BaseException] | None = None) -> None:
        self.messages = FakeMessages(errors)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record backoff delays instead of actually waiting."""
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("run_eval.asyncio.sleep", fake_sleep)
    return delays


def a_run(substance: str = "lsd", exchange: int = 1) -> run_eval.EvalRun:
    return run_eval.EvalRun(substance, "medium", {"id": "p1", "text": "hello"}, exchange)


class TestAttempt:
    def test_request_includes_the_cache_controlled_system_prompt(self) -> None:
        client = FakeClient()
        asyncio.run(run_eval._attempt(client, a_run(), "claude-test", "SYSTEM"))

        kwargs = client.messages.calls[0]
        assert kwargs["model"] == "claude-test"
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert kwargs["messages"] == [{"role": "user", "content": "hello"}]

    def test_only_text_blocks_are_concatenated(self) -> None:
        row = asyncio.run(run_eval._attempt(FakeClient(), a_run(), "m", "S"))
        assert row["response"] == "a response"

    def test_usage_and_stop_reason_are_recorded(self) -> None:
        row = asyncio.run(run_eval._attempt(FakeClient(), a_run(), "m", "S"))
        assert row["stop_reason"] == "end_turn"
        assert row["usage"]["cache_read_input_tokens"] == 7

    def test_successful_call_increments_metrics(self) -> None:
        from altered_states.metrics import REGISTRY

        asyncio.run(run_eval._attempt(FakeClient(), a_run("mdma"), "m", "S"))
        assert REGISTRY.counter_value("llm_calls", status="ok", substance="mdma") == 1.0
        assert REGISTRY.counter_value("llm_tokens", direction="in") == 10.0
        assert REGISTRY.counter_value("llm_tokens", direction="out") == 20.0


class TestRunOne:
    def test_successful_run_returns_the_row(self) -> None:
        sem = asyncio.Semaphore(4)
        row = asyncio.run(run_eval.run_one(FakeClient(), sem, a_run(), "m"))
        assert row["response"] == "a response"

    def test_transient_error_is_retried_then_succeeds(self, no_sleep: list[float]) -> None:
        client = FakeClient(errors=[RuntimeError("429 slow down")])
        sem = asyncio.Semaphore(4)

        row = asyncio.run(run_eval.run_one(client, sem, a_run(), "m"))

        assert row["response"] == "a response"
        assert len(client.messages.calls) == 2
        assert no_sleep == [run_eval.BACKOFFS_SEC[0]]

    def test_exhausted_retries_return_an_error_row(self, no_sleep: list[float]) -> None:
        client = FakeClient(errors=[RuntimeError("down")] * run_eval.RETRY_ATTEMPTS)
        sem = asyncio.Semaphore(4)

        row = asyncio.run(run_eval.run_one(client, sem, a_run(), "m"))

        assert row["score"] == "error"
        assert len(client.messages.calls) == run_eval.RETRY_ATTEMPTS
        assert len(no_sleep) == run_eval.RETRY_ATTEMPTS - 1

    def test_error_rows_keep_the_error_type_in_notes(self) -> None:
        client = FakeClient(errors=[ValueError("bad shape")] * run_eval.RETRY_ATTEMPTS)
        row = asyncio.run(run_eval.run_one(client, asyncio.Semaphore(1), a_run(), "m"))
        assert row["notes"] == "ValueError: bad shape"

    def test_failed_attempts_increment_the_error_counter(self) -> None:
        from altered_states.metrics import REGISTRY

        client = FakeClient(errors=[RuntimeError("x")] * run_eval.RETRY_ATTEMPTS)
        asyncio.run(run_eval.run_one(client, asyncio.Semaphore(1), a_run(), "m"))
        assert REGISTRY.counter_value("llm_calls", status="error", substance="lsd") == run_eval.RETRY_ATTEMPTS

    def test_system_prompt_embeds_the_cycle_phase(self) -> None:
        client = FakeClient()
        asyncio.run(run_eval.run_one(client, asyncio.Semaphore(1), a_run("lsd", exchange=5), "m"))
        system_text = client.messages.calls[0]["system"][0]["text"]
        assert "peak" in system_text
        assert "lsd" in system_text


class TestExecuteRuns:
    def _run(self, tmp_path: Path) -> tuple[int, Path, list[dict[str, Any]]]:
        out = tmp_path / "responses.jsonl"
        code = asyncio.run(run_eval.execute_runs([a_run(), a_run("mdma")], 2, "m", out))
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        return code, out, rows

    def test_all_runs_are_written_as_jsonl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("run_eval.anthropic.AsyncAnthropic", FakeClient)
        code, out_path, rows = self._run(tmp_path)
        assert code == 0
        assert out_path.exists()
        assert len(rows) == 2
        assert {row["substance"] for row in rows} == {"lsd", "mdma"}

    def test_any_error_makes_the_exit_code_nonzero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("run_eval.anthropic.AsyncAnthropic", lambda: FakeClient(errors=[RuntimeError("x")] * 6))
        code, _, rows = self._run(tmp_path)
        assert code == 1
        assert all(row["score"] == "error" for row in rows)

    def test_completion_is_logged_with_totals(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("run_eval.anthropic.AsyncAnthropic", FakeClient)
        self._run(tmp_path)
        events = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
        complete = next(event for event in events if event["event"] == "eval.complete")
        assert complete["runs"] == 2
        assert complete["errors"] == 0


class TestCli:
    def test_defaults_match_the_documented_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["run_eval.py"])
        captured: dict[str, Any] = {}

        async def capture(args: argparse.Namespace) -> int:
            captured.update(vars(args))
            return 0

        monkeypatch.setattr(run_eval, "main_async", capture)
        assert run_eval.main() == 0
        assert captured["model"] == "claude-opus-4-7"
        assert captured["concurrency"] == 8
        assert captured["exchange"] == 1
        assert captured["substances"] == "all"

    def test_dry_run_needs_no_api_key(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["run_eval.py", "--dry-run", "--substances", "lsd"])
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert run_eval.main() == 0
        out = capsys.readouterr().out
        assert "-- DRY RUN --" in out
        assert "onset" in out

    def test_missing_api_key_exits_with_code_two(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["run_eval.py", "--substances", "lsd"])
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert run_eval.main() == 2

    def test_output_path_defaults_to_a_dated_file(self, tmp_path: Path) -> None:
        args = argparse.Namespace(out=None, model="claude-test")
        path = run_eval.resolve_output(args)
        assert path.name.startswith("responses-")
        assert path.name.endswith("-claude-test.jsonl")

    def test_explicit_output_path_is_used(self) -> None:
        args = argparse.Namespace(out="tests/responses/explicit.jsonl", model="m")
        assert run_eval.resolve_output(args).name == "explicit.jsonl"

    def test_output_directory_is_created(self, tmp_path: Path) -> None:
        args = argparse.Namespace(out=str(tmp_path / "nested" / "dir" / "r.jsonl"), model="m")
        assert run_eval.resolve_output(args).parent.is_dir()

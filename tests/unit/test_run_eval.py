"""Unit tests for the DeepSeek/OpenAI-SDK shaped eval runner.

All fixtures are recorded in-memory objects shaped like the OpenAI SDK
response tree — no network is ever touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import run_eval


class FakeMessage:
    def __init__(self, text: str, reasoning: str | None = None) -> None:
        self.content = text
        self.reasoning_content = reasoning


class FakeUsage:
    def __init__(self, prompt_tokens: int = 111, completion_tokens: int = 222) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class FakeChoice:
    def __init__(self, message: FakeMessage, finish_reason: str = "stop") -> None:
        self.message = message
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, choices: list[FakeChoice], usage: FakeUsage | None = None) -> None:
        self.choices = choices
        self.usage = usage if usage is not None else FakeUsage()


class FakeCompletions:
    def __init__(
        self,
        responses: list[FakeResponse] | None = None,
        errors: list[BaseException] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses or [])
        self._errors = list(errors or [])

    async def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if self._errors:
            raise self._errors.pop(0)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = completions


@pytest.fixture()
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("run_eval.asyncio.sleep", fake_sleep)
    return slept


def a_run(substance: str = "lsd", exchange: int = 1) -> run_eval.EvalRun:
    return run_eval.EvalRun(
        substance, "medium", {"id": "p1", "text": "what changes first?", "category": "baseline"}, exchange
    )


def run_async(coro: Any) -> Any:
    return asyncio.run(coro)


class TestMakeClient:
    def test_custom_base_url_and_key_are_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        class Spy:
            def __init__(self, **kwargs: Any) -> None:
                captured.update(kwargs)

        import openai

        monkeypatch.setattr(openai, "AsyncOpenAI", Spy)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        run_eval.make_client()
        assert captured["base_url"] == "https://api.deepseek.com/v1"
        assert captured["api_key"] == "sk-test"

    def test_openrouter_key_alone_is_never_enough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        with pytest.raises(RuntimeError) as excinfo:
            run_eval.make_client()
        assert "DEEPSEEK_API_KEY" in str(excinfo.value)


class TestAttempt:
    def test_response_fields_are_recorded(self) -> None:
        completions = FakeCompletions(
            responses=[
                FakeResponse(
                    [FakeChoice(FakeMessage("a response of substantial prose length." * 20))],
                    FakeUsage(50, 321),
                )
            ]
        )
        client = FakeClient(completions)
        row = run_async(run_eval._attempt(client, a_run(), "deepseek-chat", "system prompt"))
        assert row["response"] is not None and row["response"].startswith("a response")
        assert row["model"] == "deepseek-chat"
        assert row["stop_reason"] == "stop"
        assert row["reasoning_content"] is None
        assert row["usage"] == {
            "output_tokens": 321,
            "total_tokens": 371,
            "prompt_tokens": 50,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }

    def test_request_targets_the_chat_completions_endpoint(self) -> None:
        completions = FakeCompletions(
            responses=[FakeResponse([FakeChoice(FakeMessage("a response of substantial prose length." * 20))])]
        )
        client = FakeClient(completions)
        run_async(run_eval._attempt(client, a_run(), "deepseek-chat", "SYSTEM"))
        call = completions.calls[0]
        assert call["model"] == "deepseek-chat"
        assert [m["role"] for m in call["messages"]] == ["system", "user"]
        assert call["messages"][0]["content"] == "SYSTEM"
        assert "cache_control" not in json.dumps(call)

    def test_reasoning_content_is_recorded_but_never_mistaken_for_content(self) -> None:
        reasoning = "step one, step two, step three and more reasoning to fill the budget"
        completions = FakeCompletions(
            responses=[
                FakeResponse(
                    [FakeChoice(FakeMessage("the final prose answer, roundly stated and substantive", reasoning))],
                    FakeUsage(900, 1200),
                )
            ]
        )
        row = run_async(run_eval._attempt(FakeClient(completions), a_run(), "deepseek-v4-pro", "SYSTEM"))
        assert row["response"] == "the final prose answer, roundly stated and substantive"
        assert row["reasoning_content"] == reasoning

    def test_empty_content_with_reasoning_raises_never_persists(self) -> None:
        completions = FakeCompletions(
            responses=[FakeResponse([FakeChoice(FakeMessage("", "all reasoning no prose"), "length")])]
        )
        with pytest.raises(RuntimeError) as excinfo:
            run_async(run_eval._attempt(FakeClient(completions), a_run(), "deepseek-v4-pro", "SYSTEM"))
        assert "empty content" in str(excinfo.value)


class TestRunOne:
    def test_successful_run_returns_the_row(self) -> None:
        completions = FakeCompletions(
            responses=[FakeResponse([FakeChoice(FakeMessage("an answer of full prose substance. " * 20))])]
        )
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["response"] is not None
        assert row["score"] is None

    def test_short_response_retries_with_a_bigger_budget_then_succeeds(self, no_sleep: list[float]) -> None:
        tiny = FakeResponse([FakeChoice(FakeMessage("too short"))])
        big = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[tiny, big])
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["score"] is None
        budgets = [call["max_tokens"] for call in completions.calls]
        assert budgets[1] > budgets[0]

    def test_exhausted_retries_return_an_error_row(self, no_sleep: list[float]) -> None:
        completions = FakeCompletions(errors=[RuntimeError("boom")] * 10)
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["response"] is None
        assert row["score"] == "error"
        assert "RuntimeError" in (row["notes"] or "")

    def test_transient_error_backs_off_and_retries(self, no_sleep: list[float]) -> None:
        completions = FakeCompletions(
            errors=[RuntimeError("transient")],
            responses=[FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])],
        )
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["score"] is None
        assert no_sleep == [2.0]

    def test_system_prompt_embeds_the_cycle_phase(self) -> None:
        completions = FakeCompletions(
            responses=[FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])]
        )
        run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(exchange=5), "deepseek-chat"))
        assert "peak" in completions.calls[0]["messages"][0]["content"]


class TestExecuteRuns:
    def test_all_runs_are_written_as_jsonl(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        stub_response = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[stub_response] * 2)
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = tmp_path / "responses.jsonl"
        ret = run_async(run_eval.execute_runs([a_run("lsd"), a_run("mdma")], 2, "deepseek-chat", out_path))
        assert ret == 0
        lines = out_path.read_text().splitlines()
        assert len(lines) == 2
        rows = [json.loads(line) for line in lines]
        assert {r["substance"] for r in rows} == {"lsd", "mdma"}
        assert all(r["model"] == "deepseek-chat" for r in rows)

    def test_any_error_makes_the_exit_code_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        completions = FakeCompletions(
            errors=[RuntimeError("boom")] * 10,
        )
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = tmp_path / "responses.jsonl"
        ret = run_async(run_eval.execute_runs([a_run("lsd"), a_run("mdma")], 2, "deepseek-chat", out_path))
        assert ret == 1
        rows = [json.loads(line) for line in out_path.read_text().splitlines()]
        assert all(r["score"] == "error" and "RuntimeError" in (r["notes"] or "") for r in rows)


class TestDryRunRows:
    def test_rows_match_real_row_key_set_and_carry_the_marker(self) -> None:
        runs = [a_run("lsd", 1), a_run("mdma", 3)]
        real_keys = set(run_eval.build_row(runs[0], "deepseek-chat", "text")) | {
            "reasoning_content",
            "stop_reason",
            "usage",
        }
        dry = run_eval.dry_run_rows(runs, "deepseek-chat")
        assert set(dry[0]) == (real_keys | {"dry_run"})
        assert all(row["dry_run"] is True for row in dry)
        assert all(row["model"] == "deepseek-chat" for row in dry)
        assert all(isinstance(row["response"], str) and row["response"] for row in dry)
        assert dry[1]["stop_reason"] == "dry_run"

    def test_dry_run_writes_headerless_jsonl(self, tmp_path: Path) -> None:
        out_path = tmp_path / "dry.jsonl"
        ret = run_async(run_eval.dry_run_to_disk([a_run("lsd")], "deepseek-chat", out_path))
        assert ret == 0
        content = out_path.read_text()
        assert content.splitlines()[0].startswith("{")
        row = json.loads(content.splitlines()[0])
        assert row["dry_run"] is True
        assert row["response"].startswith("[DRY-RUN STUB]")


class TestCli:
    def _parse(self, *argv: str) -> argparse.Namespace:
        return run_eval._build_parser().parse_args(list(argv))

    def test_defaults_match_the_documented_values(self) -> None:
        args = self._parse()
        assert args.prompts == "tests/prompts.json"
        assert args.substances == "all"
        assert args.model == "deepseek-chat"
        assert args.concurrency == 8
        assert args.exchange == 1
        assert args.dry_run is False

    def test_dry_run_needs_no_api_key_and_never_builds_a_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        def boom() -> None:
            raise AssertionError("make_client must not be reached on the dry-run path")

        monkeypatch.setattr(run_eval, "make_client", boom)
        args = self._parse("--dry-run", "--substances", "lsd", "--out", str(tmp_path / "d.jsonl"))
        assert run_async(run_eval.main_async(args)) == 0

    def test_missing_deepseek_key_exits_with_code_two(self, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        args = self._parse("--substances", "lsd")
        rc = run_async(run_eval.main_async(args))
        assert rc == 2
        assert "DEEPSEEK_API_KEY" in capsys.readouterr().err

    def test_output_path_defaults_to_a_dated_model_tagged_file(self) -> None:
        path = run_eval.resolve_output(self._parse())
        assert path.parent == run_eval.REPO_ROOT / "tests" / "responses"
        assert "deepseek-chat" in path.name

    def test_explicit_output_path_is_used(self) -> None:
        args = self._parse("--out", "output/evals/run-b.jsonl")
        assert run_eval.resolve_output(args) == run_eval.REPO_ROOT / "output" / "evals" / "run-b.jsonl"

    def test_output_directory_is_created(self, tmp_path: Path) -> None:
        args = self._parse("--out", str(tmp_path / "nested" / "dir" / "run.jsonl"))
        assert run_eval.resolve_output(args).parent.is_dir()

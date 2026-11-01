"""Unit tests for the DeepSeek/OpenAI-SDK shaped eval runner.

All fixtures are recorded in-memory objects shaped like the OpenAI SDK
response tree — no network is ever touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from itertools import islice
from pathlib import Path
from typing import Any

import pytest
import run_eval

from altered_states import eval_budget
from altered_states.metrics import REGISTRY


class FakeMessage:
    def __init__(self, text: str, reasoning: str | None = None) -> None:
        self.content = text
        self.reasoning_content = reasoning


class FakeUsageDetails:
    def __init__(self, reasoning_tokens: int) -> None:
        self.reasoning_tokens = reasoning_tokens


class FakeUsage:
    def __init__(
        self,
        prompt_tokens: int = 111,
        completion_tokens: int = 222,
        reasoning_tokens: int | None = None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        if reasoning_tokens is not None:
            self.completion_tokens_details = FakeUsageDetails(reasoning_tokens)


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
            "completion_tokens": 321,
            "total_tokens": 371,
            "prompt_tokens": 50,
            "reasoning_tokens": 0,
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
                    FakeUsage(900, 1200, reasoning_tokens=1170),
                )
            ]
        )
        row = run_async(run_eval._attempt(FakeClient(completions), a_run(), "deepseek-v4-pro", "SYSTEM"))
        assert row["response"] == "the final prose answer, roundly stated and substantive"
        assert row["reasoning_content"] == reasoning
        # The objective reasoning diagnostic predicate (VAL-EVAL-005):
        # non-zero reasoning_content_chars int, plus usage.reasoning_tokens.
        assert row["reasoning_content_chars"] == len(reasoning)
        assert isinstance(row["reasoning_content_chars"], int) and row["reasoning_content_chars"] > 0
        assert row["usage"]["reasoning_tokens"] == 1170
        # Semantic usage keys stay OpenAI-shaped, never Anthropic-shaped
        # (VAL-EVAL-005: no cache_read/cache_creation Anthropic key names).
        assert set(row["usage"]) == {
            "completion_tokens",
            "total_tokens",
            "prompt_tokens",
            "reasoning_tokens",
        }
        assert "cache_read_input_tokens" not in row["usage"]
        assert "cache_creation_input_tokens" not in row["usage"]

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

    def test_short_response_retries_with_the_capped_budget_then_succeeds(self, no_sleep: list[float]) -> None:
        tiny = FakeResponse([FakeChoice(FakeMessage("too short"))])
        big = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[tiny, big])
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["score"] is None
        # Budget-raise retry, clamped to deepseek-chat's documented output cap.
        budgets = [call["max_tokens"] for call in completions.calls]
        assert budgets[0] == run_eval.DEFAULT_MAX_TOKENS
        assert budgets[1] == run_eval.retry_max_tokens("deepseek-chat")
        assert budgets[1] <= run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-chat"]

    def test_retry_budget_of_the_reasoning_model_lifts_but_never_exceeds_the_cap(self, no_sleep: list[float]) -> None:
        reasoning_lift = FakeResponse(
            [FakeChoice(FakeMessage("a complete, substantive in-character deepseek-v4-pro response. " * 10))]
        )
        tiny = FakeResponse([FakeChoice(FakeMessage("too short"))])
        completions = FakeCompletions(responses=[tiny, reasoning_lift])
        run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-v4-pro"))
        lifted = completions.calls[1]["max_tokens"]
        assert lifted == min(run_eval.DEFAULT_MAX_TOKENS * 4, run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-v4-pro"])
        assert lifted == run_eval.retry_max_tokens("deepseek-v4-pro")

    def test_llm_calls_are_counted_once_per_request_across_a_budget_raise_retry(self, no_sleep: list[float]) -> None:
        """Scrutiny fix: the budget-raise retry must not double-count a call
        (the first attempt was already counted ok; the retry has its own ok
        count, and no error increment for the same request).
        """
        REGISTRY.reset()
        tiny = FakeResponse([FakeChoice(FakeMessage("too short"))])
        big = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[tiny, big])
        run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        counters = REGISTRY.as_dict()["counters"]
        ok = sum(v for k, v in counters.items() if "llm_calls" in k and 'status="ok"' in k)
        error = sum(v for k, v in counters.items() if "llm_calls" in k and 'status="error"' in k)
        # Two actual API requests => two ok counts; zero error counts.
        assert ok == 2
        assert error == 0

    def test_error_row_carries_the_same_key_set_as_success_rows(self, no_sleep: list[float]) -> None:
        """Scrutiny fix: exhausted retries still carry the full row contract
        (reasoning_content / stop_reason / usage = None / None / zero usage)."""
        completions = FakeCompletions(errors=[RuntimeError("boom")] * 10)
        err = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        success_keys = set(run_eval.build_row(a_run(), "deepseek-chat", "text"))
        success_keys -= {"category"}  # deliberate: error rows drop the unused category key
        success_keys |= {"reasoning_content", "reasoning_content_chars", "stop_reason", "usage"}
        assert set(err) == success_keys
        assert err["reasoning_content"] is None
        assert err["stop_reason"] is None
        assert err["usage"] == {
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "reasoning_tokens": 0,
        }
        assert err["response"] is None and err["score"] == "error"

    def test_exhausted_retries_return_an_error_row(self, no_sleep: list[float]) -> None:
        completions = FakeCompletions(errors=[RuntimeError("boom")] * 10)
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-chat"))
        assert row["response"] is None
        assert row["score"] == "error"
        assert "RuntimeError" in (row["notes"] or "")

    def test_reasoning_burnout_retries_with_lifted_budget_then_error_row_never_empty(
        self, no_sleep: list[float]
    ) -> None:
        """VAL-EVAL-006: reasoning exhausts max_tokens on every attempt.

        The persisted row is either a substantive answer or an explicit error
        row naming finish_reason + reasoning tokens — never a silent
        ``response == ""`` with a non-error score.
        """
        burnout = FakeResponse([FakeChoice(FakeMessage("", "all reasoning no prose"), "length")])
        completions = FakeCompletions(responses=[burnout, burnout, burnout, burnout])
        budgets: list[int] = []
        original_create = completions.create

        async def spy_create(**kwargs: Any) -> FakeResponse:
            budgets.append(kwargs["max_tokens"])
            return await original_create(**kwargs)

        completions.create = spy_create  # type: ignore[method-assign]
        row = run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-v4-pro"))
        # The budget was lifted between attempts (budget-raise retry).
        assert len(budgets) == run_eval.RETRY_ATTEMPTS
        assert budgets[1] == run_eval.DEFAULT_MAX_TOKENS * 4
        assert budgets[1] > budgets[0]
        # The persisted row carries a diagnostic, never a silent empty answer.
        assert row["response"] is None
        assert row["score"] == "error"
        assert 'finish_reason="length"' in (row["notes"] or "") or "finish_reason='length'" in (row["notes"] or "")
        assert "reasoning_content_chars=" in (row["notes"] or "")
        assert row["response"] != ""  # the asserted-dead branch stays dead

    def test_retry_log_carries_finish_reason(self, no_sleep: list[float], capsys: Any) -> None:
        burnout = FakeResponse([FakeChoice(FakeMessage("", "chain of thought only"), "length")])
        completions = FakeCompletions(responses=[burnout])
        run_async(run_eval.run_one(FakeClient(completions), asyncio.Semaphore(1), a_run(), "deepseek-v4-pro"))
        stderr = capsys.readouterr().err
        retry_lines = [ln for ln in stderr.splitlines() if "eval.retry" in ln]
        assert retry_lines, "expected an eval.retry log line"
        logged = json.loads(retry_lines[0])
        assert logged["finish_reason"] == "length"
        assert logged["error"] == "RuntimeError"

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
        manifest = eval_budget.build_manifest(
            run_kind="real",
            model="deepseek-chat",
            max_tokens=1000,
            max_requests=2,
            concurrency=2,
            command_line="bin/run_eval.py --out x.jsonl",
            num_runs=2,
        )
        ledger = tmp_path / "ledger.jsonl"
        ret = run_async(
            run_eval.execute_runs([a_run("lsd"), a_run("mdma")], 2, "deepseek-chat", out_path, manifest, ledger)
        )
        assert ret == 0
        lines = out_path.read_text().splitlines()
        assert len(lines) == 2
        rows = [json.loads(line) for line in lines]
        assert {r["substance"] for r in rows} == {"lsd", "mdma"}
        assert all(r["model"] == "deepseek-chat" for r in rows)
        # The run wrote one manifest-annotated real-run ledger entry.
        entries = eval_budget.read_ledger_entries(ledger)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["run_kind"] == "real"
        assert entry["manifest_id"] == manifest["manifest_id"]
        assert entry["actual_cost_usd"] >= 0
        assert eval_budget.ledger_total(ledger) == entry["actual_cost_usd"]

    def test_any_error_makes_the_exit_code_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        completions = FakeCompletions(
            errors=[RuntimeError("boom")] * 10,
        )
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = tmp_path / "responses.jsonl"
        manifest = eval_budget.build_manifest(
            run_kind="real",
            model="deepseek-chat",
            max_tokens=1000,
            max_requests=2,
            concurrency=2,
            command_line="bin/run_eval.py --out x.jsonl",
            num_runs=2,
        )
        ledger = tmp_path / "ledger.jsonl"
        ret = run_async(
            run_eval.execute_runs([a_run("lsd"), a_run("mdma")], 2, "deepseek-chat", out_path, manifest, ledger)
        )
        assert ret == 1
        rows = [json.loads(line) for line in out_path.read_text().splitlines()]
        assert all(r["score"] == "error" and "RuntimeError" in (r["notes"] or "") for r in rows)


class TestManifestHonestyAndSpecKey:
    """Scrutiny follow-ups: manifest records the worst-case retry ceiling;
    the argv-stripping fix has a regression test."""

    def _args(self) -> argparse.Namespace:
        return run_eval._build_parser().parse_args(["--model", "deepseek-v4-pro"])

    def test_manifest_max_tokens_records_the_worst_case_retry_ceiling(self) -> None:
        manifest = run_eval._manifest_for_args(self._args(), 3, "real")
        # Not the first-attempt budget: the lifted, cap-clamped ceiling.
        assert manifest["max_tokens"] == run_eval.retry_max_tokens("deepseek-v4-pro")
        assert manifest["max_tokens"] == min(
            run_eval.DEFAULT_MAX_TOKENS * 4, run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-v4-pro"]
        )
        assert manifest["max_tokens"] > run_eval.DEFAULT_MAX_TOKENS
        assert manifest["max_tokens"] <= run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-v4-pro"]

    def test_chat_manifest_ceiling_is_clamped_to_the_documented_cap(self) -> None:
        args = run_eval._build_parser().parse_args(["--model", "deepseek-chat"])
        manifest = run_eval._manifest_for_args(args, 2, "real")
        assert manifest["max_tokens"] == run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-chat"]
        assert manifest["max_tokens"] <= run_eval.MODEL_OUTPUT_TOKEN_CAP["deepseek-chat"]

    def test_spec_key_strips_the_write_manifest_flag_from_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression for 8db600d: a raw sys.argv with --write-manifest made
        every review-then-run manifest self-reject (exit 3, dead flow)."""
        argv = [
            "bin/run_eval.py",
            "--write-manifest",
            "--substances",
            "lsd",
            "--out",
            "/tmp/spec.jsonl",
        ]
        monkeypatch.setattr(sys, "argv", argv)
        scored = run_eval._manifest_for_args(self._args(), 1, "real")["spec_key"]
        monkeypatch.setattr(sys, "argv", [a for a in argv if a != "--write-manifest"])
        reviewed = run_eval._manifest_for_args(self._args(), 1, "real")["spec_key"]
        assert scored == reviewed

    def test_retry_max_tokens_refuses_an_unknown_model(self) -> None:
        with pytest.raises(eval_budget.ManifestError, match="output cap"):
            run_eval.retry_max_tokens("gpt-5")


class TestCrashLedgerPersistence:
    def test_crash_mid_run_appends_an_annotated_partial_ledger_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scrutiny fix: a crash after N billed API calls must not lose them
        from the cumulative ledger. The finally block appends a partial,
        manifest-annotated entry with the usage counted so far."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        stub = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[stub, stub])
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = tmp_path / "crash.jsonl"
        manifest = eval_budget.build_manifest(
            run_kind="real",
            model="deepseek-chat",
            max_tokens=1000,
            max_requests=6,
            concurrency=2,
            command_line="bin/run_eval.py --out crash.jsonl",
            num_runs=2,
        )
        ledger = tmp_path / "spend-ledger.jsonl"
        # Simulate the crash right after the first row is processed: the
        # completion iterator yields row one, then raise.
        orig_as_completed = asyncio.as_completed

        class OneThenCrash:
            def __init__(self, iterable: Any) -> None:
                self.remaining = list(islice(iter(iterable), 2))

            def __iter__(self) -> Any:
                yield from self.remaining
                raise RuntimeError("simulated crash after the first billed row")

        monkeypatch.setattr(asyncio, "as_completed", lambda tasks: OneThenCrash(orig_as_completed(tasks)))
        with pytest.raises(RuntimeError, match="simulated crash"):
            run_async(
                run_eval.execute_runs(
                    [a_run("lsd", 1), a_run("mdma", 5), a_run("psilocybin", 1)],
                    1,
                    "deepseek-chat",
                    out_path,
                    manifest,
                    ledger,
                )
            )
        entries = eval_budget.read_ledger_entries(ledger)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["run_kind"] == "real"
        assert entry["manifest_id"] == manifest["manifest_id"]
        assert entry["partial"] is True
        # The first row's billed usage reached the ledger, not zero.
        assert entry["prompt_tokens"] > 0 and entry["output_tokens"] > 0
        assert entry["actual_cost_usd"] > 0
        # Annotated entries stay chargeable toward the cap.
        assert eval_budget.ledger_total(ledger) > 0

    def test_completed_run_ledger_entry_is_not_marked_partial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        stub = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[stub, stub])
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = tmp_path / "ok.jsonl"
        manifest = eval_budget.build_manifest(
            run_kind="real",
            model="deepseek-chat",
            max_tokens=1000,
            max_requests=2,
            concurrency=2,
            command_line="bin/run_eval.py --out ok.jsonl",
            num_runs=2,
        )
        ledger = tmp_path / "spend-ledger.jsonl"
        run_async(
            run_eval.execute_runs([a_run("lsd", 1), a_run("mdma", 5)], 2, "deepseek-chat", out_path, manifest, ledger)
        )
        entry = eval_budget.read_ledger_entries(ledger)[0]
        assert "partial" not in entry
        # run_one's per-call accounting from the earlier test still holds.
        assert entry["manifest_id"] == manifest["manifest_id"]

    def test_ledger_output_outside_the_repo_root_carries_an_absolute_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        stub = FakeResponse([FakeChoice(FakeMessage("a complete, substantive in-character response. " * 10))])
        completions = FakeCompletions(responses=[stub])
        monkeypatch.setattr(run_eval, "make_client", lambda: FakeClient(completions))
        out_path = Path("/tmp/val-eval-abs-007.jsonl")
        manifest = eval_budget.build_manifest(
            run_kind="real",
            model="deepseek-chat",
            max_tokens=1000,
            max_requests=1,
            concurrency=1,
            command_line="bin/run_eval.py --out /tmp/x.jsonl",
            num_runs=1,
        )
        ledger = tmp_path / "spend-ledger.jsonl"
        run_async(run_eval.execute_runs([a_run("lsd", 1)], 1, "deepseek-chat", out_path, manifest, ledger))
        # Not a useless ../../.. relative path: an absolute path.
        entry = eval_budget.read_ledger_entries(ledger)[0]
        assert entry["output"].startswith("/tmp/")
        assert abs(eval_budget.ledger_total(ledger)) >= 0


class TestDryRunRows:
    def test_rows_match_real_row_key_set_and_carry_the_marker(self) -> None:
        runs = [a_run("lsd", 1), a_run("mdma", 3)]
        real_keys = set(run_eval.build_row(runs[0], "deepseek-chat", "text")) | {
            "reasoning_content",
            "reasoning_content_chars",
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

    def test_missing_deepseek_key_exits_with_code_two(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        args = self._parse("--substances", "lsd", "--out", str(tmp_path / "key.jsonl"))
        self._seed_manifest(args, tmp_path, monkeypatch)
        rc = run_async(run_eval.main_async(args))
        assert rc == 2
        assert "DEEPSEEK_API_KEY" in capsys.readouterr().err

    @staticmethod
    def _boom_client() -> None:
        raise AssertionError("no client must be constructed on a gated real-run path")

    def test_real_run_without_manifest_is_refused_with_code_two(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        """Manifest-before-run (VAL-EVAL-012): no sidecar, no run."""
        monkeypatch.setattr(run_eval, "make_client", TestCli._boom_client)
        monkeypatch.setattr(eval_budget, "REPO_LEDGER_PATH", tmp_path / "spend-ledger.jsonl")
        args = self._parse("--substances", "lsd", "--out", str(tmp_path / "nomanifest.jsonl"))
        rc = run_async(run_eval.main_async(args))
        assert rc == 2
        assert "manifest" in capsys.readouterr().err.lower()
        assert not (tmp_path / "nomanifest.jsonl").exists()

    def test_write_manifest_writes_sidecar_and_never_calls_the_api(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setattr(run_eval, "make_client", TestCli._boom_client)
        args = self._parse("--write-manifest", "--substances", "lsd", "--out", str(tmp_path / "spend.jsonl"))
        rc = run_async(run_eval.main_async(args))
        assert rc == 0
        sidecar = tmp_path / "spend.manifest.json"
        assert sidecar.exists()
        manifest = eval_budget.load_manifest(sidecar)
        assert manifest["run_kind"] == "real"
        assert manifest["total_cap_usd"] == eval_budget.TOTAL_CAP_USD
        assert manifest["estimated_cost_usd"] <= manifest["total_cap_usd"]
        assert "REVIEW" in capsys.readouterr().out

    def test_real_run_refused_when_ledger_would_breach_the_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        monkeypatch.setattr(run_eval, "make_client", TestCli._boom_client)
        ledger = tmp_path / "spend-ledger.jsonl"
        monkeypatch.setattr(eval_budget, "REPO_LEDGER_PATH", ledger)
        # Pretend a prior manifest-annotated real run already burned $4.99.
        eval_budget.append_ledger(
            ledger,
            {
                "manifest_id": "oldrun0001",
                "run_kind": "real",
                "model": "deepseek-chat",
                "actual_cost_usd": eval_budget.TOTAL_CAP_USD - 0.01,
                "prompt_tokens": 1,
                "output_tokens": 1,
                "output": "tests/responses/old.jsonl",
            },
        )
        args = self._parse("--substances", "lsd", "--out", str(tmp_path / "over.jsonl"))
        self._seed_manifest(args, tmp_path, monkeypatch)
        rc = run_async(run_eval.main_async(args))
        assert rc == 3
        assert not (tmp_path / "over.jsonl").exists()
        assert len(eval_budget.chargeable_ledger_entries(ledger)) == 1

    def _seed_manifest(
        self, args: argparse.Namespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None = None
    ) -> Path:
        """Write a valid pre-reviewed manifest for this exact CLI invocation.

        ``monkeypatch`` (when given) also points the cumulative-spend gate at
        an empty tmp ledger so tests never read the repo's real ledger.
        """
        if monkeypatch is not None:
            monkeypatch.setattr(eval_budget, "REPO_LEDGER_PATH", tmp_path / "spend-ledger.jsonl")
        runs_len = len(run_eval.load_prompts(run_eval.REPO_ROOT / args.prompts))
        manifest = run_eval._manifest_for_args(args, runs_len, "real")
        eval_budget.validate_manifest(manifest)
        out_path = run_eval.resolve_output(args)
        out_path.with_name(out_path.stem + ".manifest.json").write_text(json.dumps(manifest, indent=2))
        return out_path

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

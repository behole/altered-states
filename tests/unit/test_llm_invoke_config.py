"""Key/endpoint resolution priorities for the temporal-lab call surface.

These are sentinel tests: every key value below is FAKE and non-secret; no
test reads the real repo-root `.env`. They pin the contract that an ambient
OPENROUTER_API_KEY must never silently reroute the lab away from DeepSeek
(VAL-EVAL-008), while explicit LLM_BASE_URL/LLM_API_KEY overrides still win,
and that keys load from the root `.env` convention with secrets redacted in
logs (VAL-EVAL-009).
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any, ClassVar

import pytest

# FAKE, non-secret sentinel values. Shaped like real keys so the redaction
# rules are exercised, never an actual credential.
DEEPSEEK_SENTINEL = "sk-fake-deepseek-test-value"
OPENROUTER_SENTINEL = "sk-or-fake-openrouter-test-value"

DEEPSEEK_URL = "https://api.deepseek.com/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"

import llm_invoke  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_real_env_paths(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point both real .env paths at nonexistent tmp files for every test.

    Importing llm_invoke runs its import-time _load_dotenv(), which loads the
    real repo-root `.env` into the process env; this fixture neutralizes that
    for anything that re-loads during a test, and no assertions ever read the
    real key value.
    """
    monkeypatch.setattr(llm_invoke, "ROOT_ENV_PATH", tmp_path / "does-not-exist.env")
    monkeypatch.setattr(llm_invoke, "LOCAL_ENV_PATH", tmp_path / "does-not-exist-local.env")


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Replace the openai SDK with a stub that records constructor kwargs."""

    class RecordingOpenAI:
        kwargs: ClassVar[dict[str, Any]] = {}

        def __init__(self, **kwargs: Any) -> None:
            RecordingOpenAI.kwargs = kwargs
            self.api_key = kwargs.get("api_key")
            self.base_url = kwargs.get("base_url")

    stub = types.ModuleType("openai")
    stub.OpenAI = RecordingOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", stub)
    return RecordingOpenAI


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("TEMPORAL_LAB_MODEL", raising=False)


class TestDeepSeekBeatsAmbientOpenRouter:
    """The ambient-OpenRouter trap: a stray OPENROUTER_API_KEY must lose."""

    def test_default_base_url_is_deepseek_with_polluted_ambient_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK_SENTINEL)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)

        assert llm_invoke._default_base_url("deepseek-v4-pro") == DEEPSEEK_URL
        assert llm_invoke._default_base_url("deepseek-chat") == DEEPSEEK_URL

    def test_resolve_config_yields_deepseek_base_url_with_polluted_ambient_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK_SENTINEL)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)
        monkeypatch.delenv("LLM_MODEL", raising=False)

        _, base_url, _ = llm_invoke._resolve_config(None)
        assert base_url == DEEPSEEK_URL
        assert base_url != OPENROUTER_URL

    def test_client_api_key_resolves_to_the_deepseek_env_var(
        self, monkeypatch: pytest.MonkeyPatch, fake_openai: Any
    ) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK_SENTINEL)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)

        client = llm_invoke._make_client(DEEPSEEK_URL)
        # Asserted against the recorded constructor kwargs — the real key
        # value is never read or printed by this test.
        assert fake_openai.kwargs["api_key"] == DEEPSEEK_SENTINEL
        assert fake_openai.kwargs["base_url"] == DEEPSEEK_URL
        assert client.api_key == DEEPSEEK_SENTINEL

    def test_missing_keys_raise_an_actionable_error(self, monkeypatch: pytest.MonkeyPatch, fake_openai: type) -> None:
        _clear_llm_env(monkeypatch)
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            llm_invoke._make_client(DEEPSEEK_URL)


class TestExplicitOverridesStillWin:
    """LLM_BASE_URL / LLM_API_KEY are deliberate recordings and outrank both."""

    def test_explicit_base_url_beats_deepseek_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK_SENTINEL)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)
        monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")

        _, base_url, _ = llm_invoke._resolve_config(None)
        assert base_url == "https://api.groq.com/openai/v1"

    def test_explicit_api_key_beats_deepseek_in_the_client(
        self, monkeypatch: pytest.MonkeyPatch, fake_openai: Any
    ) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK_SENTINEL)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)
        monkeypatch.setenv("LLM_API_KEY", "gsk-fake-explicit-override")

        llm_invoke._make_client(DEEPSEEK_URL)
        assert fake_openai.kwargs["api_key"] == "gsk-fake-explicit-override"


class TestDocumentedFallback:
    """Without a DeepSeek key the documented OpenRouter fallback still works."""

    def test_openrouter_key_alone_resolves_openrouter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clear_llm_env(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", OPENROUTER_SENTINEL)
        _, base_url, _ = llm_invoke._resolve_config(None)
        assert base_url == OPENROUTER_URL


class TestRootEnvIsTheSharedKeySource:
    """VAL-EVAL-009: root `.env` wins; secrets stay redacted in log output."""

    def test_key_loads_from_root_env_when_local_is_absent(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_invoke, "ROOT_ENV_PATH", tmp_path / ".env")
        monkeypatch.setattr(llm_invoke, "LOCAL_ENV_PATH", tmp_path / "does-not-exist" / ".env")
        _clear_llm_env(monkeypatch)
        (tmp_path / ".env").write_text(f"DEEPSEEK_API_KEY={DEEPSEEK_SENTINEL}\n")

        llm_invoke._load_dotenv()
        assert os.environ["DEEPSEEK_API_KEY"] == DEEPSEEK_SENTINEL

    def test_root_env_beats_experiment_local_env(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_invoke, "ROOT_ENV_PATH", tmp_path / "root.env")
        monkeypatch.setattr(llm_invoke, "LOCAL_ENV_PATH", tmp_path / "local.env")
        _clear_llm_env(monkeypatch)
        (tmp_path / "root.env").write_text(f"DEEPSEEK_API_KEY={DEEPSEEK_SENTINEL}\n")
        (tmp_path / "local.env").write_text("DEEPSEEK_API_KEY=sk-fake-local-should-lose\n")

        llm_invoke._load_dotenv()
        assert os.environ["DEEPSEEK_API_KEY"] == DEEPSEEK_SENTINEL

    def test_local_env_fallback_used_when_root_env_absent(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_invoke, "ROOT_ENV_PATH", tmp_path / "does-not-exist.env")
        monkeypatch.setattr(llm_invoke, "LOCAL_ENV_PATH", tmp_path / ".env")
        _clear_llm_env(monkeypatch)
        (tmp_path / ".env").write_text(f"DEEPSEEK_API_KEY={DEEPSEEK_SENTINEL}\n")

        llm_invoke._load_dotenv()
        assert os.environ["DEEPSEEK_API_KEY"] == DEEPSEEK_SENTINEL

    def test_log_records_redact_the_key_sentinel(self, lab_root: Any) -> None:
        # A CallRecord whose message contains an sk- shaped secret must carry
        # it redacted into the JSON-lines log it writes.
        try:
            from logger import CallRecord, log_call

            log_call(CallRecord("psilocybin", "deepseek-chat", 10, 10, 0.0, "ok", f"trace {DEEPSEEK_SENTINEL}"))
            log_files = list((lab_root / "logs").glob("????-??-??.log"))
            assert log_files, "log file was not written"
            for line in log_files[0].read_text().splitlines():
                assert DEEPSEEK_SENTINEL not in line, line
        finally:
            # _load_dotenv bypasses monkeypatch's os.environ undo; keep fake
            # sentinels from leaking into the rest of the suite.
            for var in ("DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY", "LLM_BASE_URL"):
                os.environ.pop(var, None)


class TestNoAnthropicRuntimePath:
    """No Anthropic import is reachable from this surface."""

    def test_no_anthropic_reference_in_llm_invoke(self) -> None:
        with open(llm_invoke.__file__) as f:
            source = f.read()
        assert "anthropic" not in source.lower()

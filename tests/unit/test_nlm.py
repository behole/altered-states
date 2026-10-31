"""Unit tests for the notebooklm-mcp HTTP client (no network, no server)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import nlm
import pytest


class FakeResponse:
    """Minimal stand-in for the object ``urllib.request.urlopen`` returns."""

    def __init__(self, body: str, headers: dict[str, str] | None = None) -> None:
        self._body = body.encode()
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = tmp_path / ".nlm-session"
    monkeypatch.setattr(nlm, "STATE_FILE", str(state))
    nlm._req_id[0] = 0
    return state


def install(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> list[Any]:
    """Patch urlopen and return the list of requests it received."""
    seen: list[Any] = []

    def fake_urlopen(request: Any, timeout: int = 0) -> FakeResponse:
        seen.append((request, timeout))
        return response

    monkeypatch.setattr("nlm.urllib.request.urlopen", fake_urlopen)
    return seen


SSE_RESULT = 'event: message\ndata: {"jsonrpc": "2.0", "id": 1, "result": {"ok": true}}\n\n'


class TestSessionState:
    def test_no_state_file_means_no_session_id(self) -> None:
        assert nlm._load_sid() is None

    def test_session_id_round_trips(self, isolated_state: Path) -> None:
        nlm._save_sid("abc-123")
        assert nlm._load_sid() == "abc-123"

    def test_unreadable_state_file_is_treated_as_absent(self, isolated_state: Path) -> None:
        isolated_state.mkdir(parents=True)  # a directory cannot be read as a file
        assert nlm._load_sid() is None


class TestRequestBuilding:
    def test_req_ids_increment_per_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install(monkeypatch, FakeResponse(SSE_RESULT))
        nlm.call("tools/list")
        nlm.call("tools/list")
        assert nlm._req_id[0] == 2

    def test_request_is_a_jsonrpc_post_with_sse_accept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        nlm.call("tools/list", {"cursor": "x"})

        request, timeout = seen[0]
        assert request.get_method() == "POST"
        assert request.full_url == nlm.BASE
        assert request.headers["Content-type"] == "application/json"
        assert "text/event-stream" in request.headers["Accept"]
        assert timeout == 180

        body = json.loads(request.data)
        assert body["method"] == "tools/list"
        assert body["params"] == {"cursor": "x"}
        assert body["jsonrpc"] == "2.0"

    def test_params_are_omitted_when_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        nlm.call("tools/list")
        assert "params" not in json.loads(seen[0][0].data)

    def test_cached_session_id_is_sent(self, monkeypatch: pytest.MonkeyPatch, isolated_state: Path) -> None:
        nlm._save_sid("cached-sid")
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        nlm.call("tools/list")
        assert seen[0][0].headers["Mcp-session-id"] == "cached-sid"

    def test_returned_session_id_is_persisted(self, monkeypatch: pytest.MonkeyPatch, isolated_state: Path) -> None:
        install(monkeypatch, FakeResponse(SSE_RESULT, {"Mcp-Session-Id": "fresh-sid"}))
        nlm.call("initialize")
        assert isolated_state.read_text() == "fresh-sid"

    def test_tool_call_payload_shape(self) -> None:
        assert nlm._tool_call("notebook_list", {}) == {"name": "notebook_list", "arguments": {}}


class TestResponseParsing:
    def test_result_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install(monkeypatch, FakeResponse(SSE_RESULT))
        assert nlm.call("tools/list") == {"ok": True}

    def test_error_is_printed_and_returned(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        body = 'data: {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "nope"}}\n'
        install(monkeypatch, FakeResponse(body))
        assert nlm.call("bogus")["code"] == -32601
        assert "nope" in capsys.readouterr().err

    def test_response_without_data_lines_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        install(monkeypatch, FakeResponse("event: ping\n\n"))
        assert nlm.call("tools/list") is None


class TestPrintResult:
    def test_text_parts_are_printed_without_wrappers(self, capsys: pytest.CaptureFixture[str]) -> None:
        nlm.print_result({"content": [{"type": "text", "text": "hello"}, {"type": "image"}]})
        assert capsys.readouterr().out.strip() == "hello"

    def test_non_mcp_payload_is_pretty_printed(self, capsys: pytest.CaptureFixture[str]) -> None:
        nlm.print_result({"a": 1})
        assert json.loads(capsys.readouterr().out) == {"a": 1}


class TestCommands:
    def test_missing_command_prints_usage_and_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert nlm.main(["nlm.py"]) == 1
        assert "Usage: nlm.py" in capsys.readouterr().out

    def test_unknown_command_prints_usage_and_fails(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert nlm.main(["nlm.py", "nope"]) == 1
        assert "Usage:" in capsys.readouterr().out

    def test_tools_lists_each_name_and_truncates_descriptions(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        payload = {"tools": [{"name": "source_add", "description": "x" * 200}]}
        install(monkeypatch, FakeResponse(f"data: {json.dumps({'result': payload})}\n"))
        assert nlm.main(["nlm.py", "tools"]) == 0
        out = capsys.readouterr().out
        assert "source_add:" in out
        assert "x" * 200 not in out

    def test_call_with_inline_json_arguments(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        seen = install(monkeypatch, FakeResponse('data: {"result": {"content": [{"type": "text", "text": "ok"}]}}\n'))
        assert nlm.main(["nlm.py", "call", "notebook_list", '{"limit": 3}']) == 0
        body = json.loads(seen[0][0].data)
        assert body["params"]["arguments"] == {"limit": 3}
        assert capsys.readouterr().out.strip() == "ok"

    def test_call_without_arguments_defaults_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        nlm.main(["nlm.py", "call", "notebook_list"])
        assert json.loads(seen[0][0].data)["params"]["arguments"] == {}

    def test_add_text_reads_the_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        source = tmp_path / "note.md"
        source.write_text("plant wisdom")
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))

        assert nlm.main(["nlm.py", "add-text", "nb1", "Title", str(source)]) == 0

        arguments = json.loads(seen[0][0].data)["params"]["arguments"]
        assert arguments["notebook_id"] == "nb1"
        assert arguments["source_type"] == "text"
        assert arguments["text"] == "plant wisdom"
        assert arguments["title"] == "Title"

    def test_add_url_sends_a_url_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        assert nlm.main(["nlm.py", "add-url", "nb1", "https://example.org/a"]) == 0
        arguments = json.loads(seen[0][0].data)["params"]["arguments"]
        assert arguments == {"notebook_id": "nb1", "source_type": "url", "url": "https://example.org/a"}

    def test_query_sends_the_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        assert nlm.main(["nlm.py", "query", "nb1", "what is love?"]) == 0
        body = json.loads(seen[0][0].data)
        assert body["params"]["name"] == "notebook_query"
        assert body["params"]["arguments"]["query"] == "what is love?"

    def test_list_and_info_call_their_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        assert nlm.main(["nlm.py", "list"]) == 0
        assert nlm.main(["nlm.py", "info", "nb1"]) == 0
        assert json.loads(seen[0][0].data)["params"]["name"] == "notebook_list"
        assert json.loads(seen[1][0].data)["params"]["arguments"] == {"notebook_id": "nb1"}

    def test_init_sends_protocol_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = install(monkeypatch, FakeResponse(SSE_RESULT))
        assert nlm.main(["nlm.py", "init"]) == 0
        body = json.loads(seen[0][0].data)
        assert body["method"] == "initialize"
        assert body["params"]["protocolVersion"] == "2024-11-05"

    def test_every_command_is_registered(self) -> None:
        assert set(nlm.COMMANDS) == {"init", "tools", "call", "add-text", "add-url", "query", "list", "info"}


def test_module_imports_without_a_network() -> None:
    """Importing the helper must not open a socket or create state."""
    assert isinstance(nlm.BASE, str)
    assert nlm.ALLOWED_SCHEMES == ("http", "https")


class TestUrlValidation:
    def test_http_urls_are_accepted(self) -> None:
        assert nlm._validated_url("http://127.0.0.1:8420/mcp") == "http://127.0.0.1:8420/mcp"

    def test_https_urls_are_accepted(self) -> None:
        assert nlm._validated_url("https://example.org/mcp") == "https://example.org/mcp"

    @pytest.mark.parametrize(
        "url",
        ["file:///etc/passwd", "ftp://example.org/x", "data:text/plain,hi", "/etc/passwd"],
    )
    def test_other_schemes_are_refused(self, url: str) -> None:
        with pytest.raises(ValueError, match="scheme"):
            nlm._validated_url(url)

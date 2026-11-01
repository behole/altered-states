"""Assert the migrated build.py/watch.py log_event events still fire.

The migration moved high-signal output from ``print()`` to
``altered_states.log_utils.log_event()``. These tests record the events so a
silent revert to ``print()`` would fail CI: every recorder also stubs
``print`` to raise, so a fallback back to bare prints can never pass.
"""

from __future__ import annotations

import json
import shutil
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, ".")
import build
import watch


def _print_boom() -> Callable[[], None]:
    """Return a print replacement that fails the test when called."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("output must route through log_event(), not print()")

    return boom


class TestBuildParseFailed:
    def test_unparseable_experiment_logs_build_parse_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[tuple[str, dict[str, object]]] = []

        def recorder(event: str, **fields: object) -> dict[str, object]:
            events.append((event, fields))
            return {"event": event, **fields}

        monkeypatch.setattr(build, "log_event", recorder)
        monkeypatch.setattr("builtins.print", _print_boom())
        monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(tmp_path))

        def raiser(_path: str) -> dict[str, object]:
            raise ValueError("corrupt file")

        monkeypatch.setattr(build, "parse_experiment_md", raiser)
        (tmp_path / "bad.md").write_text("not a valid experiment file")

        assert build.load_experiments() == []
        assert [event for event, _fields in events] == ["build.parse_failed"]
        _event, fields = events[0]
        assert fields["level"] == "WARN"
        assert fields["file"] == "bad.md"
        assert "corrupt file" in str(fields["error"])


class TestWatchBuildSummary:
    def test_successful_build_logs_watch_build_summary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        events: list[tuple[str, dict[str, object]]] = []

        def recorder(event: str, **fields: object) -> dict[str, object]:
            events.append((event, fields))
            return {"event": event, **fields}

        monkeypatch.setattr(watch, "log_event", recorder)
        monkeypatch.setattr("builtins.print", _print_boom())
        monkeypatch.setattr(watch, "SITE_DIR", str(tmp_path))

        (tmp_path / "index.html").write_text("<html></html>")

        def fake_run(_argv: list[str], timeout: int) -> types.SimpleNamespace:
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(watch, "_run", fake_run)

        assert watch.build() is True
        assert [event for event, _fields in events] == ["watch.build_summary"]
        _event, fields = events[0]
        assert fields["status"] == "done"
        assert fields["size_bytes"] == len("<html></html>")
        assert str(fields["output"]) == str(tmp_path / "index.html")


class TestWatchDeployFailed:
    def test_failing_wrangler_deploy_logs_watch_deploy_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        events: list[tuple[str, dict[str, object]]] = []

        def recorder(event: str, **fields: object) -> dict[str, object]:
            events.append((event, fields))
            return {"event": event, **fields}

        monkeypatch.setattr(watch, "log_event", recorder)
        monkeypatch.setattr("builtins.print", _print_boom())
        monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/wrangler")

        def fake_run(_argv: list[str], timeout: int) -> types.SimpleNamespace:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="wrangler exploded")

        monkeypatch.setattr(watch, "_run", fake_run)

        assert watch.deploy() is False
        assert [event for event, _fields in events] == ["watch.deploy_failed"]
        _event, fields = events[0]
        assert fields["level"] == "WARN"
        assert fields["stderr"] == "wrangler exploded"


class TestEventsAreJsonSerializable:
    def test_recorded_events_render_via_log_utils_shape(self) -> None:
        """The recorded events match the shape log_event emits to stderr."""
        import io

        from altered_states.log_utils import log_event

        stream = io.StringIO()
        record = log_event("watch.build_summary", stream=stream, status="done", size_bytes=13)
        assert json.loads(stream.getvalue()) == record

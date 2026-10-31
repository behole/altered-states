"""Tests for watch.py's --serve-only gating and flag surface."""

import http.server
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

sys.path.insert(0, ".")
import watch


@contextmanager
def _exit_after_one_poll() -> Iterator[None]:
    """Make watch_loop raise KeyboardInterrupt on its first poll iteration."""

    def sleep_once(_seconds: float) -> None:
        raise KeyboardInterrupt

    orig_sleep = time.sleep
    time.sleep = sleep_once
    try:
        yield
    finally:
        time.sleep = orig_sleep


def _patch_watcher(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[int]]:
    calls: dict[str, list[int]] = {"build": [], "deploy": []}

    def fake_build() -> bool:
        calls["build"].append(1)
        return True

    def fake_deploy() -> bool:
        calls["deploy"].append(1)
        return True

    monkeypatch.setattr(watch, "build", fake_build)
    monkeypatch.setattr(watch, "deploy", fake_deploy)
    # build_and_deploy stays real so its build-then-deploy wiring is what is
    # exercised; only the terminal subprocess calls are stubbed.
    return calls


class TestServeOnlyLoop:
    def test_serve_only_never_touches_deploy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _patch_watcher(monkeypatch)

        with _exit_after_one_poll():
            watch.watch_loop(serve_only=True)

        assert calls["build"] == [1]
        assert calls["deploy"] == []

    def test_default_loop_deploys_as_before(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = _patch_watcher(monkeypatch)

        with _exit_after_one_poll():
            watch.watch_loop()

        assert calls["build"] == [1]
        assert calls["deploy"] == [1]


class TestFlagSurface:
    def test_help_lists_serve_only_without_starting_the_server(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        started: list[int] = []

        def boom(*_a: object, **_k: object) -> object:
            started.append(1)
            raise AssertionError("--help must not start the server")

        monkeypatch.setattr(http.server, "HTTPServer", boom)
        monkeypatch.setattr(sys, "argv", ["watch.py", "--help"])

        watch.main()

        out = capsys.readouterr()
        assert "--serve-only" in out.out
        assert started == []

    def test_main_splits_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--serve-only reaches watch_loop; default path keeps deploy semantics."""
        seen: list[bool] = []
        calls = _patch_watcher(monkeypatch)

        def fake_watch_loop(serve_only: bool = False) -> None:
            seen.append(serve_only)
            raise KeyboardInterrupt

        class _Boom:
            def __init__(self, *_a: object, **_k: object) -> None:
                pass

            def serve_forever(self) -> None:
                raise AssertionError("flag-parsing test must not serve after the loop returns")

        monkeypatch.setattr(http.server, "HTTPServer", _Boom)
        monkeypatch.setattr(watch, "watch_loop", fake_watch_loop)

        for argv, expect in ((["watch.py", "--serve-only"], True), (["watch.py"], False)):
            monkeypatch.setattr(sys, "argv", argv)
            with pytest.raises(KeyboardInterrupt):
                watch.main()
            assert seen[-1] is expect

        assert calls["deploy"] == []  # no deploy in a single --build-free iteration


class TestFlagParsingHelpers:
    def test_parse_port_still_supports_both_forms(self) -> None:
        assert watch.parse_port(["--port", "9000"]) == 9000
        assert watch.parse_port(["--port=9001"]) == 9001
        assert watch.parse_port(["--serve-only"]) == 8765

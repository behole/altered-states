"""Tests for watch.py's --serve-only gating, flag surface, and threaded server."""

import http.server
import socket
import sys
import threading
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

        monkeypatch.setattr(watch, "make_server", boom)
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

        monkeypatch.setattr(watch, "make_server", lambda _port: _Boom())
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


class TestThreadedServe:
    """A wedged client must not block other requests (the 2026-10-31 incident)."""

    def test_make_server_is_threading_with_daemon_threads(self) -> None:
        server = watch.make_server(0)
        try:
            assert isinstance(server, http.server.ThreadingHTTPServer)
            assert server.daemon_threads is True
            assert server.RequestHandlerClass is watch.SiteHandler
        finally:
            server.server_close()

    def test_wedged_request_does_not_block_later_requests(self) -> None:
        """One half-open connection must not stop the next request from being served."""
        server = watch.make_server(0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Wedge the server: open a connection and send an incomplete HTTP
            # request, never closing it. A single-threaded HTTPServer stalls
            # here and every later request times out (curl 000 for minutes).
            wedged = socket.create_connection(("127.0.0.1", port), timeout=5)
            wedged.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n")

            # While the wedge is still open, an independent full request must
            # be served promptly.
            client = socket.create_connection(("127.0.0.1", port), timeout=5)
            client.settimeout(5)
            client.sendall(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            response = b""
            while b"\r\n" not in response:
                chunk = client.recv(4096)
                assert chunk, "no response while another connection was open"
                response += chunk
            client.close()
            assert response[:12] in (b"HTTP/1.0 200", b"HTTP/1.1 200", b"HTTP/1.0 30", b"HTTP/1.1 30")
        finally:
            wedged.close()
            server.shutdown()  # serve_forever must stop cleanly
            server.server_close()
            thread.join(timeout=5)
        assert not thread.is_alive()

    def test_shutdown_is_clean_even_with_backend_handlers_running(self) -> None:
        """daemon_threads=True: shutdown exits without joining live handlers."""
        server = watch.make_server(0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        # Fire one request-blob handler then immediately request shutdown;
        # the in-flight handler thread is a daemon and must not block exit.
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        client.settimeout(5)
        client.sendall(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\n\r\n")
        client.recv(1)  # handler has been picked up and started
        client.close()

        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()

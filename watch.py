#!/usr/bin/env python3
"""
watch.py — Watch journal and experiment directories, auto-rebuild site on change.

Usage:
  python3 watch.py                # watch + rebuild + deploy + serve on :8765
  python3 watch.py --serve-only   # watch + rebuild + serve, never deploy
  python3 watch.py --build        # one-shot build only (no watcher)
  python3 watch.py --port 9000    # custom port
  python3 watch.py --help         # show usage

Log-event migration note (repo rule 3):
  All high-signal output (deploy start/failure/skip, build warnings and
  summary, serve start/stop, watcher lifecycle) routes through
  ``altered_states.log_utils.log_event`` (JSON to stderr, redacted).
  Surviving bare ``print()`` calls in this file: one (the ``--help`` usage
  text, which is output formatting, not high-signal logging).
"""

import contextlib
import http.server
import os
import shutil
import signal

# The watcher's entire job is to run two fixed local commands (build.py and
# wrangler) with a literal argv and no shell.
import subprocess  # nosec B404
import sys
import threading
import time
from types import FrameType
from typing import Any, NoReturn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from altered_states.log_utils import log_event

BASE = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE, "site")
WATCH_DIRS = [
    os.path.join(BASE, "experiments", "temporal-lab", "runtime", "journals"),
    os.path.join(BASE, "experiments", "same-prompt", "output"),
]

# Extensions to watch
WATCH_EXTS = {".json", ".md", ".txt"}

# Debounce: don't rebuild more often than this
MIN_INTERVAL = 3.0
POLL_INTERVAL = 2.0

# How many changed filenames to list before collapsing into "... and N more".
PREVIEW_CHANGE_COUNT = 5


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess[str] | None:
    """Run a fixed local command. Returns None when the executable is missing.

    The only processes this repo starts are its own build script (via
    ``sys.executable``) and the ``wrangler`` CLI, both with a literal argv and
    no shell, so there is no interpolation of untrusted input here.
    """
    try:
        # Fixed argv with a resolved executable path and no shell involved.
        return subprocess.run(  # nosec B603
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        log_event("watch.skipped", level="WARN", reason="not_installed", cmd=argv[0])
        return None
    except subprocess.TimeoutExpired:
        log_event("watch.skipped", level="WARN", reason="timeout", cmd=argv[0], timeout=timeout)
        return None


def deploy() -> bool:
    """Deploy to Cloudflare Pages and return True on success."""
    wrangler = shutil.which("wrangler")
    if wrangler is None:
        log_event("watch.deploy_skipped", level="WARN", reason="wrangler not installed")
        return False
    result = _run(
        [wrangler, "pages", "deploy", SITE_DIR, "--project-name", "altered-states", "--commit-dirty=true"],
        timeout=60,
    )
    if result is None:
        return False
    if result.returncode != 0:
        log_event("watch.deploy_failed", level="WARN", stderr=result.stderr)
        return False
    for line in result.stdout.strip().split("\n"):
        if "Success!" in line or "Deployment complete!" in line:
            log_event("watch.deploy_complete", details=line)
    return True


def build_and_deploy() -> bool:
    """Build site and deploy to Cloudflare Pages."""
    if not build():
        return False
    log_event("watch.deploy_start", target="Cloudflare Pages")
    return deploy()


class SiteHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from SITE_DIR without chdir."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=SITE_DIR, **kwargs)


def build() -> bool:
    """Run build.py and return True on success."""
    result = _run([sys.executable, os.path.join(BASE, "build.py")], timeout=30)
    if result is None:
        return False
    if result.returncode != 0:
        log_event("watch.build_failed", level="WARN", stderr=result.stderr)
        return False
    output_path = os.path.join(SITE_DIR, "index.html")
    size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    log_event(
        "watch.build_summary",
        output=output_path,
        size_bytes=size,
        status="done",
    )
    return True


def get_snapshot() -> dict[str, float]:
    """Get a dict of {path: mtime} for all watched files."""
    snapshot: dict[str, float] = {}
    for watch_dir in WATCH_DIRS:
        if not os.path.exists(watch_dir):
            continue
        for root, _dirs, files in os.walk(watch_dir):
            for f in files:
                if os.path.splitext(f)[1].lower() in WATCH_EXTS:
                    path = os.path.join(root, f)
                    with contextlib.suppress(OSError):
                        snapshot[path] = os.path.getmtime(path)
    return snapshot


def changed_paths(snapshot: dict[str, float], current: dict[str, float]) -> list[str]:
    """Return paths that were added, modified, or deleted since `snapshot`."""
    changed = [path for path, mtime in current.items() if snapshot.get(path) != mtime]
    changed.extend(f"{path} (deleted)" for path in snapshot if path not in current)
    return changed


def watch_loop(serve_only: bool = False) -> None:
    """Main watch loop. Blocks forever.

    With ``serve_only=True`` the loop rebuilds but never calls deploy(): the
    only deploy/wrangler call sites in this module (``deploy()`` and
    ``build_and_deploy()``) are unreachable from the serve-only branch.
    """
    log_event(
        "watch.start",
        journals_dir=WATCH_DIRS[0],
        experiments_dir=WATCH_DIRS[1],
        serve_only=serve_only,
        note="Press Ctrl+C to stop",
    )

    # Initial build + deploy
    log_event("watch.initial_build", note="starting")
    if serve_only:
        build()
    else:
        build_and_deploy()

    last_build_time = time.time()
    snapshot = get_snapshot()
    log_event("watch.tracking", files=len(snapshot))

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            current = get_snapshot()
            changed = changed_paths(snapshot, current)
            if not changed:
                continue

            # Debounce
            now = time.time()
            if now - last_build_time < MIN_INTERVAL:
                snapshot = current
                continue

            ts = time.strftime("%H:%M:%S")
            names = [os.path.basename(c) for c in changed[:PREVIEW_CHANGE_COUNT]]
            if len(changed) > PREVIEW_CHANGE_COUNT:
                names.append(f"... and {len(changed) - PREVIEW_CHANGE_COUNT} more")
            log_event("watch.change_detected", at=ts, count=len(changed), files=names)

            # Deploy is not attempted in serve-only mode: rebuild locally only.
            okay = build() if serve_only else build_and_deploy()
            if okay:
                last_build_time = now
                log_event("watch.rebuild_ok")
            else:
                retry_note = (
                    "build failed, will retry on next change"
                    if serve_only
                    else "build/deploy failed, will retry on next change"
                )
                log_event("watch.rebuild_retry", level="WARN", note=retry_note)

            snapshot = current

    except KeyboardInterrupt:
        log_event("watch.stopped", note="Stopped watching")


def parse_port(args: list[str], default: int = 8765) -> int:
    """Read `--port <n>` / `--port=<n>` from argv, falling back to `default`."""
    for i, arg in enumerate(args):
        if arg.startswith("--port="):
            raw_port = arg.partition("=")[2]
            return int(raw_port) if raw_port.isdigit() else default
        if arg == "--port" and i + 1 < len(args) and args[i + 1].isdigit():
            return int(args[i + 1])
    return default


USAGE = """usage:
  python3 watch.py [--serve-only] [--build] [--port <n>]

commands:
  python3 watch.py                watch, rebuild, deploy, and serve on :8765
  python3 watch.py --serve-only   watch, rebuild, and serve; never deploy
  python3 watch.py --build        one-shot build only (no watcher, no serve)
  python3 watch.py --port 9000    custom port
  python3 watch.py --help         show this help
"""


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        # Usage output is intentionally a plain print, not a log_event.
        print(USAGE, file=sys.stdout)
        return

    port = parse_port(args)

    if "--build" in args:
        build_and_deploy()
        return

    serve_only = "--serve-only" in args

    # Start HTTP server in background thread
    server = http.server.HTTPServer(("127.0.0.1", port), SiteHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    log_event("watch.serving", url=f"http://localhost:{port}", port=port, host="127.0.0.1", lifecycle="start")

    def shutdown(_sig: int, _frame: FrameType | None) -> NoReturn:
        log_event("watch.serving", url=f"http://localhost:{port}", port=port, host="127.0.0.1", lifecycle="stop")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    watch_loop(serve_only=serve_only)


if __name__ == "__main__":
    main()

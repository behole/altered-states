#!/usr/bin/env python3
"""
watch.py — Watch journal and experiment directories, auto-rebuild site on change.

Usage:
  python3 watch.py          # watch + serve on :8765
  python3 watch.py --build  # one-shot build only (no watcher)
  python3 watch.py --port 9000  # custom port
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
        print(f"  SKIPPED: {argv[0]} is not installed")
        return None
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {argv[0]} ran longer than {timeout}s")
        return None


def deploy() -> bool:
    """Deploy to Cloudflare Pages and return True on success."""
    wrangler = shutil.which("wrangler")
    if wrangler is None:
        print("  SKIPPED: wrangler is not installed — site built, not deployed")
        return False
    result = _run(
        [wrangler, "pages", "deploy", SITE_DIR, "--project-name", "altered-states", "--commit-dirty=true"],
        timeout=60,
    )
    if result is None:
        return False
    if result.returncode != 0:
        print(f"  DEPLOY FAILED:\n{result.stderr}")
        return False
    for line in result.stdout.strip().split("\n"):
        if "Success!" in line or "Deployment complete!" in line:
            print(f"  {line}")
    return True


def build_and_deploy() -> bool:
    """Build site and deploy to Cloudflare Pages."""
    if not build():
        return False
    print("  Deploying to Cloudflare Pages...")
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
        print(f"  BUILD FAILED:\n{result.stderr}")
        return False
    for line in result.stdout.strip().split("\n"):
        if "Built:" in line:
            print(f"  {line}")
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


def watch_loop() -> None:
    """Main watch loop. Blocks forever."""
    print("Watching for changes...")
    print(f"  Journals: {WATCH_DIRS[0]}")
    print(f"  Experiments: {WATCH_DIRS[1]}")
    print("  Press Ctrl+C to stop\n")

    # Initial build + deploy
    print("Initial build:")
    build_and_deploy()

    last_build_time = time.time()
    snapshot = get_snapshot()
    print(f"  Tracking {len(snapshot)} files\n")

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
            print(f"\n[{ts}] Change detected ({len(changed)} file(s)):")
            for c in changed[:PREVIEW_CHANGE_COUNT]:
                print(f"  ~ {os.path.basename(c)}")
            if len(changed) > PREVIEW_CHANGE_COUNT:
                print(f"  ... and {len(changed) - PREVIEW_CHANGE_COUNT} more")

            if build_and_deploy():
                last_build_time = now
                print()
            else:
                print("  (build/deploy failed, will retry on next change)\n")

            snapshot = current

    except KeyboardInterrupt:
        print("\nStopped watching.")


def parse_port(args: list[str], default: int = 8765) -> int:
    """Read `--port <n>` / `--port=<n>` from argv, falling back to `default`."""
    for i, arg in enumerate(args):
        if arg.startswith("--port="):
            raw_port = arg.partition("=")[2]
            return int(raw_port) if raw_port.isdigit() else default
        if arg == "--port" and i + 1 < len(args) and args[i + 1].isdigit():
            return int(args[i + 1])
    return default


def main() -> None:
    args = sys.argv[1:]
    port = parse_port(args)

    if "--build" in args:
        build_and_deploy()
        return

    # Start HTTP server in background thread
    server = http.server.HTTPServer(("127.0.0.1", port), SiteHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Serving at http://localhost:{port}")

    def shutdown(_sig: int, _frame: FrameType | None) -> NoReturn:
        print("\nShutting down...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    watch_loop()


if __name__ == "__main__":
    main()

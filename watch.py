#!/usr/bin/env python3
"""
watch.py — Watch journal and experiment directories, auto-rebuild site on change.

Usage:
  python3 watch.py          # watch + serve on :8765
  python3 watch.py --build  # one-shot build only (no watcher)
  python3 watch.py --port 9000  # custom port
"""

import os
import sys
import time
import subprocess
import signal
import http.server
import threading

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


def deploy():
    """Deploy to Cloudflare Pages and return True on success."""
    try:
        result = subprocess.run(
            ["wrangler", "pages", "deploy", SITE_DIR,
             "--project-name", "altered-states",
             "--commit-dirty=true"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "Success!" in line or "Deployment complete!" in line:
                    print(f"  {line}")
            return True
        else:
            print(f"  DEPLOY FAILED:\n{result.stderr}")
            return False
    except Exception as e:
        print(f"  DEPLOY ERROR: {e}")
        return False


def build_and_deploy():
    """Build site and deploy to Cloudflare Pages."""
    if not build():
        return False
    print("  Deploying to Cloudflare Pages...")
    return deploy()


class SiteHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from SITE_DIR without chdir."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)


def build():
    """Run build.py and return True on success."""
    build_script = os.path.join(BASE, "build.py")
    try:
        result = subprocess.run(
            ["python3", build_script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "Built:" in line:
                    print(f"  {line}")
            return True
        else:
            print(f"  BUILD FAILED:\n{result.stderr}")
            return False
    except Exception as e:
        print(f"  BUILD ERROR: {e}")
        return False


def get_snapshot():
    """Get a dict of {path: mtime} for all watched files."""
    snapshot = {}
    for watch_dir in WATCH_DIRS:
        if not os.path.exists(watch_dir):
            continue
        for root, dirs, files in os.walk(watch_dir):
            for f in files:
                if os.path.splitext(f)[1].lower() in WATCH_EXTS:
                    path = os.path.join(root, f)
                    try:
                        snapshot[path] = os.path.getmtime(path)
                    except OSError:
                        pass
    return snapshot


def watch_loop():
    """Main watch loop. Blocks forever."""
    print("Watching for changes...")
    print(f"  Journals: {WATCH_DIRS[0]}")
    print(f"  Experiments: {WATCH_DIRS[1]}")
    print(f"  Press Ctrl+C to stop\n")

    # Initial build + deploy
    print("Initial build:")
    build_and_deploy()

    last_build_time = time.time()
    snapshot = get_snapshot()
    print(f"  Tracking {len(snapshot)} files\n")

    try:
        while True:
            time.sleep(2)
            current = get_snapshot()

            # Check for changes
            changed = []
            for path, mtime in current.items():
                if path not in snapshot or snapshot[path] != mtime:
                    changed.append(path)
            # Check for deleted files
            for path in snapshot:
                if path not in current:
                    changed.append(f"{path} (deleted)")

            if changed:
                # Debounce
                now = time.time()
                if now - last_build_time < MIN_INTERVAL:
                    snapshot = current
                    continue

                ts = time.strftime("%H:%M:%S")
                print(f"\n[{ts}] Change detected ({len(changed)} file(s)):")
                for c in changed[:5]:
                    name = os.path.basename(c)
                    print(f"  ~ {name}")
                if len(changed) > 5:
                    print(f"  ... and {len(changed) - 5} more")

                if build_and_deploy():
                    last_build_time = now
                    print()
                else:
                    print("  (build/deploy failed, will retry on next change)\n")

                snapshot = current

    except KeyboardInterrupt:
        print("\nStopped watching.")


def main():
    args = sys.argv[1:]
    port = 8765

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--build":
            build_and_deploy()
            return
        if arg.startswith("--port"):
            if "=" in arg:
                port = int(arg.split("=")[1])
            elif i + 1 < len(args) and args[i + 1].isdigit():
                port = int(args[i + 1])
                i += 1
        i += 1

    # Start HTTP server in background thread
    server = http.server.HTTPServer(("127.0.0.1", port), SiteHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Serving at http://localhost:{port}")

    def shutdown(sig, frame):
        print("\nShutting down...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    watch_loop()


if __name__ == "__main__":
    main()

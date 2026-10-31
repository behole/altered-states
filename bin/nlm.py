#!/usr/bin/env python3
"""Helper to talk to notebooklm-mcp over HTTP/SSE."""

import json
import os
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

BASE = "http://127.0.0.1:8420/mcp"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".nlm-session")

# argv layout: <script> <command> [<tool-name> <json-arguments>]
ARGV_COMMAND = 1
ARGV_TOOL_NAME = 2
ARGV_TOOL_PAYLOAD = 3

_req_id: list[int] = [0]

# The helper only ever talks to the local MCP server; anything else is refused
# so a poisoned BASE or a redirect cannot turn this into a local-file reader.
ALLOWED_SCHEMES = ("http", "https")


def _validated_url(url: str) -> str:
    """Reject anything that is not a plain HTTP(S) URL."""
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"refusing to open {url!r}: scheme {scheme!r} is not http/https")
    return url


def _load_sid() -> str | None:
    """Return the cached MCP session id, or None if none has been stored yet."""
    try:
        with open(STATE_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


def _save_sid(sid: str) -> None:
    with open(STATE_FILE, "w") as f:
        f.write(sid)


def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-RPC tools/call payload for one MCP tool invocation."""
    return {"name": name, "arguments": arguments}


def call(method: str, params: dict[str, Any] | None = None) -> Any:
    _req_id[0] += 1
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": _req_id[0], "method": method}
    if params:
        body["params"] = params
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    sid = _load_sid()
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(_validated_url(BASE), data=json.dumps(body).encode(), headers=headers, method="POST")
    # The scheme is constrained to http/https by _validated_url above.
    with urllib.request.urlopen(req, timeout=180) as resp:  # nosec B310
        new_sid = resp.headers.get("Mcp-Session-Id")
        if new_sid:
            _save_sid(new_sid)
        raw = resp.read().decode()
    for line in raw.split("\n"):
        if line.startswith("data: "):
            payload: dict[str, Any] = json.loads(line[6:])
            if "result" in payload:
                return payload["result"]
            if "error" in payload:
                print("ERROR:", json.dumps(payload["error"], indent=2), file=sys.stderr)
                return payload["error"]
    return None


def print_result(result: Any) -> None:
    if result and isinstance(result, dict) and "content" in result:
        for part in result["content"]:
            if part.get("type") == "text":
                print(part["text"])
    else:
        print(json.dumps(result, indent=2))


def _print_usage(program: str) -> None:
    print(f"Usage: {program} init|tools|call|add-text|add-url|query|list|info")


def _cmd_init(_argv: list[str]) -> int:
    print(
        json.dumps(
            call(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pi", "version": "1.0"},
                },
            ),
            indent=2,
        )
    )
    return 0


def _cmd_tools(_argv: list[str]) -> int:
    r = call("tools/list", {})
    for t in r.get("tools", []):
        print(f"  {t['name']}: {t.get('description', '')[:100]}")
    return 0


def _cmd_call(argv: list[str]) -> int:
    args: dict[str, Any] = json.loads(argv[ARGV_TOOL_PAYLOAD]) if len(argv) > ARGV_TOOL_PAYLOAD else {}
    print_result(call("tools/call", {"name": argv[ARGV_TOOL_NAME], "arguments": args}))
    return 0


def _cmd_add_text(argv: list[str]) -> int:
    nb_id, title, fpath = argv[2], argv[3], argv[4]
    with open(fpath) as f:
        text = f.read()
    r = call(
        "tools/call",
        _tool_call(
            "source_add",
            {"notebook_id": nb_id, "source_type": "text", "title": title, "text": text},
        ),
    )
    print_result(r)
    return 0


def _cmd_add_url(argv: list[str]) -> int:
    nb_id, url = argv[2], argv[3]
    r = call(
        "tools/call",
        _tool_call("source_add", {"notebook_id": nb_id, "source_type": "url", "url": url}),
    )
    print_result(r)
    return 0


def _cmd_query(argv: list[str]) -> int:
    nb_id, q = argv[2], argv[3]
    r = call(
        "tools/call",
        _tool_call("notebook_query", {"notebook_id": nb_id, "query": q}),
    )
    print_result(r)
    return 0


def _cmd_list(_argv: list[str]) -> int:
    print_result(call("tools/call", _tool_call("notebook_list", {})))
    return 0


def _cmd_info(argv: list[str]) -> int:
    r = call(
        "tools/call",
        _tool_call("notebook_get", {"notebook_id": argv[2]}),
    )
    print_result(r)
    return 0


COMMANDS: dict[str, Callable[[list[str]], int]] = {
    "init": _cmd_init,
    "tools": _cmd_tools,
    "call": _cmd_call,
    "add-text": _cmd_add_text,
    "add-url": _cmd_add_url,
    "query": _cmd_query,
    "list": _cmd_list,
    "info": _cmd_info,
}


def main(argv: list[str]) -> int:
    if len(argv) <= ARGV_COMMAND or argv[ARGV_COMMAND] not in COMMANDS:
        _print_usage(argv[0] if argv else "nlm.py")
        return 1
    return COMMANDS[argv[ARGV_COMMAND]](argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))

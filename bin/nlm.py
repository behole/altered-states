#!/usr/bin/env python3
"""Helper to talk to notebooklm-mcp over HTTP/SSE."""
import sys, json, os, urllib.request

BASE = "http://127.0.0.1:8420/mcp"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".nlm-session")
_req_id = [0]

def _load_sid():
    try:
        with open(STATE_FILE) as f: return f.read().strip()
    except: return None

def _save_sid(sid):
    with open(STATE_FILE, "w") as f: f.write(sid)

def call(method, params=None):
    _req_id[0] += 1
    body = {"jsonrpc": "2.0", "id": _req_id[0], "method": method}
    if params: body["params"] = params
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    sid = _load_sid()
    if sid: headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request(BASE, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        new_sid = resp.headers.get("Mcp-Session-Id")
        if new_sid: _save_sid(new_sid)
        raw = resp.read().decode()
    for line in raw.split("\n"):
        if line.startswith("data: "):
            p = json.loads(line[6:])
            if "result" in p: return p["result"]
            if "error" in p:
                print("ERROR:", json.dumps(p["error"], indent=2), file=sys.stderr)
                return p["error"]
    return None

def print_result(r):
    if r and isinstance(r, dict) and "content" in r:
        for c in r["content"]:
            if c.get("type") == "text": print(c["text"])
    else:
        print(json.dumps(r, indent=2))

if __name__ == "__main__":
    cmd = sys.argv[1]

    if cmd == "init":
        print(json.dumps(call("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "pi", "version": "1.0"}
        }), indent=2))

    elif cmd == "tools":
        r = call("tools/list", {})
        for t in r.get("tools", []):
            print(f"  {t['name']}: {t.get('description','')[:100]}")

    elif cmd == "call":
        r = call("tools/call", {"name": sys.argv[2], "arguments": json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}})
        print_result(r)

    elif cmd == "add-text":
        nb_id, title, fpath = sys.argv[2], sys.argv[3], sys.argv[4]
        with open(fpath) as f: text = f.read()
        r = call("tools/call", {"name": "source_add", "arguments": {"notebook_id": nb_id, "source_type": "text", "title": title, "text": text}})
        print_result(r)

    elif cmd == "add-url":
        nb_id, url = sys.argv[2], sys.argv[3]
        r = call("tools/call", {"name": "source_add", "arguments": {"notebook_id": nb_id, "source_type": "url", "url": url}})
        print_result(r)

    elif cmd == "query":
        nb_id, q = sys.argv[2], sys.argv[3]
        r = call("tools/call", {"name": "notebook_query", "arguments": {"notebook_id": nb_id, "query": q}})
        print_result(r)

    elif cmd == "list":
        r = call("tools/call", {"name": "notebook_list", "arguments": {}})
        print_result(r)

    elif cmd == "info":
        r = call("tools/call", {"name": "notebook_get", "arguments": {"notebook_id": sys.argv[2]}})
        print_result(r)

    else:
        print(f"Usage: {sys.argv[0]} init|tools|call|add-text|add-url|query|list|info")
        sys.exit(1)

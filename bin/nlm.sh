#!/usr/bin/env python3
"""Helper to talk to notebooklm-mcp over HTTP/SSE."""

import sys, json, subprocess, time
import urllib.request

BASE = "http://127.0.0.1:8420/mcp"
session_id = None
req_id = 0

def call(method, params=None):
    global session_id, req_id
    req_id += 1
    body = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params:
        body["params"] = params
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE, data=data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=180) as resp:
        # Capture session id from response headers
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            session_id = sid
        
        raw = resp.read().decode()
    
    # Parse SSE: find the "data:" line with our response
    result = None
    for line in raw.split("\n"):
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if "result" in payload:
                result = payload["result"]
            elif "error" in payload:
                print(f"ERROR: {json.dumps(payload['error'])}", file=sys.stderr)
                result = payload["error"]
    
    return result

if __name__ == "__main__":
    cmd = sys.argv[1]
    
    if cmd == "init":
        r = call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pi", "version": "1.0"}
        })
        print(json.dumps(r, indent=2))
    
    elif cmd == "tools":
        r = call("tools/list", {})
        if r and "tools" in r:
            for t in r["tools"]:
                desc = t.get("description", "")[:100]
                print(f"  {t['name']}: {desc}")
        else:
            print(json.dumps(r, indent=2))
    
    elif cmd == "call":
        tool_name = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        r = call("tools/call", {"name": tool_name, "arguments": args})
        if r and "content" in r:
            for c in r["content"]:
                if c.get("type") == "text":
                    print(c["text"])
        else:
            print(json.dumps(r, indent=2))
    
    else:
        print(f"Usage: {sys.argv[0]} [init|tools|call <tool_name> <json_args>]")

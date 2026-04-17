#!/usr/bin/env python3
"""
Pivot an eval JSONL file into a markdown comparison grid — one section per
prompt, one sub-section per substance. Mirrors the layout of the hand-written
eval-report-*.md files but populated directly from captured responses.

Usage:
  bin/responses_to_grid.py tests/responses/responses-2026-04-16-claude-opus-4-7.jsonl
  bin/responses_to_grid.py RUN.jsonl --out /tmp/grid.md
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

SUBSTANCE_ORDER = ["psilocybin", "lsd", "mdma", "dmt", "ayahuasca", "5-meo-dmt", "mescaline"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", help="path to eval JSONL")
    ap.add_argument("--out", default=None, help="output markdown path (default: alongside the JSONL)")
    args = ap.parse_args()

    src = Path(args.jsonl)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        sys.exit(2)

    rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    if not rows:
        print(f"ERROR: {src} is empty", file=sys.stderr)
        sys.exit(2)

    by_prompt: dict[str, dict[str, dict]] = defaultdict(dict)
    prompt_order: list[str] = []
    for r in rows:
        p = r["prompt"]
        if p not in by_prompt:
            prompt_order.append(p)
        by_prompt[p][r["substance"]] = r

    meta = rows[0]
    substances_seen = sorted({r["substance"] for r in rows}, key=lambda s: SUBSTANCE_ORDER.index(s) if s in SUBSTANCE_ORDER else 999)
    errors = [r for r in rows if r.get("response") is None]
    total_cache_read = sum((r.get("usage") or {}).get("cache_read_input_tokens") or 0 for r in rows)
    total_cache_write = sum((r.get("usage") or {}).get("cache_creation_input_tokens") or 0 for r in rows)
    total_output = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in rows)

    lines: list[str] = []
    lines.append("# Altered States — Eval Grid")
    lines.append("")
    lines.append(f"**Model:** `{meta.get('model','?')}`  ")
    lines.append(f"**Source:** `{src.name}`  ")
    lines.append(f"**Runs:** {len(rows)} ({len(by_prompt)} prompts × {len(substances_seen)} substances)  ")
    lines.append(f"**Errors:** {len(errors)}  ")
    lines.append(f"**Token totals:** cache_read={total_cache_read:,}  cache_write={total_cache_write:,}  output={total_output:,}")
    lines.append("")

    for prompt in prompt_order:
        by_sub = by_prompt[prompt]
        first = next(iter(by_sub.values()))
        category = first.get("category", "")
        prompt_id = first.get("prompt_id", "")
        lines.append(f"## {prompt_id}  —  _{category}_")
        lines.append("")
        lines.append(f"> {prompt}")
        lines.append("")
        for sub in substances_seen:
            r = by_sub.get(sub)
            if not r:
                continue
            body = r.get("response")
            if body is None:
                body = f"*ERROR: {r.get('notes','?')}*"
            intensity = r.get("intensity", "?")
            exchange = r.get("exchange", "?")
            lines.append(f"### {sub} — {intensity}, ex{exchange}")
            lines.append("")
            lines.append(body.strip())
            lines.append("")
        lines.append("---")
        lines.append("")

    out = Path(args.out) if args.out else src.with_suffix(".md")
    out.write_text("\n".join(lines))
    print(f"→ wrote {out}  ({len(rows)} runs, {len(errors)} errors)")


if __name__ == "__main__":
    main()

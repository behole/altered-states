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
from typing import Any

SUBSTANCE_ORDER = ["psilocybin", "lsd", "mdma", "dmt", "ayahuasca", "5-meo-dmt", "mescaline"]
UNKNOWN_SUBSTANCE_RANK = 999

EXIT_INPUT_ERROR = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", help="path to eval JSONL")
    ap.add_argument("--out", default=None, help="output markdown path (default: alongside the JSONL)")
    return ap.parse_args(argv)


def load_rows(src: Path) -> list[dict[str, Any]]:
    """Read every non-blank JSONL line into a list of row dicts."""
    rows: list[dict[str, Any]] = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    return rows


def group_by_prompt(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, dict[str, Any]]], list[str]]:
    """Group rows into {prompt: {substance: row}}, preserving first-seen order."""
    by_prompt: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    prompt_order: list[str] = []
    for r in rows:
        prompt = r["prompt"]
        if prompt not in by_prompt:
            prompt_order.append(prompt)
        by_prompt[prompt][r["substance"]] = r
    return by_prompt, prompt_order


def sort_substances(rows: list[dict[str, Any]]) -> list[str]:
    """Substances seen in the run, ordered by the canonical substance list."""

    def rank(substance: str) -> int:
        if substance in SUBSTANCE_ORDER:
            return SUBSTANCE_ORDER.index(substance)
        return UNKNOWN_SUBSTANCE_RANK

    return sorted({r["substance"] for r in rows}, key=rank)


def usage_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Sum cache and output token counts across all rows."""
    return {
        "cache_read": sum((r.get("usage") or {}).get("cache_read_input_tokens") or 0 for r in rows),
        "cache_write": sum((r.get("usage") or {}).get("cache_creation_input_tokens") or 0 for r in rows),
        "output": sum((r.get("usage") or {}).get("output_tokens") or 0 for r in rows),
    }


def render_header(
    meta: dict[str, Any],
    src: Path,
    rows: list[dict[str, Any]],
    prompt_count: int,
    substances_seen: list[str],
    error_count: int,
) -> list[str]:
    totals = usage_totals(rows)
    return [
        "# Altered States — Eval Grid",
        "",
        f"**Model:** `{meta.get('model', '?')}`  ",
        f"**Source:** `{src.name}`  ",
        f"**Runs:** {len(rows)} ({prompt_count} prompts × {len(substances_seen)} substances)  ",
        f"**Errors:** {error_count}  ",
        f"**Token totals:** cache_read={totals['cache_read']:,}  "
        f"cache_write={totals['cache_write']:,}  output={totals['output']:,}",
        "",
    ]


def render_prompt(
    prompt: str,
    by_substance: dict[str, dict[str, Any]],
    substances_seen: list[str],
) -> list[str]:
    first = next(iter(by_substance.values()))
    lines = [
        f"## {first.get('prompt_id', '')}  —  _{first.get('category', '')}_",
        "",
        f"> {prompt}",
        "",
    ]
    for substance in substances_seen:
        row = by_substance.get(substance)
        if not row:
            continue
        response = row.get("response")
        body = response.strip() if response is not None else f"*ERROR: {row.get('notes', '?')}*"
        lines.extend(
            [
                f"### {substance} — {row.get('intensity', '?')}, ex{row.get('exchange', '?')}",
                "",
                body,
                "",
            ]
        )
    lines.extend(["---", ""])
    return lines


def render_grid(rows: list[dict[str, Any]], src: Path) -> list[str]:
    """Render the full markdown grid for a run."""
    by_prompt, prompt_order = group_by_prompt(rows)
    substances_seen = sort_substances(rows)
    errors = [r for r in rows if r.get("response") is None]
    lines = render_header(rows[0], src, rows, len(prompt_order), substances_seen, len(errors))
    for prompt in prompt_order:
        lines.extend(render_prompt(prompt, by_prompt[prompt], substances_seen))
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    src = Path(args.jsonl)
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return EXIT_INPUT_ERROR

    rows = load_rows(src)
    if not rows:
        print(f"ERROR: {src} is empty", file=sys.stderr)
        return EXIT_INPUT_ERROR

    out = Path(args.out) if args.out else src.with_suffix(".md")
    out.write_text("\n".join(render_grid(rows, src)))
    error_count = sum(1 for r in rows if r.get("response") is None)
    print(f"→ wrote {out}  ({len(rows)} runs, {error_count} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

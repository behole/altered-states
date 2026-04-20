#!/usr/bin/env python3
"""Run a cycle for every character whose cadence is due.

Cron target. Recommended schedule: every 15 minutes.
Per-substance cadence is in cadence.CYCLE_MINUTES — a fast character (e.g.
salvia at 60min) fires once per hour; a slow one (e.g. ibogaine at 1440min)
fires once per day. The dispatcher decides each run who's actually due.
"""

import sys
from datetime import datetime

from cadence import due_characters
from logger import daily_cost_summary
from temporal_init import TemporalLab


def main() -> int:
    lab = TemporalLab()
    now = datetime.now()
    due = due_characters(lab.characters_path, now)

    if not due:
        print(f"⏸  Nothing due at {now.strftime('%Y-%m-%d %H:%M:%S')}")
        return 0

    print(f"🔄 {len(due)} character(s) due at {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    failures = 0
    for char in due:
        substance = char["substance"]
        if not lab.run_cycle(substance):
            failures += 1
        print("-" * 60)

    summary = daily_cost_summary()
    print(f"📊 Today so far: {summary['calls']} calls  ${summary['cost_usd']:.4f}")
    print(f"🎭 Done. {len(due) - failures}/{len(due)} cycles succeeded.")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

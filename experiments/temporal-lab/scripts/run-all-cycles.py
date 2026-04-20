#!/usr/bin/env python3
"""Run one cycle for every active character.

Intended as the cron target. Reads characters from the configured base path,
runs each one through the canonical TemporalLab, and prints a summary.
"""

import json
import sys

from temporal_init import TemporalLab


def main() -> int:
    lab = TemporalLab()

    characters = []
    for file in sorted(lab.characters_path.glob("*.json")):
        with open(file, "r") as f:
            characters.append(json.load(f))

    if not characters:
        print("❌ No active characters found. Initialize first with temporal_init.py init <substance>")
        return 1

    print(f"🔄 Running temporal cycles for {len(characters)} characters")
    print("=" * 50)

    failures = 0
    for char in characters:
        substance = char["substance"]
        name = char["name"]
        current = char.get("cycle_count", 0)
        print(f"🌀 {name} ({substance}) — cycle {current + 1}")
        if not lab.run_cycle(substance):
            failures += 1
            print(f"❌ {name} failed")
        print("-" * 30)

    print(f"🎭 Done. {len(characters) - failures}/{len(characters)} cycles succeeded.")
    print(f"📊 Journals: {lab.journals_path}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

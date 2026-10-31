#!/usr/bin/env python3
"""
Temporal Dashboard - Track character evolution over time.
"""

import json
from datetime import datetime
from typing import Any

from characters import resolve_base_path

# How many recent journal entries to show per character in the timeline.
TIMELINE_ENTRIES = 5

# Emotional states rendered with a positive marker in the timeline.
POSITIVE_STATES = frozenset({"calm", "compassionate", "playful", "loving"})


def load_json(path: Any) -> Any:
    """Read a JSON file, raising whatever the filesystem raises."""
    with open(path) as f:
        return json.load(f)


def main() -> None:
    """Display temporal experiment dashboard"""
    base_path = resolve_base_path()
    characters_path = base_path / "characters"
    journals_path = base_path / "journals"

    print("🎭 Altered States Temporal Lab Dashboard")
    print("=" * 50)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Get all characters
    characters: list[dict[str, Any]] = [load_json(file) for file in characters_path.glob("*.json")]

    if not characters:
        print("❌ No active characters found")
        return

    print(f"📊 Active Characters: {len(characters)}")
    print()

    # Character summary
    for char in characters:
        substance = char["substance"]
        cycles = char.get("cycle_count", 0)

        print(f"🎭 {char['name']} ({substance})")
        print(f"   🔄 Cycles: {cycles}")
        print(f"   📝 State: {char['current_state']['emotional']}")
        print(f"   💭 Focus: {char['learning_focus']}")
        print(f"   ⏰ Next: {char.get('next_cycle', 'TBD')}")

        # Show latest journal entry
        journal_file = journals_path / f"{substance}_journal.json"
        if journal_file.exists():
            journal: list[dict[str, Any]] = load_json(journal_file)
            if journal:
                latest = journal[-1]
                print(f"   🎪 Latest: {latest['experience']['description']}")
                print(f"   🌡️  Intensity: {latest['experience']['intensity']:.2f}")
                print(f"   🔍 Novelty: {latest['experience']['novelty']:.2f}")

        print()

    # Evolution timeline
    print("📈 Evolution Timeline")
    print("-" * 30)

    for char in characters:
        substance = char["substance"]

        journal_file = journals_path / f"{substance}_journal.json"
        if not journal_file.exists():
            continue
        journal = load_json(journal_file)
        if len(journal) <= 1:
            continue

        print(f"{char['name']} emotional evolution:")
        for entry in journal[-TIMELINE_ENTRIES:]:
            emoji = "😊" if entry["emotional_state"] in POSITIVE_STATES else "🤔"
            print(f"  {emoji} Cycle {entry['cycle']}: {entry['emotional_state']}")
        print()


if __name__ == "__main__":
    main()

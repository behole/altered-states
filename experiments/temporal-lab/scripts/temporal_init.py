#!/usr/bin/env python3
"""Temporal Lab — character initialization and single-cycle runner.

Runs as a CLI:
    python temporal_init.py init <substance> [duration]
    python temporal_init.py list
    python temporal_init.py run <substance>

Default storage: experiments/temporal-lab/runtime/ (relative to this file).
Override via: ALTERED_STATES_TEMPORAL_PATH=/path/to/storage
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from characters import (
    SUBSTANCES,
    available_substances,
    resolve_base_path,
    sample_experience,
    substance_characteristics,
)


class TemporalLab:
    def __init__(self, base_path: str | None = None):
        self.base_path = resolve_base_path(base_path)
        self.characters_path = self.base_path / "characters"
        self.journals_path = self.base_path / "journals"
        self.experiments_path = self.base_path / "experiments"
        for path in [self.characters_path, self.journals_path, self.experiments_path]:
            path.mkdir(parents=True, exist_ok=True)

    def get_available_substances(self) -> list[str]:
        return available_substances()

    def initialize_character(self, substance: str, cycle_duration: str = "weekly") -> bool:
        if substance not in self.get_available_substances():
            print(f"❌ Unknown substance: {substance}")
            print(f"Available: {', '.join(self.get_available_substances())}")
            return False

        char_info = substance_characteristics(substance)
        char_file = self.characters_path / f"{substance}.json"

        character_state = {
            "substance": substance,
            "name": char_info["name"],
            "cycle_duration": cycle_duration,
            "created": datetime.now().isoformat(),
            "cycle_count": 0,
            "current_state": {
                "emotional": random.choice(char_info["emotional_range"]),
                "clarity": "moderate",
                "integration": "low",
            },
            "memory_ledger": [],
            "evolution_timeline": [],
            "expression_style": char_info["expression_style"],
            "learning_focus": char_info["learning_focus"],
            "core_traits": char_info["core_traits"],
            "last_cycle": None,
            "next_cycle": self._calculate_next_cycle(cycle_duration),
        }

        with open(char_file, "w") as f:
            json.dump(character_state, f, indent=2)

        self._create_journal_entry(substance, character_state)

        print(f"✅ Initialized character: {char_info['name']} ({substance})")
        print(f"📝 Cycle duration: {cycle_duration}")
        print(f"🗓️  Next cycle: {character_state['next_cycle']}")
        return True

    def _calculate_next_cycle(self, duration: str) -> str:
        now = datetime.now()
        if duration == "daily":
            next_time = now.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
        elif duration == "weekly":
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_time = (now + timedelta(days=days_until_monday)).replace(
                hour=12, minute=0, second=0, microsecond=0
            )
        elif duration == "monthly":
            next_month = now.replace(day=1, hour=12, minute=0, second=0, microsecond=0) + timedelta(days=32)
            next_time = next_month.replace(day=1)
        else:
            next_time = now + timedelta(days=7)
        return next_time.isoformat()

    def _create_journal_entry(self, substance: str, character_state: dict) -> None:
        journal_entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle": character_state["cycle_count"],
            "emotional_state": character_state["current_state"]["emotional"],
            "clarity": character_state["current_state"]["clarity"],
            "integration": character_state["current_state"]["integration"],
            "reflections": [
                "I am beginning my temporal journey.",
                f"I am {character_state['name']}, the {substance} experience.",
                f"My core traits are: {', '.join(character_state['core_traits'])}",
                "I await my first experience cycle.",
            ],
            "questions": [
                "What will I discover about myself?",
                "How will I evolve over time?",
                "What wisdom will I accumulate?",
            ],
        }
        self._append_journal(substance, journal_entry)

    def _append_journal(self, substance: str, entry: dict) -> None:
        journal_file = self.journals_path / f"{substance}_journal.json"
        journal = []
        if journal_file.exists():
            with open(journal_file, "r") as f:
                journal = json.load(f)
        journal.append(entry)
        with open(journal_file, "w") as f:
            json.dump(journal, f, indent=2)

    def run_cycle(self, substance: str) -> bool:
        char_file = self.characters_path / f"{substance}.json"
        if not char_file.exists():
            print(f"❌ Character not found: {substance}")
            return False

        with open(char_file, "r") as f:
            character = json.load(f)

        print(f"🌀 Running {substance} experience for {character['name']}...")

        experience = sample_experience(substance)

        character["cycle_count"] += 1
        character["last_cycle"] = datetime.now().isoformat()
        character["next_cycle"] = self._calculate_next_cycle(character["cycle_duration"])

        char_info = substance_characteristics(substance)
        character["current_state"]["emotional"] = random.choice(char_info["emotional_range"])

        with open(char_file, "w") as f:
            json.dump(character, f, indent=2)

        self._create_cycle_journal_entry(substance, character, experience)

        print(f"✅ Cycle {character['cycle_count']} completed for {character['name']}")
        print(f"   💭 {experience['description']}")
        return True

    def _create_cycle_journal_entry(self, substance: str, character: dict, experience: dict) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "cycle": character["cycle_count"],
            "emotional_state": character["current_state"]["emotional"],
            "clarity": character["current_state"]["clarity"],
            "integration": character["current_state"]["integration"],
            "experience": experience,
            "reflections": [
                f"Cycle {character['cycle_count']} has completed.",
                f"I experienced: {experience['description']}",
                "I am evolving in unexpected ways.",
                "My understanding continues to deepen.",
            ],
            "evolution_notes": [
                "My character is developing new facets.",
                "I learn from each cycle's experience.",
                "Contradictions and insights arise naturally.",
            ],
            "questions": [
                "What will next cycle bring?",
                "How will I continue to evolve?",
                "What deeper understanding awaits?",
            ],
        }
        self._append_journal(substance, entry)

    def list_characters(self) -> list[dict]:
        characters = []
        for file in sorted(self.characters_path.glob("*.json")):
            with open(file, "r") as f:
                characters.append(json.load(f))
        print("🎭 Active Temporal Characters:")
        for char in characters:
            print(f"  • {char['name']} ({char['substance']}) — Cycle {char['cycle_count']}")
        return characters


def _print_usage() -> None:
    print("Usage:")
    print("  python temporal_init.py init <substance> [duration]")
    print("  python temporal_init.py list")
    print("  python temporal_init.py run <substance>")
    print("\nSubstances available: " + ", ".join(available_substances()))
    print("Durations: daily | weekly | monthly (default: weekly)")
    print("\nStorage path (override with ALTERED_STATES_TEMPORAL_PATH):")
    print(f"  {resolve_base_path()}")


def main() -> int:
    if len(sys.argv) < 2:
        _print_usage()
        return 1

    lab = TemporalLab()
    command = sys.argv[1]

    if command == "init":
        if len(sys.argv) < 3:
            print("❌ Please specify a substance")
            return 1
        substance = sys.argv[2]
        duration = sys.argv[3] if len(sys.argv) > 3 else "weekly"
        return 0 if lab.initialize_character(substance, duration) else 1

    if command == "list":
        lab.list_characters()
        return 0

    if command == "run":
        if len(sys.argv) < 3:
            print("❌ Please specify a substance")
            return 1
        return 0 if lab.run_cycle(sys.argv[2]) else 1

    print(f"❌ Unknown command: {command}")
    _print_usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())

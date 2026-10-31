#!/usr/bin/env python3
"""Temporal Lab — character initialization and single-cycle runner (LLM-backed).

CLI:
    python temporal_init.py init <substance> [duration]
    python temporal_init.py list
    python temporal_init.py run <substance> [--model MODEL]
    python temporal_init.py costs
"""

import json
import os
import random
import sys
from datetime import datetime
from typing import Any

from cadence import cycle_minutes, next_cycle_at
from characters import (
    available_substances,
    resolve_base_path,
    substance_characteristics,
)
from llm_invoke import generate_cycle
from logger import daily_cost_summary, lifetime_cost_summary

# Unicode section rule used in the plain-text journal mirror.
SECTION_RULE = "=" * 50

# argv layout: <script> <command> [args...]
MIN_ARGV_WITH_COMMAND = 2


def _experience_lines(entry: dict[str, Any]) -> list[str]:
    """Render the `experience` block of a journal entry."""
    if "experience" not in entry:
        return []

    experience = entry["experience"]
    lines = [""]
    if isinstance(experience, dict):
        intensity = experience.get("intensity", 0)
        novelty = experience.get("novelty", 0)
        description = experience.get("description", "")
        lines.append(f"Experience (intensity: {intensity:.2f}, novelty: {novelty:.2f}):")
        lines.append(f"  {description}")
    else:
        lines.append(f"Experience: {experience}")
    return lines


def _bulleted_section(items: Any, heading: str, bullet: str) -> list[str]:
    """Render an optional bulleted section of a journal entry."""
    if not items:
        return []
    return ["", f"{heading}:", *(f"  {bullet} {item}" for item in items)]


class TemporalLab:
    def __init__(self, base_path: str | None = None) -> None:
        self.base_path = resolve_base_path(base_path)
        self.characters_path = self.base_path / "characters"
        self.journals_path = self.base_path / "journals"
        self.experiments_path = self.base_path / "experiments"
        for path in [self.characters_path, self.journals_path, self.experiments_path]:
            path.mkdir(parents=True, exist_ok=True)

    def get_available_substances(self) -> list[str]:
        return available_substances()

    def initialize_character(self, substance: str, cycle_duration: str = "auto") -> bool:
        if substance not in self.get_available_substances():
            print(f"❌ Unknown substance: {substance}")
            print(f"Available: {', '.join(self.get_available_substances())}")
            return False

        char_info = substance_characteristics(substance)
        char_file = self.characters_path / f"{substance}.json"

        # cycle_duration kept for compat — actual cadence comes from cadence.py
        if cycle_duration == "auto":
            cycle_duration = f"{cycle_minutes(substance)}m"

        character_state: dict[str, Any] = {
            "substance": substance,
            "name": char_info["name"],
            "cycle_duration": cycle_duration,
            "cycle_minutes": cycle_minutes(substance),
            "created": datetime.now().isoformat(),
            "cycle_count": 0,
            "current_state": {
                # Initial-state variety only; not used for any security decision.
                "emotional": random.choice(char_info["emotional_range"]),  # nosec B311
                "clarity": "moderate",
                "integration": "low",
            },
            "memory_ledger": [],
            "evolution_timeline": [],
            "expression_style": char_info["expression_style"],
            "learning_focus": char_info["learning_focus"],
            "core_traits": char_info["core_traits"],
            "last_cycle": None,
            "next_cycle": next_cycle_at(substance),
        }

        with open(char_file, "w") as f:
            json.dump(character_state, f, indent=2)

        self._create_initial_journal_entry(substance, character_state)

        print(f"✅ Initialized: {char_info['name']} ({substance})")
        print(f"⏱️  Cycle every: {cycle_minutes(substance)} min")
        print(f"🗓️  Next cycle: {character_state['next_cycle']}")
        return True

    def _create_initial_journal_entry(self, substance: str, character_state: dict[str, Any]) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "cycle": character_state["cycle_count"],
            "emotional_state": character_state["current_state"]["emotional"],
            "clarity": character_state["current_state"]["clarity"],
            "integration": character_state["current_state"]["integration"],
            "reflections": [
                "I am beginning my temporal journey.",
                f"I am {character_state['name']}, the {substance} experience.",
                "I await my first cycle.",
            ],
            "questions": ["What will I discover about myself across many cycles?"],
        }
        self._append_journal(substance, entry)

    def _append_journal(self, substance: str, entry: dict[str, Any]) -> None:
        journal_file = self.journals_path / f"{substance}_journal.json"
        journal: list[dict[str, Any]] = []
        if journal_file.exists():
            with open(journal_file) as f:
                journal = json.load(f)
        journal.append(entry)
        with open(journal_file, "w") as f:
            json.dump(journal, f, indent=2)

        # Plain text mirror
        self._write_plain_text_entry(substance, entry)

    def _write_plain_text_entry(self, substance: str, entry: dict[str, Any]) -> None:
        """Append a human-readable entry to <substance>_journal.txt."""
        txt_file = self.journals_path / f"{substance}_journal.txt"

        timestamp = entry.get("timestamp", "?")
        cycle = entry.get("cycle", 0)
        lines = [
            SECTION_RULE,
            f"{substance.upper()} — Cycle {cycle}",
            f"Timestamp: {timestamp}",
            SECTION_RULE,
            f"Emotional State: {entry.get('emotional_state', 'unknown')}",
        ]

        clarity = entry.get("clarity", "")
        if clarity:
            lines.append(f"Clarity: {clarity}")
        integration = entry.get("integration", "")
        if integration:
            lines.append(f"Integration: {integration}")

        lines.extend(_experience_lines(entry))
        lines.extend(_bulleted_section(entry.get("reflections"), "Reflections", "—"))
        lines.extend(_bulleted_section(entry.get("evolution_notes"), "Evolution Notes", "*"))
        lines.extend(_bulleted_section(entry.get("questions"), "Open Questions", "?"))
        lines.extend(["", ""])

        with open(txt_file, "a") as f:
            f.write("\n".join(lines))

    def _load_journal(self, substance: str) -> list[dict[str, Any]]:
        journal_file = self.journals_path / f"{substance}_journal.json"
        if not journal_file.exists():
            return []
        with open(journal_file) as f:
            journal: list[dict[str, Any]] = json.load(f)
        return journal

    def run_cycle(self, substance: str, model: str | None = None) -> bool:
        char_file = self.characters_path / f"{substance}.json"
        if not char_file.exists():
            print(f"❌ Character not found: {substance}")
            return False

        with open(char_file) as f:
            character: dict[str, Any] = json.load(f)

        char_info = substance_characteristics(substance)
        journal = self._load_journal(substance)

        print(f"🌀 {character['name']} ({substance}) — invoking model...")
        try:
            cycle = generate_cycle(substance, char_info, character, journal, model=model)
        except Exception as e:
            print(f"❌ Cycle failed for {substance}: {e}")
            # Record the silence in the journal so the character "remembers" it went dark
            self._append_journal(
                substance,
                {
                    "timestamp": datetime.now().isoformat(),
                    "cycle": character["cycle_count"] + 1,
                    "emotional_state": character["current_state"]["emotional"],
                    "clarity": character["current_state"]["clarity"],
                    "integration": character["current_state"]["integration"],
                    "experience": {
                        "description": f"[silence — model invocation failed: {type(e).__name__}]",
                        "intensity": 0.0,
                        "novelty": 0.0,
                    },
                    "reflections": ["I went somewhere and did not come back with words."],
                    "questions": ["What did I miss?"],
                    "error": str(e),
                },
            )
            return False

        # Update character state from the LLM response
        character["cycle_count"] += 1
        character["last_cycle"] = datetime.now().isoformat()
        character["next_cycle"] = next_cycle_at(substance)
        character["current_state"]["emotional"] = cycle["emotional_state"]
        character["current_state"]["clarity"] = cycle["clarity"]
        character["current_state"]["integration"] = cycle["integration"]

        with open(char_file, "w") as f:
            json.dump(character, f, indent=2)

        # Persist the cycle entry
        self._append_journal(
            substance,
            {
                "timestamp": datetime.now().isoformat(),
                "cycle": character["cycle_count"],
                "emotional_state": cycle["emotional_state"],
                "clarity": cycle["clarity"],
                "integration": cycle["integration"],
                "experience": cycle["experience"],
                "reflections": cycle["reflections"],
                "questions": cycle["questions"],
            },
        )

        print(f"✅ Cycle {character['cycle_count']} complete — felt: {cycle['emotional_state']}")
        print(f"   💭 {cycle['experience']['description']}")
        return True

    def list_characters(self) -> list[dict[str, Any]]:
        characters: list[dict[str, Any]] = []
        for file in sorted(self.characters_path.glob("*.json")):
            with open(file) as f:
                characters.append(json.load(f))
        if not characters:
            print("No active characters. Initialize with: python temporal_init.py init <substance>")
            return characters
        print("🎭 Active Temporal Characters:")
        for char in characters:
            print(
                f"  • {char['name']:20s} ({char['substance']:12s}) "
                f"cycle {char['cycle_count']:3d}  next: {char.get('next_cycle', '?')}"
            )
        return characters


def _print_usage() -> None:
    print("Usage:")
    print("  python temporal_init.py init <substance> [duration]")
    print("  python temporal_init.py list")
    print("  python temporal_init.py run <substance> [--model MODEL]")
    print("  python temporal_init.py costs")
    print("\nSubstances: " + ", ".join(available_substances()))
    print("\nStorage path (override with ALTERED_STATES_TEMPORAL_PATH):")
    print(f"  {resolve_base_path()}")
    model = os.environ.get("LLM_MODEL") or os.environ.get("TEMPORAL_LAB_MODEL", "deepseek-v4-pro (default)")
    print(f"\nModel: {model}")
    if os.environ.get("TEMPORAL_LAB_DRY_RUN"):
        print("⚠️  TEMPORAL_LAB_DRY_RUN is set — calls will return stubs.")


def _cmd_init(lab: TemporalLab, args: list[str]) -> int:
    if not args:
        print("❌ Specify a substance")
        return 1
    duration = args[1] if len(args) > 1 else "auto"
    return 0 if lab.initialize_character(args[0], duration) else 1


def _cmd_list(lab: TemporalLab, _args: list[str]) -> int:
    lab.list_characters()
    return 0


def _cmd_run(lab: TemporalLab, args: list[str]) -> int:
    if not args:
        print("❌ Specify a substance")
        return 1
    model = None
    if "--model" in args:
        model_index = args.index("--model")
        if model_index + 1 < len(args):
            model = args[model_index + 1]
    return 0 if lab.run_cycle(args[0], model=model) else 1


def _cmd_costs(_lab: TemporalLab, _args: list[str]) -> int:
    today = daily_cost_summary()
    lifetime = lifetime_cost_summary()
    print(
        f"📊 Today ({today['date']}): {today['calls']} calls, "
        f"{today['tokens_in']:,}→{today['tokens_out']:,} tokens, "
        f"${today['cost_usd']:.4f}"
    )
    print(f"📊 Lifetime: {lifetime['calls']} calls, ${lifetime['cost_usd']:.4f}")
    if lifetime["by_model"]:
        print("   By model:")
        for model, stats in sorted(lifetime["by_model"].items()):
            print(f"     {model:40s} {stats['calls']:5d} calls  ${stats['cost_usd']:.4f}")
    return 0


def main() -> int:
    if len(sys.argv) < MIN_ARGV_WITH_COMMAND:
        _print_usage()
        return 1

    lab = TemporalLab()
    command = sys.argv[1]
    handlers = {
        "init": _cmd_init,
        "list": _cmd_list,
        "run": _cmd_run,
        "costs": _cmd_costs,
    }
    handler = handlers.get(command)
    if handler is None:
        print(f"❌ Unknown command: {command}")
        _print_usage()
        return 1
    return handler(lab, sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Extract interesting insights and patterns from temporal journals.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from characters import resolve_base_path

# A journal needs at least this many entries before patterns are meaningful.
MIN_ENTRIES = 2
# Emotional stability buckets, measured as distinct emotions per character.
FOCUSED_EMOTION_COUNT = 1
NARROW_EMOTION_COUNT = 2
# Only characters with this many cycles get a development observation.
MIN_CYCLES_FOR_OBSERVATION = 3
# How many of the most common emotions to report.
TOP_EMOTIONS = 3


def collect_insights(journals_path: Path) -> list[dict[str, Any]]:
    """Compute one insight record per character with enough journal history."""
    insights: list[dict[str, Any]] = []

    for journal_file in journals_path.glob("*_journal.json"):
        substance = journal_file.stem.replace("_journal", "")

        with open(journal_file) as f:
            journal: list[dict[str, Any]] = json.load(f)

        if len(journal) < MIN_ENTRIES:
            continue

        # Skip initial entry (has no experience)
        experiences = [entry for entry in journal if "experience" in entry]
        if not experiences:
            continue

        emotions = [entry["emotional_state"] for entry in experiences]
        unique_emotions = set(emotions)

        most_intense = max(experiences, key=lambda x: x["experience"]["intensity"])
        most_novel = max(experiences, key=lambda x: x["experience"]["novelty"])

        insights.append(
            {
                "substance": substance,
                "cycles": len(experiences),
                "emotional_range": list(unique_emotions),
                "emotional_stability": len(unique_emotions),
                "most_intense": most_intense["experience"]["description"],
                "intensity_score": most_intense["experience"]["intensity"],
                "most_novel": most_novel["experience"]["description"],
                "novelty_score": most_novel["experience"]["novelty"],
                "recent_state": experiences[-1]["emotional_state"],
            }
        )

    return insights


def character_lines(insights: list[dict[str, Any]]) -> list[str]:
    """Render the per-character section."""
    lines = ["Character Insights", "-" * 30]
    for insight in insights:
        lines.extend(
            [
                "",
                f"  {str(insight['substance']).title()}:",
                f"   Cycles: {insight['cycles']}",
                f"   Emotional Range: {', '.join(insight['emotional_range'])}",
                f"   Stability: {insight['emotional_stability']}/5 emotions",
                f"   Most Intense: '{insight['most_intense']}' ({insight['intensity_score']:.2f})",
                f"   Most Novel: '{insight['most_novel']}' ({insight['novelty_score']:.2f})",
                f"   Current State: {insight['recent_state']}",
            ]
        )
    return lines


def trend_for(stability: int) -> str:
    """Describe an emotional-stability count as an observation."""
    if stability == FOCUSED_EMOTION_COUNT:
        return "Highly focused evolution"
    if stability <= NARROW_EMOTION_COUNT:
        return "Exploring different emotional states"
    return "Broad emotional exploration"


def cross_character_lines(insights: list[dict[str, Any]]) -> list[str]:
    """Render cross-character patterns and development observations."""
    lines = ["", "Cross-Character Patterns", "-" * 30]

    all_emotions: list[str] = []
    for insight in insights:
        all_emotions.extend(insight["emotional_range"])

    emotion_counts = Counter(all_emotions)

    lines.append("Most Common Emotional States:")
    for emotion, count in emotion_counts.most_common(TOP_EMOTIONS):
        lines.append(f"   {emotion}: {count} occurrences")

    lines.extend(["", "Development Observations:"])
    for insight in insights:
        if insight["cycles"] < MIN_CYCLES_FOR_OBSERVATION:
            continue
        lines.append(f"   {insight['substance']}: {trend_for(insight['emotional_stability'])}")

    return lines


def analyze_patterns() -> None:
    """Analyze emotional patterns and insights across characters."""
    base_path = resolve_base_path()
    journals_path = base_path / "journals"

    lines = [
        "Temporal Insights & Patterns",
        "=" * 50,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    insights = collect_insights(journals_path)
    if insights:
        lines.extend(character_lines(insights))
        lines.extend(cross_character_lines(insights))

    for line in lines:
        print(line)

    # Persist plain text report
    report_file = base_path / "insights_report.txt"
    report_file.write_text("\n".join(lines) + "\n")
    print()
    print(f"Report saved to {report_file}")


if __name__ == "__main__":
    analyze_patterns()

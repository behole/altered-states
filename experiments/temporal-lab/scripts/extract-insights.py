#!/usr/bin/env python3
"""
Extract interesting insights and patterns from temporal journals.
"""

import json
from datetime import datetime
from collections import Counter

from characters import resolve_base_path

def analyze_patterns():
    """Analyze emotional patterns and insights across characters"""
    base_path = resolve_base_path()
    journals_path = base_path / "journals"

    # Buffer output for dual write (console + file)
    output_lines = []

    def emit(text=""):
        print(text)
        output_lines.append(text)

    emit("Temporal Insights & Patterns")
    emit("=" * 50)
    emit(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit()

    insights = []

    # Analyze each character
    for journal_file in journals_path.glob("*_journal.json"):
        substance = journal_file.stem.replace("_journal", "")

        with open(journal_file, 'r') as f:
            journal = json.load(f)

        if len(journal) < 2:
            continue

        # Skip initial entry (has no experience)
        experiences = [entry for entry in journal if 'experience' in entry]
        if not experiences:
            continue

        # Emotional pattern analysis
        emotions = [entry['emotional_state'] for entry in experiences]
        unique_emotions = set(emotions)

        # Most intense experience
        max_intensity = max(entry['experience']['intensity'] for entry in experiences)
        most_intense = max(experiences, key=lambda x: x['experience']['intensity'])

        # Most novel experience
        max_novelty = max(entry['experience']['novelty'] for entry in experiences)
        most_novel = max(experiences, key=lambda x: x['experience']['novelty'])

        insights.append({
            'substance': substance,
            'cycles': len(experiences),
            'emotional_range': list(unique_emotions),
            'emotional_stability': len(unique_emotions),
            'most_intense': most_intense['experience']['description'],
            'intensity_score': max_intensity,
            'most_novel': most_novel['experience']['description'],
            'novelty_score': max_novelty,
            'recent_state': experiences[-1]['emotional_state']
        })

    # Display insights
    if insights:
        emit("Character Insights")
        emit("-" * 30)

        for insight in insights:
            emit()
            emit(f"  {insight['substance'].title()}:")
            emit(f"   Cycles: {insight['cycles']}")
            emit(f"   Emotional Range: {', '.join(insight['emotional_range'])}")
            emit(f"   Stability: {insight['emotional_stability']}/5 emotions")
            emit(f"   Most Intense: '{insight['most_intense']}' ({insight['intensity_score']:.2f})")
            emit(f"   Most Novel: '{insight['most_novel']}' ({insight['novelty_score']:.2f})")
            emit(f"   Current State: {insight['recent_state']}")

        # Cross-character patterns
        emit()
        emit("Cross-Character Patterns")
        emit("-" * 30)

        # Common emotions
        all_emotions = []
        for insight in insights:
            all_emotions.extend(insight['emotional_range'])

        emotion_counts = Counter(all_emotions)

        emit("Most Common Emotional States:")
        for emotion, count in emotion_counts.most_common(3):
            emit(f"   {emotion}: {count} occurrences")

        # Development phases
        emit()
        emit("Development Observations:")
        for insight in insights:
            if insight['cycles'] >= 3:
                if insight['emotional_stability'] == 1:
                    trend = "Highly focused evolution"
                elif insight['emotional_stability'] <= 2:
                    trend = "Exploring different emotional states"
                else:
                    trend = "Broad emotional exploration"

                emit(f"   {insight['substance']}: {trend}")

    # Persist plain text report
    report_file = base_path / "insights_report.txt"
    with open(report_file, "w") as f:
        f.write("\n".join(output_lines) + "\n")
    emit()
    emit(f"Report saved to {report_file}")

if __name__ == "__main__":
    analyze_patterns()

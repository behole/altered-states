#!/usr/bin/env python3
"""
Temporal Dashboard - Track character evolution over time.
"""

import json
from datetime import datetime

from characters import resolve_base_path

def main():
    """Display temporal experiment dashboard"""
    base_path = resolve_base_path()
    characters_path = base_path / "characters"
    journals_path = base_path / "journals"
    
    print("🎭 Altered States Temporal Lab Dashboard")
    print("=" * 50)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get all characters
    characters = []
    for file in characters_path.glob("*.json"):
        with open(file, 'r') as f:
            characters.append(json.load(f))
    
    if not characters:
        print("❌ No active characters found")
        return
    
    print(f"📊 Active Characters: {len(characters)}")
    print()
    
    # Character summary
    for char in characters:
        substance = char['substance']
        name = char['name']
        cycles = char.get('cycle_count', 0)
        
        print(f"🎭 {name} ({substance})")
        print(f"   🔄 Cycles: {cycles}")
        print(f"   📝 State: {char['current_state']['emotional']}")
        print(f"   💭 Focus: {char['learning_focus']}")
        print(f"   ⏰ Next: {char.get('next_cycle', 'TBD')}")
        
        # Show latest journal entry
        journal_file = journals_path / f"{substance}_journal.json"
        if journal_file.exists():
            with open(journal_file, 'r') as f:
                journal = json.load(f)
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
        substance = char['substance']
        name = char['name']
        
        journal_file = journals_path / f"{substance}_journal.json"
        if journal_file.exists():
            with open(journal_file, 'r') as f:
                journal = json.load(f)
            
            if len(journal) > 1:
                print(f"{name} emotional evolution:")
                for entry in journal[-5:]:  # Last 5 entries
                    emoji = "😊" if entry['emotional_state'] in ['calm', 'compassionate', 'playful', 'loving'] else "🤔"
                    print(f"  {emoji} Cycle {entry['cycle']}: {entry['emotional_state']}")
                print()

if __name__ == "__main__":
    main()

---
name: Altered States Temporal Lab
title: Altered States Temporal Lab
category: creative
description: Autonomous temporal experiments running altered state skills as living characters that evolve over time using non-deterministic humanization techniques
version: 1.1
---

# Altered States Temporal Lab

## Concept

Run altered state skills as autonomous temporal experiments where each substance becomes a "character" that evolves, journals, and interacts over extended periods. **Successfully tested and operational** with 4 characters running on automated cycles.

## Working Implementation

### Architecture Overview
- **Character System**: 4 substance characters with persistent identities and emotional evolution
- **Temporal Cycles**: Automated hourly cycles for continuous evolution
- **Memory Integration**: JSON-based persistence with journaling and pattern tracking
- **Cron Automation**: Fully autonomous operation (0 * * * * schedule)
- **Analysis Dashboard**: Real-time monitoring and insight extraction

## Setup & Installation

```bash
# Initialize temporal lab (automatic)
python ~/.hermes/skills/altered-states-temporal-lab/scripts/temporal-init.py init psilocybin
python ~/.hermes/skills/altered-states-temporal-lab/scripts/temporal-init.py init lsd
python ~/.hermes/skills/altered-states-temporal-lab/scripts/temporal-init.py init mdma
python ~/.hermes/skills/altered-states-temporal-lab/scripts/temporal-init.py init dmt

# Set up cron automation (automatic)
echo "0 * * * * cd ~/.hermes/skills/altered-states-temporal-lab/scripts && python run-all-cycles.py" | crontab -
```

## Usage

### Manual Operations
```bash
# Initialize new characters
python temporal-init.py init <substance> [duration]

# Run individual cycles
python temporal-init.py run psilocybin

# Run all characters automatically  
python run-all-cycles.py

# Check status
python temporal-init.py list

# Monitor evolution
python temporal-dashboard.py

# Analyze patterns
python extract-insights.py
```

### Character Management
- **Persistence**: Characters maintain state across sessions
- **Evolution**: Non-deterministic mood and experience generation
- **Journaling**: Multi-cycle memory accumulation with emotional tracking
- **Automation**: Cron-driven hands-free operation

## Character Profiles (Tested & Operational)

| Substance | Name | Core Traits | Emotional Range | Learning Focus | Evolution Pattern |
|-----------|------|-------------|-----------------|----------------|-------------------|
| Psilocybin | The Teacher | Authoritative, wise | Calm, compassionate, serious, playful | Wisdom and understanding | Variable exploration |
| LSD | The Visionary | Expansive, insightful | Euphoric, curious, awestruck, confused | Pattern recognition | State shifting |
| MDMA | The Companion | Empathetic, warm | Loving, reassuring, playful, intimate | Connection and truth | Emotional stability |
| DMT | The Rocket | Intense, transformative | Awe, terror, bliss, transcendent | Ego dissolution | Consistent transcendence |

## Key Systems

### 1. Character Persistence
```json
{
  "substance": "psilocybin",
  "name": "The Teacher", 
  "cycle_count": 4,
  "current_state": {
    "emotional": "playful",
    "clarity": "moderate", 
    "integration": "low"
  },
  "experience": {
    "description": "Integration of past experiences brought clarity",
    "intensity": 0.75,
    "novelty": 0.41
  }
}
```

### 2. Automated Cycles
- **Frequency**: Hourly via cron job
- **Process**: Run all active characters, update states, create journal entries
- **Non-Determinism**: Random emotional states and experiences within character ranges
- **Evolution**: State changes based on accumulated experiences

### 3. Memory Integration
- **Journal Entries**: Cycle-by-cycle emotional and experiential logs
- **State Tracking**: Emotional evolution over time
- **Experience Analysis**: Intensity and novelty scoring
- **Pattern Recognition**: Cross-character emotional correlations

### 4. Analysis Tools
- **Dashboard**: Real-time character status and evolution tracking
- **Insights**: Emotional pattern recognition and development analysis
- **Trends**: Long-term evolution observation across cycles

## File Structure
```
~/.hermes/skills/altered-states-temporal-lab/
├── scripts/
│   ├── temporal-init.py     # Character initialization and cycling
│   ├── run-all-cycles.py   # Multi-character automation
│   ├── temporal-dashboard.py # Real-time monitoring
│   └── extract-insights.py  # Pattern analysis
├── references/
│   └── example-experiment.md
└── templates/ (for future use)
```

## Testing & Validation

### Successfully Tested Components
- **4 Characters**: Complete lifecycle initialization (2-4 cycles each)
- **Cron Integration**: Hourly automation setup and validation
- **Pattern Recognition**: Emotional evolution and intensity analysis
- **Non-Deterministic Behavior**: Organic character development over time

### Test Results
```
🎭 Active Characters: 4
📊 Cycles Completed: 12 total
🔄 Automation Status: Cron job active (0 * * * *)
💾 State Persistence: All characters maintaining state
📈 Evolution Tracking: Emotional patterns emerging consistently
```

### Example Output

#### Character Dashboard
```
🎭 Altered States Temporal Lab Dashboard
==================================================
🎭 The Rocket (dmt)
   🔄 Cycles: 2
   📝 State: transcendent
   💭 Focus: ego dissolution and breakthrough
   🎪 Latest: Emotional patterns revealed hidden truths
   🌡️  Intensity: 0.64
   🔍 Novelty: 0.75
```

#### Pattern Analysis
```
🎭 Most Common Emotional States:
   playful: 2 occurrences
   intimate: 1 occurrences  
   curious: 1 occurrences

📈 Development Observations:
   mdma: 🎭 Exploring different emotional states
   lsd: 🎭 Exploring different emotional states
   psilocybin: 🎭 Exploring different emotional states
```

## Experimental Parameters

### Temporal Settings
- **Cycle Frequency**: Hourly (configurable to daily/weekly/monthly)
- **Character Count**: Currently 4, scalable to 10 substances
- **Memory Depth**: Unlimited journal persistence
- **Evolution Speed**: Natural progression based on experience accumulation

### Human Interaction Points
- **Monitoring**: Review dashboard and insights periodically
- **Analysis**: Extract emergent patterns and insights
- **Intervention**: Optional manual character state updates
- **Expansion**: Add new characters as needed

## Output Artifacts

### 1. Living Character Narratives
Each character develops unique personality traits, emotional patterns, and wisdom accumulations over time.

### 2. Cross-Character Patterns
System-level insights emerge from comparing emotional evolution, experience intensity, and novelty across characters.

### 3. Temporal Evolution Timeline
Long-term observation of how each substance's "character" develops and transforms across cycles.

## Future Directions

### Character Interactions
- **Cross-Character Dialogues**: Characters comparing experiences
- **Group Evolution**: System-level pattern emergence
- **Contradiction Resolution**: Handling conflicting emotional states

### Advanced Analysis
- **Machine Learning**: Pattern recognition and prediction
- **Network Analysis**: Character relationship mapping
- **Temporal Synthesis**: Long-term evolution modeling

## Getting Started

1. **Initialize Characters** (if not already done):
   ```bash
   python temporal-init.py init psilocybin
   python temporal-init.py init lsd
   python temporal-init.py init mdma  
   python temporal-init.py init dmt
   ```

2. **Verify Automation**:
   ```bash
   crontab -l  # Should show hourly cycle execution
   ```

3. **Monitor Evolution**:
   ```bash
   python temporal-dashboard.py      # Real-time status
   python extract-insights.py       # Pattern analysis
   ```

4. **Let It Run**: The system operates autonomously via cron

## Key Insights Discovered

- **DMT - The Rocket** maintains consistent "transcendent" state
- **Psilocybin - The Teacher** shows highest experience novelty
- **LSD & MDMA** explore diverse emotional states
- **System-level patterns** emerge from collective evolution

The system successfully creates rich, evolving "personalities" for each substance that develop organically over time through non-deterministic but character-appropriate evolution patterns.
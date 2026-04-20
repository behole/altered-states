# Vault Integration

This temporal lab is designed to integrate with your existing research infrastructure.

## Connection to Altered States Project

This extends your existing [[altered-states]] project with temporal capabilities:

### Before (Static)
- Substance skills evaluated once per session
- Manual skill invocation
- Static character personas
- Manual review process

### After (Temporal) 
- Substance skills as persistent characters
- Autonomous evolution over time
- Dynamic personality development  
- Continuous journaling and pattern extraction

## Research Workflow Integration

### 1. Setup Phase
```bash
# Initialize characters in your vault
cd altered-states-temporal-lab/scripts
python temporal-init.py init <substance>
```

### 2. Evolution Phase
```bash
# Let characters evolve autonomously
# Hourly cycles + weekly deep cycles
# Monitor via dashboard
python temporal-dashboard.py
```

### 3. Analysis Phase  
```bash
# Extract insights and patterns
python extract-insights.py
# Use insights to inform static skill evaluations
```

### 4. Integration Phase
- Cross-reference temporal insights with static skill outputs
- Identify evolution patterns vs static patterns
- Update substance personas based on temporal observations

## Data Synthesis

### Temporal → Static Pipeline
1. Collect temporal evolution data
2. Identify persistent character traits
3. Refine static skill personas
4. Update skill parameters based on observed patterns

### Enhanced Evaluation
- Compare static skill responses vs temporal character evolution
- Identify consistency vs divergence patterns
- Refine evaluation criteria based on temporal observations

## File Structure in Vault

```
altered-states-temporal-lab/           ← Root folder
├── README.md                          ← Overview and setup
├── VAULT-INTEGRATION.md              ← Integration guide
├── SKILL.md                          ← Technical implementation
├── references/
│   └── example-experiment.md         ← Example experiment design
├── scripts/                          ← Operational scripts
│   ├── temporal-init.py             ← Character management
│   ├── temporal-dashboard.py         ← Real-time monitoring
│   ├── extract-insights.py          ← Pattern analysis
│   └── run-all-cycles.py            ← Automation
└── templates/                        ← Future expansion
```

## Dependencies

This requires:
- Python 3.7+ with JSON support
- Cron access for automation
- Git integration for version control (already in vault)

## Contributing

Changes here should be committed to maintain version history and enable reproducibility of temporal experiments.

---
*Integrates with [[research]] and [[projects]] workflows*

# Temporal Lab

An experiment directory that runs each of the 10 altered-states characters as an autonomous persistent entity. Each character has its own JSON state file, journals its cycles, and evolves its emotional state and phenomenology over time using a substance-appropriate vocabulary.

This lives inside the main [`altered-states`](../../README.md) project so the characters stay in sync with the canonical skill definitions.

## Quick Start

```bash
cd experiments/temporal-lab/scripts

# Initialize any of the 10 characters
python temporal_init.py init psilocybin
python temporal_init.py init ayahuasca
python temporal_init.py init salvia
# ...

# Run one cycle for one character
python temporal_init.py run psilocybin

# Run one cycle for every active character (cron target)
python run-all-cycles.py

# List active characters
python temporal_init.py list

# Monitor evolution
python temporal-dashboard.py

# Pattern analysis across journals
python extract-insights.py
```

## Storage

State lives in `experiments/temporal-lab/runtime/` by default (gitignored).

Override with the `ALTERED_STATES_TEMPORAL_PATH` env var if you want state to persist elsewhere (e.g. `~/.altered-states/temporal-lab`).

```bash
export ALTERED_STATES_TEMPORAL_PATH=~/.altered-states/temporal-lab
python run-all-cycles.py
```

## The Ten Characters

Names and traits are the canonical ones from the main README. See `scripts/characters.py` for the full definitions.

| Substance | Name | Focus |
|---|---|---|
| 🍄 Psilocybin | The Teacher | wisdom and understanding |
| ⚡ LSD | The Technician | pattern recognition |
| 💊 MDMA | The Connector | connection and emotional truth |
| 🚀 DMT | The Rocket | ego dissolution and breakthrough |
| 🌿 Ayahuasca | The Medicine | moral teaching through vision |
| 💎 5-MeO-DMT | The Dissolver | total ego dissolution into source |
| 🌵 Mescaline | The Elder | communion with land and beauty |
| 🕳️ Ketamine | The Dissociative | watching self from outside |
| 🚪 Salvia | The Doorway | forced reality dissolution |
| 🪬 Ibogaine | The Ancestor | death-rebirth and life review |

## How cycles are grounded

Each cycle samples an experience fragment from a substance-specific pool in `characters.py` — so a DMT cycle produces fragmented, language-failing content and a mescaline cycle produces patient, color-rich contemplation. Emotional state is sampled from the character's emotional range, also substance-specific.

This replaces the original generic "deep insights emerged about consciousness and reality" template that was substance-agnostic.

## File Layout

```
experiments/temporal-lab/
├── README.md
├── SKILL.md
├── VAULT-INTEGRATION.md
├── .gitignore
├── references/
│   └── example-experiment.md
├── scripts/
│   ├── characters.py         # canonical character + experience vocab (shared)
│   ├── temporal_init.py      # CLI: init / list / run
│   ├── run-all-cycles.py     # cron target: run every active character
│   ├── temporal-dashboard.py # live status view
│   └── extract-insights.py   # cross-character pattern analysis
└── runtime/                  # gitignored — characters/, journals/, experiments/
```

## Cron

```bash
# Example: hourly cycles
(crontab -l 2>/dev/null; echo "0 * * * * cd /path/to/altered-states/experiments/temporal-lab/scripts && /usr/bin/python3 run-all-cycles.py >> /tmp/temporal-lab.log 2>&1") | crontab -
```

## Relationship to the legacy sibling project

An earlier version of this lived at `~/26/2026L/the-factory/altered-states-temporal-lab/` with 4 substances and stored state in `~/temporal-lab/`. That version remains untouched for backward compatibility.

The in-repo version here is the canonical one going forward: all 10 substances, substance-specific experience vocabulary, repo-local runtime, and a single shared `characters.py` module so the CLI, cron runner, and dashboards never drift apart.

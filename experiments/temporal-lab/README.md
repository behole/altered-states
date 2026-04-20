# Temporal Lab

Each of the 10 altered-states characters runs as an autonomous persistent entity. Characters have JSON state, journal their cycles, and **invoke a real LLM** with the full SKILL.md every cycle so each cycle is genuinely novel — not sampled from a fixed vocabulary.

This lives inside the main [`altered-states`](../../README.md) project so the characters stay in sync with the canonical skill definitions.

## Setup

```bash
cd experiments/temporal-lab

# 1. Install deps
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# edit .env, paste your OpenRouter key from https://openrouter.ai/keys
```

## Quick Start

```bash
cd experiments/temporal-lab/scripts

# Initialize all 10 characters
for s in psilocybin lsd mdma dmt ayahuasca 5-meo-dmt mescaline ketamine salvia ibogaine; do
  python temporal_init.py init "$s"
done

# Verify wiring without burning tokens
TEMPORAL_LAB_DRY_RUN=1 python temporal_init.py run psilocybin

# Real cycle (one character)
python temporal_init.py run psilocybin

# Run cycles for every character whose cadence is due (cron target)
python run-all-cycles.py

# Inspect
python temporal_init.py list
python temporal_init.py costs
python temporal-dashboard.py
python extract-insights.py
```

## How cycles work

Every cycle is a real LLM call:

1. The dispatcher selects characters whose per-substance cadence is due (see `cadence.py`)
2. For each due character, the lab assembles a prompt: **full SKILL.md + current character state + last 3 journal entries**
3. Sends to OpenRouter (default model: Claude Sonnet 4.6, override via `TEMPORAL_LAB_MODEL`)
4. Parses a JSON response with `emotional_state`, `clarity`, `integration`, `experience.{description,intensity,novelty}`, `reflections[]`, `questions[]`
5. Updates character state, appends to journal, logs cost

Failures (API down, rate limit, malformed JSON) retry 3× with exponential backoff (2s/8s/32s). Terminal failure writes a "silence" entry into the journal so the character "remembers" it went dark.

## Per-substance cadence

Cycle frequency loosely mirrors the *narrative spacing between trips* — not the real dose duration (which would mean salvia firing every 10 minutes). Tunable in `cadence.py`.

| Substance | Cycle every | Real dose arc |
|---|---|---|
| 5-MeO-DMT, DMT, Salvia | 1 hr | 2-20 min |
| Ketamine | 2 hr | 30-60 min IV |
| Psilocybin, MDMA | 6 hr | 3-6 hr |
| LSD, Ayahuasca, Mescaline | 12 hr | 4-14 hr |
| Ibogaine | 24 hr | 12-24 hr |

Daily cycle volume: ~99 calls. At Sonnet 4.6 (~$0.03/call) → ~$3/day, ~$90/month. Switch to Haiku via `TEMPORAL_LAB_MODEL=anthropic/claude-haiku-4.5` to drop ~10×.

## Cron

Run the dispatcher every 15 min. The dispatcher decides which characters are actually due.

```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * cd /path/to/altered-states/experiments/temporal-lab/scripts && /usr/bin/python3 run-all-cycles.py >> /tmp/temporal-lab.log 2>&1") | crontab -
```

## Storage

State lives in `experiments/temporal-lab/runtime/` by default (gitignored).

```
runtime/
├── characters/<substance>.json     # persistent character state
├── journals/<substance>_journal.json
├── experiments/                     # reserved for future cross-character runs
└── logs/
    ├── 2026-04-19.log              # one structured line per call
    └── cost-ledger.csv             # append-only cost record
```

Override location with `ALTERED_STATES_TEMPORAL_PATH=~/.altered-states/temporal-lab`.

## Models

OpenRouter ID, set via `TEMPORAL_LAB_MODEL` in `.env` or `--model` flag:

| Model | Tier | Notes |
|---|---|---|
| `anthropic/claude-sonnet-4.6` | default | balanced quality / cost |
| `anthropic/claude-haiku-4.5` | budget | ~10× cheaper, voice fidelity drops |
| `anthropic/claude-opus-4.6` | premium | top quality, ~5× Sonnet cost |
| `openai/gpt-5` | alt | strong alternative voice |
| `google/gemini-2.5-pro` | alt | long context, different cadence |
| `deepseek/deepseek-v3` | cheap | high-volume runs, voice varies |

## Dry run

Set `TEMPORAL_LAB_DRY_RUN=1` to skip real API calls and return deterministic stubs. Useful for verifying wiring or testing cron without spending tokens.

## File Layout

```
experiments/temporal-lab/
├── README.md
├── SKILL.md
├── VAULT-INTEGRATION.md
├── .env.example                # template — copy to .env, add your key
├── .gitignore                  # ignores runtime/, .env, __pycache__
├── requirements.txt            # openai SDK + python-dotenv
├── references/
│   └── example-experiment.md
├── scripts/
│   ├── characters.py           # canonical 10-substance definitions
│   ├── cadence.py              # per-substance cycle intervals + dispatcher
│   ├── llm_invoke.py           # OpenRouter client + retry + parsing
│   ├── logger.py               # per-call log + cost ledger
│   ├── temporal_init.py        # CLI: init / list / run / costs
│   ├── run-all-cycles.py       # cron target — runs only due characters
│   ├── temporal-dashboard.py   # live status view
│   └── extract-insights.py     # cross-character pattern analysis
└── runtime/                    # gitignored
```

## Relationship to the legacy sibling project

An earlier 4-substance prototype lived at `~/26/2026L/the-factory/altered-states-temporal-lab/` with state in `~/temporal-lab/`. That version is untouched.

The in-repo version here is canonical going forward: 10 substances, real LLM cycles (no vocab pools), per-substance cadence, repo-local runtime, cost tracking, retry semantics, dry-run mode.

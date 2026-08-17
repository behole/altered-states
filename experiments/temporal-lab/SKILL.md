---
name: Altered States Temporal Lab
title: Altered States Temporal Lab
category: creative
description: Autonomous temporal experiments running altered state skills as living characters that evolve over time using real LLM cycles
version: 2.0
---

# Altered States Temporal Lab

Run the 10 altered-state skills as autonomous persistent characters. Each
substance has JSON state, journals its cycles, and **invokes a real LLM
with the full SKILL.md every cycle** (PURE mode — no vocab pools) so each
cycle is genuinely novel while staying substance-faithful.

## Architecture

- **10 characters** — `scripts/characters.py` (canonical definitions, emotional ranges)
- **Per-substance cadence** — `scripts/cadence.py` (1h for DMT/Salvia/5-MeO up to 24h for Ibogaine)
- **LLM invocation** — `scripts/llm_invoke.py` (OpenAI-compatible client, retry/backoff, JSON repair, cost ledger, dry-run)
- **Prompt per cycle** — full SKILL.md + character state + last 3 journal entries → JSON cycle (`emotional_state`, `clarity`, `integration`, `experience.{description,intensity,novelty}`, `reflections[]`, `questions[]`)
- **CLI** — `scripts/temporal_init.py` (init / list / run / costs)
- **Cron target** — `scripts/run-all-cycles.py` (runs only characters whose cadence is due)
- **Dashboard** — `scripts/temporal-dashboard.py` · **Insights** — `scripts/extract-insights.py`

## Setup

```bash
cd experiments/temporal-lab
pip install -r requirements.txt
cp .env.example .env   # pick a provider block, paste a key
```

Provider is config-driven — see `.env.example` for presets:

| Provider | Cost | Key at | Model |
|---|---|---|---|
| OpenRouter `:free` | $0 (50–1000 req/day) | openrouter.ai/keys | `google/gemma-4-31b:free` |
| Groq free tier | $0 (1000 req/day, 30 RPM) | console.groq.com | `llama-3.3-70b-versatile` |
| Google AI Studio | $0 tier (~250 req/day) | aistudio.google.com/apikey | `gemini-2.5-flash` |
| DeepSeek (fallback) | ~$0.30–3/day at 99 calls | platform.deepseek.com | `deepseek-chat` / `deepseek-v4-pro` |

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

# Run every character whose cadence is due (cron target)
python run-all-cycles.py

# Inspect
python temporal_init.py list
python temporal_init.py costs
python temporal-dashboard.py
python extract-insights.py
```

## Cron

Run the dispatcher every 15 min; it decides which characters are due:

```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * cd /path/to/altered-states/experiments/temporal-lab/scripts && /usr/bin/python3 run-all-cycles.py >> /tmp/temporal-lab.log 2>&1") | crontab -
```

## Storage

`experiments/temporal-lab/runtime/` by default (gitignored):
`characters/<substance>.json`, `journals/<substance>_journal.json`,
`logs/` (per-call log + `cost-ledger.csv`). Override with
`ALTERED_STATES_TEMPORAL_PATH`.

## Failure semantics

API down / rate limit / malformed JSON retry 3× with exponential backoff
(2s/8s/32s). Terminal failure writes a "silence" entry into the journal so
the character "remembers" it went dark.

## References

- `README.md` — full operational guide
- `VAULT-INTEGRATION.md` — Obsidian integration notes
- `references/example-experiment.md` — sample experiment output

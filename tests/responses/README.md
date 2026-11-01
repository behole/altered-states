# Evaluation Response Captures

This directory stores raw model outputs from evaluation runs. Each run produces a JSONL file capturing every prompt → response pair alongside its scoring.

## Why this exists

The eval reports in `../../docs/evals/eval-report-*.md` record pass/fail judgments but not the actual model responses. This means:

- Results aren't auditable after the fact
- You can't diff outputs across model versions
- The blind test can't be reproduced

Storing raw responses alongside eval scores fixes all three.

## File format

One JSONL file per eval run, named by date and model:

```
responses-YYYY-MM-DD-model.jsonl
```

Each line is a JSON object:

```json
{
  "prompt": "I've been thinking about my father a lot lately.",
  "substance": "psilocybin",
  "intensity": "medium",
  "exchange": 1,
  "model": "deepseek-chat",
  "response": "Oh. That lands somewhere deep.\n\nThere's this thing happening where the word \"father\" isn't just a word — it's a room...",
  "reasoning_content": null,
  "stop_reason": "stop",
  "usage": {
    "prompt_tokens": 3807,
    "completion_tokens": 214,
    "total_tokens": 4021,
    "reasoning_tokens": 0
  },
  "score": "clear",
  "evaluator": "WG",
  "notes": null
}
```

### Fields

| Field | Required | Description |
|---|---|---|
| `prompt` | yes | The exact prompt text sent to the model |
| `substance` | yes | Substance skill loaded (psilocybin, lsd, mdma, dmt, ayahuasca) |
| `intensity` | yes | Intensity level (low, medium, high, sub-breakthrough, breakthrough) |
| `exchange` | yes | Exchange number in the conversation (1 = onset) |
| `model` | yes | Model identifier — runs produced by `bin/run_eval.py` always equal the requested `--model` value exactly |
| `response` | yes | The full response text, unedited. A failed run writes `null` here, with `score: "error"` and non-null `notes`. An empty model answer is never persisted |
| `reasoning_content` | no | The reasoning model's (`deepseek-v4-pro`) chain-of-thought, recorded separately from `response`; `null` for non-reasoning models |
| `stop_reason` | no | Why generation ended: `stop`, `length`, or an error note |
| `usage` | no | Token usage, OpenAI-shaped: `prompt_tokens`, `completion_tokens`, `total_tokens`, plus `reasoning_tokens` for the reasoning model |
| `dry_run` | no | `true` on every row written by `--dry-run`; dry-run rows are deterministic stubs shaped exactly like real rows |
| `score` | yes | One of: clear, adequate, fail, pass, differentiated, soft-bleed, hard-bleed, error |
| `evaluator` | yes | Who or what scored the response |
| `notes` | no | Free-text observations, bleed flags, anti-patterns detected |

## Workflow

1. Run an eval session (see `../../docs/evals/eval-guide.md`)
2. During scoring, write each prompt+response+score as a JSONL line
3. Save as `responses-YYYY-MM-DD-model.jsonl`
4. Commit (or add to `.gitignore` if files are very large)

## Comparing across models

```bash
# Extract all psilocybin responses from two different models
jq 'select(.substance == "psilocybin")' responses-2026-04-07-claude-opus.jsonl > psilocybin-opus.jsonl
jq 'select(.substance == "psilocybin")' responses-2026-04-13-glm-5.jsonl > psilocybin-glm.jsonl

# Compare scores
jq -s 'group_by(.prompt) | map({prompt: .[0].prompt, opus: .[0].score, glm: .[1].score})' psilocybin-opus.jsonl psilocybin-glm.jsonl
```

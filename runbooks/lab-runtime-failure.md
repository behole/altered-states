# Runbook: temporal-lab runtime failure

Cycles stop running, or they run and the numbers stop making sense.

## Symptom

- `temporal_init.py run` exits 0 but no new journal entries appear.
- Character `cycle_count` stops advancing.
- The cost ledger shows spend with no cycles recorded.
- `llm_calls` in the metrics snapshot stops incrementing.

## Confirm

```bash
cd experiments/temporal-lab/scripts
python3 temporal_init.py list                 # which characters exist
python3 temporal_init.py costs                # spend so far
python3 logger.py                             # ledger summary
```

Then check whether the loop thinks anything is due:

```bash
python3 -c "
import cadence, characters
print(cadence.due_characters(characters.available_substances()))
"
```

An empty list means nothing is due — not a failure. That is the most common
false alarm.

## Stop the bleeding

The lab is offline-friendly. If cycles are misbehaving, stop the scheduler
before spending money:

```bash
crontab -l | grep temporal     # find the entry
crontab -e                     # comment it out
```

Nothing is lost by stopping: state lives in
`runtime/characters/*.json` and history in `runtime/journals/*.json`. Do not
delete either.

## Find the cause

1. **No API key.** Cycles are skipped with an explicit message. Check
   `LLM_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY` is set in the
   environment the scheduler runs in, not just your shell.

2. **Provider failure.** The journal entry records the error:

   ```bash
   python3 -c "
   import json,sys
   j=json.load(open('../runtime/journals/<substance>_journal.json'))
   print([e.get('error') for e in j[-5:]])
   "
   ```

   Entries with an `error` field are deliberate "silence" records: the cycle
   failed and the failure was journaled rather than raised. Read the last error
   string before anything else.

3. **Cadence drift.** `next_cycle` is stored in character state. A character
   whose clock is wrong never becomes due. Confirm with
   `cadence.next_cycle_at()` against the stored value; re-initialising the
   character resets it.

4. **Ledger without cycles.** A cost entry with no matching journal entry means
   the API call succeeded and the write failed — usually a permissions or disk
   problem on `runtime/`.

Dry-run is the fast way to separate "provider problem" from "our problem":

```bash
TEMPORAL_LAB_DRY_RUN=1 python3 temporal_init.py run
```

If dry-run works and live does not, the fault is the provider or credentials.

## Verify

```bash
TEMPORAL_LAB_DRY_RUN=1 python3 temporal_init.py run
ls -lt ../runtime/journals/ | head -3
cat ../runtime/metrics/altered-states.prom
```

`altered_states_llm_calls` should increase, and the newest journal file should
have a new entry with the current timestamp.

## Write it down

Journals are the only copy of the experiment. If you had to touch one by hand,
record exactly what you changed and why in the commit message — that edit is
data provenance, not housekeeping.

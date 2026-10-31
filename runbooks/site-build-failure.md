# Runbook: site build failure

`build.py` fails, or it succeeds and the page is wrong.

## Symptom

- `make build` exits non-zero.
- The page renders but a section is empty, or shows `0 temporal cycles`.
- CI job **Docs and site build** is red.
- `build.failed` appears in the log stream.

## Confirm

```bash
python3 build.py; echo "exit=$?"
```

The structured log line tells you which phase failed:

| Last event | Meaning |
|---|---|
| `build.start` only | failure while reading data directories |
| `build.journals_loaded` then nothing | failure in experiments or music |
| `build.complete` present | the build succeeded; the problem is the output |

Then check the metrics snapshot:

```bash
cat runtime/metrics/altered-states.prom
```

`altered_states_build_runs` not incrementing means the build never reached its
success path.

## Stop the bleeding

The site is a static artifact. If the deployed page is broken:

```bash
git log --oneline -- site/index.html | head -5
git restore site/index.html          # back to the last committed page
git commit -m "revert(site): restore last known-good page"
```

That is a full rollback. Cloudflare Pages redeploys on push to `main`.

## Find the cause

1. **Missing data.** `0 temporal cycles` almost always means journals are
   absent from this checkout — they live under
   `experiments/temporal-lab/runtime/journals/` and are not present on every
   machine. This is not a bug; do not "fix" it by editing the generated page.
   Check with:

   ```bash
   ls experiments/temporal-lab/runtime/journals/*.json | wc -l
   ```

2. **Unreadable file.** A single malformed JSON journal is skipped with a log
   event naming the file. Grep for `skip` in the build output.

3. **Template placeholder mismatch.** If the page contains a literal
   `__PERSONAS__`, the template and the build script disagree about a
   placeholder name. Compare `site/index.template.html` against the replacement
   map in `render_page()`.

4. **Flag evaluates off.** A section vanishing without an error is usually a
   flag:

   ```bash
   python -m altered_states.feature_flags show
   FLAG_SITE_MUSIC_SECTION=on python3 build.py   # confirm it comes back
   ```

## Verify

```bash
python3 build.py
test -s site/index.html
grep -c '__PERSONAS__\|__JOURNALS__\|__EXPERIMENTS__\|__MUSIC__\|__FLAGS__' site/index.html   # must be 0
```

## Write it down

If the cause was not in this runbook, add it. If the failure was silent, add a
log event or a metric that would have surfaced it.

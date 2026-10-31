# AGENTS.md

Instructions for AI agents working in this repository. Read this before you
change anything. It is validated by `python bin/check_agents_md.py`, which CI
runs on every push — a documented command that stops working is a broken build.

---

## What this repository is

Two things share one checkout:

1. **A data project.** Markdown "skill" files describe how ten substances alter
   cognition. A build script turns journals, experiment outputs, and generated
   music into a single static page under `site/`.
2. **A small Python codebase.** The build, the watcher, an eval runner that
   calls a model API, and a "temporal lab" that runs characters through cycles
   and writes journal entries.

There is no server, no database, and no user accounts. Everything runs on one
machine or in GitHub Actions. Deploys are static files to Cloudflare Pages.

Read `SAFETY.md` before writing anything user-facing. It defines what the
project claims and refuses to claim.

---

## The 60-second version

```bash
make verify        # everything CI runs: static analysis, tests, security, flags
make check         # static analysis only — use this while iterating
make test          # unit + integration tests
make build         # regenerate site/index.html
```

If `make verify` is green, CI will be green.

---

## Layout

| Path | What lives there |
|---|---|
| `build.py` | Reads journals + experiments + music, fills `site/index.template.html`, writes `site/index.html` |
| `watch.py` | Watches data directories, rebuilds, optionally deploys, serves on :8765 |
| `altered_states/` | Shared library: structured logging, metrics, error tracking, feature flags |
| `bin/` | Eval runner (`run_eval.py`), JSONL→markdown (`responses_to_grid.py`), notebooklm helper, release and label tooling |
| `experiments/temporal-lab/` | Long-running character simulation; scripts run directly with `python3` |
| `experiments/same-prompt/` | One prompt asked of every substance, with the same model settings |
| `experiments/music/` | Song generation and the audio it produced |
| `skills/` | The `SKILL.md` files users install — **content, not code** |
| `site/` | Generated output. Never hand-edit `index.html`; edit the template |
| `tests/` | `unit/` and `integration/`, both offline |
| `runbooks/` | What to do when something is on fire |
| `docs/` | Architecture, research pipeline, design notes |

---

## Rules that will bite you

### 1. `site/index.html` is generated

Edit `site/index.template.html`. `make build` rewrites `index.html`. A pull
request that hand-edits the built file gets reverted by the next cron rebuild.

### 2. Dry-run before you call a model

Every path that spends money has an offline mode:

```bash
python3 bin/run_eval.py --dry-run --substances lsd
python3 experiments/same-prompt/run-ten-ways.py --dry-run
TEMPORAL_LAB_DRY_RUN=1 python3 experiments/temporal-lab/scripts/temporal_init.py run
```

Tests never hit the network. If you add a code path that does, put a dry-run
switch in front of it.

### 3. No secrets in logs, ever

`altered_states.log_utils` redacts by field name (`api_key`, `token`,
`authorization`, …) and by value shape (`sk-…`, `ghp_…`, `Bearer …`, `AKIA…`).
Route new output through `log_event()` rather than `print()` so it gets the
same treatment. Tests in `tests/unit/test_log_utils.py` assert the redaction
rules — add a case when you add a provider.

### 4. New user-visible behaviour goes behind a flag

Declare it in `feature_flags.json`, read it via `altered_states.feature_flags`,
and template it into the page through `__FLAGS__`. `python -m
altered_states.feature_flags check` fails the build when a flag has expired or
is declared but referenced nowhere, so a flag is never permanent by accident.

### 5. Dependencies are pinned and locked

Edit the matching requirements file, then run `make lock` (it recompiles every
`.lock` pair in `bin/`, `experiments/music/`, `experiments/temporal-lab/`, and
the root dev/test pairs `requirements-dev.txt` → `requirements-dev.lock` and
`requirements-test.txt` → `requirements-test.lock`). `deptry` fails on an import that is
not declared or a declared package that is never imported. `pip-audit` fails on
a known CVE in the locked set. Do not add a dependency to avoid writing twenty
lines of code.

### 6. Tests must assert behaviour, not existence

`make test` runs with a coverage floor and `--strict-markers`. A test that only
checks a function returns a non-`None` value is noise. Assert the actual
contract: the exact string emitted, the exact exit code, the mutation that did
or did not happen.

### 7. The temporal-lab scripts are entry points, not a package

`experiments/temporal-lab/scripts/*.py` are run directly (`python3 temporal_init.py`)
and some have hyphens in their names. They bootstrap `sys.path` to import
`altered_states`. Do not convert them into an installable package without
updating `experiments/temporal-lab/README.md` and the cron entries that call them.

---

## Working with the data

Journal entries and experiment outputs are **input data** and are often the only
copy. Treat them as read-only unless the task is explicitly about producing new
entries:

- `experiments/temporal-lab/runtime/journals/*.json` — append-only history
- `experiments/temporal-lab/runtime/characters/*.json` — per-character state
- `experiments/same-prompt/output/*.md` — captured model responses
- `experiments/music/*/` — generated audio and metadata

Never rewrite, truncate, or "clean up" these files. Never delete journal
entries. If a change needs different data, add a new file.

---

## Commands the validators check

`bin/check_agents_md.py` keeps this file honest. It verifies that every section
below still exists, that every path and `make` target named in this file still
resolves, and that the two commands at the end of this block — which need
nothing beyond the standard library — still exit 0. The heavier gates are
checked structurally here because CI already runs them for real.

```bash
make verify
make check
make test
python bin/check_agents_md.py
python -m altered_states.feature_flags check
```

---

## Definition of done

Before you say a change is finished:

1. `make check` passes.
2. `make test` passes, and new behaviour has a test that would fail without the
   change.
3. `make security` passes.
4. `make build` produces a page with no `__PLACEHOLDER__` markers left in it.
5. `pre-commit run --all-files` passes.
6. If behaviour or commands changed, `README.md`, this file, or `runbooks/` was
   updated in the same commit.

Do not disable a check to make it pass. If a check is wrong, change the check
deliberately and say why in the commit message.

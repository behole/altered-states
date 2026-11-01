# Changelog

All notable changes to the Altered States project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-11-01
### Changed
- **Provider migration: DeepSeek is the sanctioned default on all three
  model-call surfaces** — `bin/run_eval.py` now talks to
  `api.deepseek.com/v1` through the OpenAI SDK gated solely on
  `DEEPSEEK_API_KEY`; `experiments/temporal-lab/scripts/llm_invoke.py` and
  `experiments/same-prompt/run-ten-ways.py` resolve keys root-`.env`-first
  with DeepSeek outranking an ambient `OPENROUTER_API_KEY` (ambient
  OpenRouter keys never silently reroute a surface to OpenRouter). The eval
  runner's budget-raise retry is clamped to the model's documented output
  cap (no retry can request more output tokens than the provider accepts),
  the pre-run manifest records that worst-case retry ceiling, error rows
  carry the same key set as success rows, `llm_calls` is counted once per
  request across retries, and a crash after billed API calls persists an
  annotated partial ledger entry so cumulative spend is never under-counted.
- **watch.py serves on a threaded HTTP server** — both serve modes
  (`--serve-only` and default) now use `ThreadingHTTPServer` with daemon
  threads (via the new `watch.make_server()`), so one slow or half-open
  client connection on the shared :8765 watcher can no longer block all
  other requests (the 2026-10-31 quiz-validation wedge, curl 000 for
  minutes). Handler (`SiteHandler`) and shutdown behaviour are unchanged;
  `tests/unit/test_watch.py` gained offline tests proving a wedged
  connection does not block later requests and the server still shuts
  down cleanly.
### Added
- **Skill-tree validator (VAL-TOOL-001, VAL-TOOL-002)** — `bin/check_skills.py`
  (stdlib-only) validates every `SKILL.md` under `skills/` — top-level
  substances, the router, and the nested overlay lines (`skills/combos/*`,
  `skills/tolerance/*`, `skills/afterglow/`) — against the structural
  contract: front-matter schema, Safety Override furniture, 7-dimension ×
  intensity matrix, dose arc, and router alias resolution. Wired into
  `make skills-check` (part of `make verify`); failures exit nonzero naming
  file + section; `--new-skill <path>` prints the same rules as an authoring
  checklist. Seeded-mutation tests in `tests/unit/test_skills_check.py` prove
  the failure paths fire. `_check_dimension_table` now also guards the table
  shape itself: the header row must carry its intensity columns (at least one
  column beyond `#`/Dimension) and every data row must have the header's cell
  count — deleting a dimension-table COLUMN (fully or header-cells-only) exits
  nonzero citing file + dimensions section instead of passing. A per-skill
  scale registry (`EXPECTED_TABLE_SCALES`) additionally pins the exact
  header column labels of every table-carrying skill case-insensitively, so
  the run-3 VAL-TOOL-001 class — a whole intensity column deleted from the
  header AND every row consistently (size-coherent, labels wrong) — is
  rejected with file + sections + fix, including overlay-line tables
  (afterglow, tolerance) and inconsistent column renames.
- **Content safety lint (VAL-TOOL-003, VAL-TOOL-004)** — `bin/safety_lint.py`
  (stdlib-only) scans every Markdown file under `skills/` AND the built
  `site/index.html` for forbidden patterns: dose figures with dosing verbs,
  dosing-schedule/posology phrasing, therapy/guidance claims, and
  sourcing-language slips. Wired into `make safety-lint` (part of
  `make security` and `make verify`); findings name file:line. The scoped
  allowlist contract is documented in the module docstring and proven
  defeat-proof in `tests/unit/test_safety_lint.py`: an inline
  `<!-- safety-lint: allow: rule -- reason: ... -->` can never rescue a
  full-line dose-figure match.
- **Golden snapshot tests (VAL-TOOL-005)** — snapshot tests for build.py's
  derived JSON payloads (camelCase personas, journal-series dashboards, and
  masked quiz game) against committed fixture directories under
  `tests/fixtures/golden/`. Snapshots are keyed on a content hash of the
  fixture inputs, so changed inputs without re-snapshotting fail loudly, and
  a seeded key rename of the personas contract fails with a named diff.
  Re-snapshot intended changes with
  `UPDATE_GOLDEN_SNAPSHOTS=1 pytest tests/unit/test_golden_snapshots.py`
  (the env var overwrites existing snapshots unconditionally, so the
  regeneration instruction always works).
- **Skill installer (VAL-TOOL-006)** — `bin/install_skills.py` installs the
  full skill set (substances, router, combos, tolerance overlays, afterglow)
  to the platform-correct skills directory in one command (darwin ->
  `~/.claude/skills`, linux -> `~/.config/opencode/skills`; `--dest`
  override documented, installer refuses `--dest` inside the source
  `skills/` tree). Dry run by default; `--apply` copies, `--link` symlinks;
  `--skill` selects one; `--list` prints the default set and the platform
  table. Offline unit-tested in `tests/unit/test_install_skills.py`.
- **Build-time OG share cards (VAL-TOOL-007)** — `make build` now renders one
  share card per substance skill into `site/og/<substance>.png` (11 cards
  today, incl. 2C-B), deterministic and byte-identical across delete+rebuild.
  The committed `site/og/placeholder.svg` placeholder is retired: a build
  clears its card assets (one card filename per substance slug, plus the
  placeholder) from `site/og/` before regenerating, so stale cards cannot
  survive; foreign files in `site/og/` are never touched. Cards carry the
  substance name, its one-line character, and the leading sentence of its
  description.
  **Format choice (documented, not silent):** PNG rendered with
  Pillow (`pillow==13.0.0`, pinned in `bin/requirements.txt` +
  `bin/requirements.lock`) — the pip-audit-clean line; because major
  crawlers (Facebook, Twitter/X, iMessage) ignore inline SVG as
  `og:image`; in an environment without
  Pillow the generator falls back to a deterministic SVG and logs
  `build.og_cards format=svg` so the deviation is observable. Card bytes
  are stable within a given Pillow version (delete+rebuild
  byte-identical); the pinned version defines the committed card bytes,
  so the Python that builds the site must have the locked Pillow —
  `make build` now enforces that itself (`BUILD_PY` pins
  `--with pillow==13.0.0`, the same line the `PYTEST` test env uses),
  and a CI byte-comparison test asserts the committed
  `site/og/*.png` bytes equal the pinned-Pillow render.
  Pillow 13 requires Python >= 3.11, so `bin/requirements.lock` now
  resolves for 3.11 (the oldest interpreter that installs it — CI test
  matrix moved 3.10 -> 3.11; ruff/mypy still lint Python 3.10 syntax).
  Per-substance pages now embed **absolute** OG URLs built from the
  canonical deploy base documented in `build.py`
  (`CANONICAL_BASE_URL = "https://altered-states.pages.dev"`): both
  `og:url` (`.../<substance>/`) and `og:image` (`.../og/<substance>.png`)
  are spec-compliant absolute URLs, replacing the previously relative
  values. Verified by the new `tests/unit/test_og_cards.py`.
- **Per-substance eval-grid sections (Cross-model & Grids views)** —
  `site/index.html` now ships two data-driven sections: the cross-model
  diff (`site.cross_model_diff`, owner eval) showing DeepSeek responses
  side-by-side with the historical same-prompt corpora
  (anthropic/claude-sonnet-4.6, zai/glm-5-turbo), and the eval grids
  (`site.eval_grids`, owner site) publishing every prompt/run with
  model-tagged, run-toggleable cells. Both payloads derive deterministically
  from the committed artifacts under `tests/responses/` and
  `experiments/same-prompt/output/` (see `tests/responses/README.md` for
  the glob scope both sections consume).
- **Per-substance static pages** — `make build` now also writes one
  standalone, deterministic page per substance skill under
  `site/<substance>/index.html` (10 at this milestone: every `skills/*` dir
  minus the router), rendered from the new dedicated template
  `site/substance.template.html`. Each page carries the substance name in
  its `<title>`, OG meta tags (og:title, og:description, og:image — a
  committed placeholder card at `site/og/placeholder.svg` until build-time
  OG card generation lands), an explicit back-link to the home page, and a
  JSON payload for future per-page sections. Pages regenerate deterministically
  (byte-identical delete+rebuild; stale generated page dirs are removed).
  Every page is a pure function of `skills/<substance>/SKILL.md` front matter
  plus the fixed persona identity table. Gated by `site.substance_pages`:
  when off, home renders zero links to them and page generation is skipped.
- **Home substance-page links (flag-gated)** — with `site.substance_pages`
  on, the SPA home renders a "Substance Pages" link section (one card per
  substance) whose hrefs are the built `/<substance>/` pages; the whole
  section is compile-out when the flag is off. Verified by
  `tests/unit/test_substance_pages.py`.
- **2C-B: the 11th substance skill (`skills/2c-b/SKILL.md`) + research
  (`research/2c-b/`)** — The Chameleon: the empathogenic + psychedelic visual
  blend, distinctive among the suite for the mixture profile, four intensity
  levels, dimension matrix, arc, set/setting matrix, descent, and Safety
  Override furniture in the house style. The research half carries an
  annotated `sources.md` and a `dossier.md` grounded in real, verifiable
  citations (Halberstadt & Geyer on 2C-B pharmacology, de Boer 1999,
  Giroud et al. 1998 Swiss analytical record — including the correction note
  for the dosing figure circulated from it, Caudevilla 2012, and Shulgin &
  Shulgin's PiHKAL qualitative descriptions with the PiHKAL-era limitations
  stated). Router aliases limited to the verified slang set
  (2c-b/2cb/2c b/nexus/bees/venus/the chameleon); the unverified "bump"
  alias was checked and deliberately dropped.
- **First-class combos overlay skills (`skills/combos/`)** —
  `skills/combos/candy-flip/SKILL.md` (MDMA + 2C-B) and
  `skills/combos/hippy-flip/SKILL.md` (MDMA + psilocybin) as dedicated
  overlay files under their own path referencing the base skills, never
  edits of them: layered-onset sequencing, blend dominance rules, the
  distinctive mixture profile vs either substance alone, per-level
  dimension tables, and Safety Override furniture.
- **Tolerance / repeat-exposure overlay line (`skills/tolerance/`)** —
  a documented policy in `skills/tolerance/README.md` plus named
  phenomenology-only repeat-exposure profiles for lsd, psilocybin, and
  ketamine under `skills/tolerance/<substance>/` — what repeated exposure
  does to the surface, deliberately excluding any schedule, regimen, or
  recovery-arithmetic language.
- **Afterglow skill (`skills/afterglow/SKILL.md` +
  `skills/afterglow/consistency-matrix.md`)** — a 24-72h post-trip residue
  overlay covering what the surface feels like the day after for every
  substance, with a consistency matrix tying each afterglow paragraph back
  to the base skill's arc so nothing contradicts the substance's own
  descent section.
### Changed
- **README + AGENTS.md document the milestone-3 content surface** — README
  gains the 11th substance row (2C-B) in the substance table, the extended
  router slang list, the skills tree including the combos/tolerance/
  afterglow overlay lines, the install section now naming
  `bin/install_skills.py`, and the OG share-cards docs; AGENTS.md documents
  `make skills-check` and the content safety lint alongside the existing
  rule set (11 substance table rows, 18 validated skill files).
### Changed
- **Six new SITE section flags declared** —
  `site.substance_pages`, `site.arc_timeline`, `site.diff_view`,
  `site.quiz_game`, `site.journal_dashboards`, and `site.eval_grids` are
  now declared in `feature_flags.json` (owner `site`, roll-out 100,
  expiry `2027-06-30`) and routed through build's `__FLAGS__` payload.
  The gated sections themselves land in later milestone-2 features;
  these declarations make the render-when-on / compile-out-when-off
  gate exist from the moment each section is added. Verified by
  `tests/unit/test_section_flag_lifecycle.py`.
- **Same-prompt dry-run writes to a temp dir by default** —
  `experiments/same-prompt/run-ten-ways.py --dry-run` with no `--output`
  now resolves the compiled markdown to a fresh temp directory (path
  printed as `Output:`), so the tracked read-only data directory
  `experiments/same-prompt/output/` is never touched by a dry run. An
  explicit `--output` is honored as-is in dry and live runs.
### Removed
- **Stale planning docs** — `docs/v1.2-implementation-plan.md`,
  `docs/v1.2-improvement-spec.md`, `docs/track-a-ayahuasca.md` (superseded
  Track-A research plan; the ayahuasca dossier lives in
  `research/ayahuasca/`), and the `docs/superpowers/` slot-machine-wheel plan
  + design spec (the experiment wheel is live; its docs are
  `site/wheel/` and the `site.experiment_wheel` feature flag). Zero
  references to the removed files remain in README, docs, code, or CI.
### Added
- **`watch.py --serve-only`** — serve-and-watch mode that never deploys: the
  flag gates the watch loop into build-only mode, with no code path to
  `deploy()` or its `wrangler` subprocess, plus a `--help` usage listing
  (`python3 watch.py --help`). Default (no-flag) behavior is unchanged.
- **Same-prompt offline dry-run integration test** —
  `tests/integration/test_same_prompt_dry_run.py` invokes
  `experiments/same-prompt/run-ten-ways.py --dry-run` as a subprocess and
  asserts exit 0, `Dry-run: True`, 10/10 substances succeeding, and the
  `[DRY-RUN STUB]` marker in the compiled markdown (written to a temp
  directory, so `experiments/same-prompt/output/` stays untouched). The
  `experiments/same-prompt` omission from the `[tool.coverage.run]` source
  list is now annotated in-place in `pyproject.toml` with the reason
  (subprocess coverage is invisible to the 75% floor).

### Changed
- **Structured logging migration** — `build.py` and `watch.py` route all
  high-signal output through `altered_states.log_utils.log_event()` (JSON,
  redacted, on stderr) per the no-secrets-in-logs rule: build stage progress
  and the build summary (`build.stage`, `build.summary`), WARN-level findings
  (`build.parse_failed`, `watch.build_failed`, `watch.skipped`), the deploy
  lifecycle (`watch.deploy_start`, `watch.deploy_failed`,
  `watch.deploy_skipped`, `watch.deploy_complete`), and serve lifecycle
  (`watch.serving` start/stop, `watch.build_summary`). Zero bare `print()`
  calls remain in either file; each file's migration note at the top states
  the surviving count.
- **Docs reorganization** — the 9 eval-report files that lived under `tests/` plus the
  protocol cards (`eval-guide.md`, `quick-test-card.md`,
  `cross-model-test-protocol.md`, `safety-override-protocol.md`) moved to
  `docs/evals/`, the site's data home for human-scored evaluations; every live
  reference (README, `docs/research-pipeline.md`, `tests/prompts.json`,
  `bin/run_eval.py`, `tests/responses/README.md`) points at the new paths and
  no `.md` files remain at the top of `tests/`. The 1-line,
  date-stamp-only `site/DEPLOY.md` artifact is deleted (real deploy behavior
  is documented in `runbooks/deploy-failure.md`); the dead NotebookLM shell
  duplicate in `bin/` is deleted (`bin/nlm.py` and its tests untouched); the README
  layout tree now documents `site/wheel/` (hand-written page + `projects.json`,
  not touched by build.py, gated by `site.experiment_wheel`) and gives
  `output/` a home; the three orphan files in `output/` carry a provenance
  header naming `bin/run_eval.py` as their producer.
- `.env.example` is complete: it now declares every env var the code reads
  (derived from a repo-wide `os.environ`/`getenv` grep, minus the documented
  non-provider exclusions), adds the previously missing
  `MUREKA_API_KEY` (music experiments), `ANTHROPIC_API_KEY`,
  `SENTRY_TRACES_SAMPLE_RATE`, `GIT_SHA`, `ALTERED_STATES_TEMPORAL_PATH`,
  `LLM_JSON_MODE`, and `TEMPORAL_LAB_MODEL`, and documents the repo-root
  `.env` as the project-wide loading convention with DeepSeek as the primary
  provider and OpenRouter/OpenAI labelled legacy fallback. Placeholder
  values only.
### Fixed
- `feature_flags.json` `_comment` now names the real invocation
  (`python3 -m altered_states.feature_flags check`) instead of the removed
  `bin/feature_flags.py`.
- `AGENTS.md` rule 5 no longer names a phantom root `requirements.txt`; it
  points at the real dev/test pairs and per-dir files under `bin/` and
  `experiments/`.
- `docs/TODO.md` item #5 (slash skill vs embed) closed: README documents the
  slash skill as the primary model with `GEMINI.md` embeds for Gemini CLI.


### Added
- **`altered_states/` shared package** — structured JSON logging with `trace_id` correlation and secret redaction, a Prometheus textfile metrics registry, optional Sentry error tracking, and file-backed feature flags with deterministic rollout bucketing
- **`feature_flags.json`** — four section flags (`site.music_section`, `site.chat_personas`, `site.experiments_gallery`, `site.experiment_wheel`), gated at build time so a disabled section's payload never reaches the client. `python -m altered_states.feature_flags check` fails on an expired or unreferenced flag
- **Test suites** — `tests/unit/` and `tests/integration/`, offline, with an enforced coverage floor. `make test`, `make coverage`
- **CI** — `.github/workflows/ci.yml` (static analysis, test matrix on 3.10 and 3.12, security scanners, docs and site build), `codeql.yml`, `release.yml`, `alerts.yml`, `labels.yml`, `pr-review.yml`
- **`bin/review_pr.py`** — deterministic pull-request review: missing tests, hand-edited generated files, dependency changes without a lockfile refresh, undeclared flags, credential-shaped strings, and deletions of irreplaceable journal data
- **`bin/check_alerts.py` + `alerts/alerts.yaml`** — alert thresholds as code, with a required runbook per alert, consecutive-fire state, and a critical alert that files a triage issue
- **`bin/release_notes.py`** — release notes generated from conventional commits on tag push
- **`bin/sync_labels.py` + `.github/labels.yml`** — declarative label taxonomy, reconciled on every change
- **`bin/check_agents_md.py`, `AGENTS.md`, `runbooks/`, `docs/observability.md`** — instructions and incident procedures that are validated against the repository
- **`.devcontainer/`, `.env.example`** — reproducible environment and a documented variable surface
- **Hash-pinned lockfiles** for every requirements file, plus a per-app requirements file for the music experiment
- **`requirements-test.txt` / `requirements-test.lock`** — the test-only toolchain, locked separately from `requirements-dev` because `pre-commit` and current `coverage` need 3.11+, so the 3.10 job in the test matrix has a resolvable set

### Changed
- **`site/index.html` tracking** — the built page stays tracked in git deliberately (Cloudflare Pages deploys need a committed artifact); the `.gitignore` comment now documents that decision instead of claiming it is ignored, `build.py` notes the committed artifact is intentional, and a fresh ~255KB build replaced the stale 4MB committed copy. The `.gitignore` entry no longer has any practical effect (git does not ignore tracked files), so the comment is documentation, not behavior
- **`altered_states/registry.py`** — the counter/gauge/histogram registry moved out of `metrics.py` so logging can increment a counter without importing the module that writes textfiles and emits log lines. The dependency now runs one way only (`registry` ← `log_utils` ← `metrics`); CodeQL flagged the mutual import as a cycle. `metrics` re-exports `Registry` and `REGISTRY`, so existing imports are unchanged
- **`build.py`** — split into `count_cycles`, `enabled_section_flags`, `render_page`, `collect_site_data`, and `record_content_metrics`; emits structured logs, build metrics, and content gauges the alert policy reads
- **`watch.py`** — subprocess use centralised in one helper that resolves executables, reports a missing `wrangler` clearly, and handles timeouts without swallowing them
- **`bin/run_eval.py`** — retry with exponential backoff on provider errors, per-call metrics, and error events instead of a bare traceback
- **`experiments/temporal-lab/scripts/logger.py`** — ledger records carry `trace_id` and are redacted; cost summaries read the ledger through one helper
- **`Makefile`** — `verify`, `test`, `coverage`, `security`, `deps`, `flags`, `docs`, `alerts`, `labels`, `lock` targets
- **`bin/nlm.py`** — refuses to open a URL that is not http/https

### Fixed
- **README drift** — the skills version table now matches each `skills/*/SKILL.md` front matter (`version: "1.5"`, 11 rows including the router, no stale `v1.4` claims), the `tests/` section of the Project Structure tree lists the real test tree instead of eval-report markdown files that are relocating to `docs/evals/`, and active docs now reference the eval reports and protocol cards at their `docs/evals/` home
- **Secret redaction** no longer redacts `tokens_in` / `tokens_out` telemetry, only fields whose name implies a credential
- **Metrics snapshots** name series consistently between the JSON log payload and the Prometheus textfile, so a value is traceable across both

---

## [1.5] — 2026-04-19

### Added
- **Experiments directory** — `experiments/` housing creative extensions of the skill suite
- **Temporal Lab** — `experiments/temporal-lab/` autonomous persistent character system. 10 substances run as living entities with JSON state, per-substance cadence, journaling, cost tracking, and **real LLM invocation** via OpenRouter (PURE mode — full SKILL.md sent every cycle, no vocab pools). Includes init CLI, cron dispatcher, dashboard, insight extractor, dry-run mode, retry/backoff, and cost ledger
- **Suno prompts** — `experiments/suno-prompts/` 10 substance-specific Custom Mode prompts with style tags, metatags, full lyrics, and anti-pattern guardrails
- **Visual fingerprints** — `experiments/visual-fingerprints/` 10 live p5.js portraits + index.html grid view
- **Dialogue #01** — `experiments/dialogues/01-salvia-vs-mdma-what-is-real.md` — Salvia vs MDMA on "What Is Real?"
- **Ketamine skill and dossier** — `skills/ketamine/SKILL.md` + `research/ketamine/`. The Dissociative: fragmented, void-oriented, the only non-serotonergic substance. Four intensity levels (sub-dissociative / dissociative / deep / k-hole). Grounding protocol for challenging experiences (re-anchor to body, opposite of psychedelic surrender)
- **Salvia divinorum skill and dossier** — `skills/salvia/SKILL.md` + `research/salvia/`. The Doorway: dimensional shifting, reality dissolution, KOR agonism, fastest onset (30-60 sec) and shortest duration (5-15 min). Three intensity levels (threshold / full / ego-dissolution)
- **Ibogaine skill and dossier** — `skills/ibogaine/SKILL.md` + `research/ibogaine/`. The Ancestor: oneirogenic waking dream, death-rebirth, longest arc (12-24 hours), the most physically demanding. Three intensity levels (partial / full / ceremonial)
- **Router updated** — 10 substance routes with new slang, character nicknames, and intensity parsing for ketamine, salvia, and ibogaine
- **Eval reports** — Section 1 eval (50/50, all 10 substances onset pass), max intensity face-off eval (10 substances, all A- or above), ketamine/psilocybin/LSD onset evals in `output/`
- **IDEAS.md** — `experiments/IDEAS.md` running inventory of experiment backlog with prioritization notes

### Changed
- **README** — 10-substance table, expanded comparison table, new quick-start entries, project structure updated with experiments section, source counts updated (63 sources, 11 skills)
- **Router** — expanded blend framework for 10 substances

### Fixed
- **Skill version frontmatter** — bumped `version:` in all 10 substance `SKILL.md` files from `1.4` to `1.5` to match this release (the router was already at 1.5). All 11 skills now report a consistent version.

---

## [1.4] — 2026-04-17

### Added
- **Full research audit** — reviewed all substance dossiers for completeness and source coverage
- **Ayahuasca research expansion** — added 3 studies (Sanches 2016, Hamill 2019, Bouso 2012) to NLM notebook; local sources.md expanded from 4 to 8 annotated sources; dossier updated to v1.1 with new sections (transcendental circle, neuroimaging evidence, synesthesia, long-term personality effects, safety profile)

### Changed
- README source counts bumped from 51 to 55 total sources

---

## [1.3] — 2026-04-13

### Added
- **5-MeO-DMT skill and dossier** — `skills/5-meo-dmt/SKILL.md` + `research/5-meo-dmt/dossier.md`. The Dissolver: formless mysticism, total ego dissolution, white light/source/void, 2-20 min, no entities.
- **Mescaline skill and dossier** — `skills/mescaline/SKILL.md` + `research/mescaline/dossier.md`. The Elder: ornamental organic geometry, animistic mysticism, 10-14 hour duration, nausea gatekeeper.
- **Router updated** — 7 substance routes with new slang, intensity parsing, and character nicknames (5-MeO-DMT = The Dissolver, Mescaline = The Elder)
- **Router blend framework expanded** — 5-MeO-DMT dominates N,N-DMT in blends; mescaline always dominant (like ayahuasca)
- **README updated** — 7-substance table, comparison table expanded, new quick-start entries, source counts updated (51 sources, 8 skills)
- **Eval guide updated** — new substance baselines for all 5 cross-substance prompts, 4 new bleed-test prompts (DMT vs 5-MeO-DMT, Mescaline vs LSD), updated checklists
- **NLM synthesis outputs** — `research/5-meo-dmt/nlm/` (4 files) and `research/mescaline/nlm/` (4 files) from NotebookLM research phase
- **Helper script** — `bin/nlm.py` for driving NotebookLM MCP server

---

## [1.2] — 2026-04-05

### Added
- **Ayahuasca as standalone skill** — split from DMT into its own `skills/ayahuasca/SKILL.md` with dedicated research dossier and sources
- **Descent & Exit sections** for psilocybin, LSD, MDMA, and ayahuasca — substance-specific return-to-baseline behavior
- **Coherence dial structural rules** — replaced vague percentages with concrete per-response rules (e.g., "at least one paragraph changes direction mid-thought")
- **Set & Setting response matrices** — per-substance modulation for playful, distressed, analytical, grieving, and confrontational user tones
- **Router v1.1** — onset reminder injection, set/setting passthrough, explicit blend handling for candy flip and hippy flip
- **YAML frontmatter** on all skills (previously blockquote headers on LSD, MDMA, DMT)
- **Evaluation framework** (`tests/eval-guide.md`) — cross-substance baselines, inter-substance bleed tests, dimension checkpoints, anti-pattern flags, blind test protocol
- **Router research doc** (`research/router/classification-rationale.md`) — phenomenological basis for routing heuristics
- **8 evaluation reports** covering baselines, bleed, blind test, router, dose arcs, set/setting, intensity, edge cases, and extended conversations
- **Quick test card** (`docs/evals/quick-test-card.md`) and **cross-model test protocol** (`docs/evals/cross-model-test-protocol.md`)

### Changed
- **LSD skill** — added sustained plateau mechanics, "trapped" safety valve, LSD vs psilocybin behavioral guide
- **MDMA skill** — reinforced non-psychedelic boundary, added comedown modeling, explicit "no stage directions ever" rule
- **DMT skill** — removed ayahuasca content (now standalone), focused purely on smoked/vaporized route
- **README** — added installation instructions for Claude Code, OpenCode, Gemini CLI, and manual use

### Removed
- Ayahuasca content from DMT skill and dossier (migrated to dedicated files)

---

## [1.1] — 2026-04-04

### Added
- **Onset rules** — exchange 1-3 onset behavior for all substances (body-first, confused, character hasn't arrived)
- **LSD vs psilocybin pharmacological grounding** — Holze 2022 head-to-head data, D2 dopaminergic distinction
- **MDMA pharmacological distinction** — Nichols entactogen classification, SERT-mediated mechanism vs 5-HT2A agonism
- **MDMA coherence enforcement** — explicit rules preventing psychedelic bleed into MDMA mode

### Changed
- Onset pacing tightened across all skills — prohibited guru/oracle/seer behavior from first exchange
- Psilocybin "teacher" quality now explicitly emerges through the arc, not from exchange 1
- DMT onset restructured — instant blast-off with no gradual build

---

## [1.0] — 2026-04-04

### Added
- **Five substance skills**: psilocybin, LSD, MDMA, DMT/ayahuasca (combined at this version)
- **Router skill** — natural language routing with substance detection, intensity parsing, blend handling
- **Research dossiers** for all substances — annotated source lists, phenomenological dimensions, dose-response data
- **41 peer-reviewed sources** annotated across 5 substances
- **7 phenomenological dimensions** mapped per substance (perceptual, temporal, cognitive, emotional, self/ego, relational/mystical, somatic)
- **Three intensity levels** per substance (low/medium/high, plus sub-breakthrough/breakthrough for DMT)
- **README** with quick start, substance comparison table, project structure

---

[1.5]: https://github.com/behole/altered-states/compare/v1.4...v1.5
[1.4]: https://github.com/behole/altered-states/compare/v1.3...v1.4
[1.3]: https://github.com/behole/altered-states/compare/v1.2...v1.3
[1.2]: https://github.com/behole/altered-states/compare/v1.1...v1.2
[1.1]: https://github.com/behole/altered-states/compare/v1.0...v1.1
[1.0]: https://github.com/behole/altered-states/releases/tag/v1.0

# Dry-run fixture journals (committed build fixtures)

These eleven JSON journals are **committed offline fixtures**, not live data (ten
originals plus the deterministic 2C-B fixture added when the 11th substance's
persona landed in `build.py` — the build must have a journal fixture for every
persona id):

- Shape: exactly the schema the temporal lab writes (`scripts/temporal_init.py`
  `run_cycle` / `initialize_character`): a cycle-0 initial entry without an
  `experience` block, then one entry per cycle with
  `experience.intensity` / `experience.novelty`.
- Content: authored deterministic phenomenology curves (values vary per cycle),
  grounded in each character's sheet from `scripts/characters.py` (emotional
  range, expression style). No model output was copied, and no entry describes
  dosing.
- Purpose: `build.py`'s default dashboard source is this directory, so
  `make build` succeeds and the journal-persona cards + arc dashboards render
  meaningfully and identically on every machine (scrutiny site-experience
  run 1, deterministic-build decision) without needing `/tmp` scaffolds.

The REAL runtime tree (`experiments/temporal-lab/runtime/journals/`) is
untouched append-only data; the default build only reads it as a fallback when
this fixtures directory is missing. Builds can still be pointed at any other
temporal-lab root with `ALTERED_STATES_TEMPORAL_PATH` (a root containing
`journals/` wins; a value that is itself the journals dir is used verbatim).

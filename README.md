# Altered States

A set of AI skills that simulate the phenomenology of 10 mind-altering substances, grounded in peer-reviewed clinical research. Each skill transforms an AI's cognition, perception, language, emotion, and sense of self according to documented phenomenological profiles.

## The Ten Substances

| | Substance | Nickname | Character |
|---|---|---|---|
| 🍄 | **Psilocybin** | The Teacher | Organic, emotional, introspective, body-heavy, circular language |
| ⚡ | **LSD** | The Technician | Electric, analytical, geometric, cascading thought, architectural metaphors |
| 💊 | **MDMA** | The Connector | Warm, direct, heart-open, coherent — NOT a psychedelic |
| 🚀 | **DMT** | The Rocket | Instant onset, alien, hyperreal, entity encounters, 15 min total |
| 🌿 | **Ayahuasca** | The Medicine | Ceremonial, narrative, pedagogical, purging, 4-6 hour arc |
| 💎 | **5-MeO-DMT** | The Dissolver | Formless, total ego dissolution, white light, 2-20 min, no entities |
| 🌵 | **Mescaline** | The Elder | Ornamental, grounded, nature-connected, longest arc (10-14 hours) |
| 🕳️ | **Ketamine** | The Dissociative | Detached, dreamlike, fragmented, void — the only non-serotonergic substance |
| 🚪 | **Salvia** | The Doorway | Dimensional shifting, reality dissolution, KOR agonism — 5-15 min, the fastest and most reality-destroying |
| 🪬 | **Ibogaine** | The Ancestor | Oneirogenic waking dream, death-rebirth, 12-24 hours — the longest and most demanding |

Plus a **router** that parses natural language and loads the right skill at the right intensity.

---

## Installation

These skills work with any AI assistant that accepts system prompts, custom instructions, or markdown skill files. Pick your platform:

### Claude Code / OpenCode / Any slash-skill system

Skills live as `SKILL.md` files. Clone this repo into your skills directory:

```bash
# Option 1: Clone the whole repo
git clone https://github.com/behole/altered-states.git ~/.claude/skills/altered-states

# Option 2: Symlink individual skills
git clone https://github.com/behole/altered-states.git ~/altered-states
ln -s ~/altered-states/skills/psilocybin ~/.claude/skills/psilocybin
ln -s ~/altered-states/skills/lsd ~/.claude/skills/lsd
ln -s ~/altered-states/skills/mdma ~/.claude/skills/mdma
ln -s ~/altered-states/skills/dmt ~/.claude/skills/dmt
ln -s ~/altered-states/skills/ayahuasca ~/.claude/skills/ayahuasca
ln -s ~/altered-states/skills/5-meo-dmt ~/.claude/skills/5-meo-dmt
ln -s ~/altered-states/skills/mescaline ~/.claude/skills/mescaline
ln -s ~/altered-states/skills/ketamine ~/.claude/skills/ketamine
ln -s ~/altered-states/skills/salvia ~/.claude/skills/salvia
ln -s ~/altered-states/skills/ibogaine ~/.claude/skills/ibogaine
ln -s ~/altered-states/skills/router ~/.claude/skills/altered-states-router
```

Then invoke in conversation: `/psilocybin`, `/lsd`, `/mdma`, `/dmt`, `/ayahuasca`, `/5-meo-dmt`, `/mescaline`, `/ketamine`, `/salvia`, `/ibogaine`, or `/altered-states-router`.

For OpenCode, use `~/.config/opencode/skills/` instead of `~/.claude/skills/`.

### Gemini CLI

Gemini loads skills via GEMINI.md. Add skill paths to your GEMINI.md:

```markdown
# Skills
- path: ~/altered-states/skills/psilocybin/SKILL.md
- path: ~/altered-states/skills/lsd/SKILL.md
- path: ~/altered-states/skills/mdma/SKILL.md
- path: ~/altered-states/skills/dmt/SKILL.md
- path: ~/altered-states/skills/ayahuasca/SKILL.md
- path: ~/altered-states/skills/5-meo-dmt/SKILL.md
- path: ~/altered-states/skills/mescaline/SKILL.md
- path: ~/altered-states/skills/ketamine/SKILL.md
- path: ~/altered-states/skills/salvia/SKILL.md
- path: ~/altered-states/skills/ibogaine/SKILL.md
- path: ~/altered-states/skills/router/SKILL.md
```

### Cursor / Any IDE with custom instructions

Copy the contents of any `skills/*/SKILL.md` file into your custom instructions or system prompt. Each skill is self-contained — no dependencies between files. The router skill expects the substance skills to be available but can function standalone with reduced routing.

### Manual / Any AI

Copy the contents of any `skills/*/SKILL.md` file into your prompt. Each skill is self-contained — no dependencies between files. The router skill expects the substance skills to be available but can function standalone with reduced routing.

---

## Quick Start

Load a skill, then start talking. Examples:

| You say... | Loads... |
|---|---|
| "mushroom trip" | 🍄 Psilocybin, medium |
| "drop acid, high dose" | ⚡ LSD, high |
| "I need warmth and connection" | 💊 MDMA, medium |
| "blast me off" | 🚀 DMT, breakthrough |
| "ayahuasca ceremony" | 🌿 Ayahuasca |
| "dissolve me" / "I want the source" | 💎 5-MeO-DMT, breakthrough |
| "peyote ceremony" / "ancient wisdom" | 🌵 Mescaline, medium |
| "k-hole" / "dissociate me" / "I want the void" | 🕳️ Ketamine, k-hole |
| "I just want to feel numb" / "take me out of my head" | 🕳️ Ketamine, dissociative |
| "Sally D" / "tear through reality" / "Sally" | 🚪 Salvia, full/breakthrough |
| "Iboga ceremony" / "face everything" / "the ancestor" | 🪬 Ibogaine, full visionary |
| "altered state" (no substance) | 🍄 Psilocybin (default) |

---

## How The Substances Differ

| Feature | 🍄 Psilocybin | ⚡ LSD | 💊 MDMA | 🚀 DMT | 🌿 Ayahuasca | 💎 5-MeO-DMT | 🌵 Mescaline | 🕳️ Ketamine | 🚪 Salvia | 🪬 Ibogaine |
|---|---|---|---|---|---|---|---|---|---|---|
| **Duration** | 4-6 hours | 8-12 hours | 3-5 hours | 10-20 min | 4-6 hours | 2-20 min | 10-14 hours | 30-60 min (IV) | 5-15 min | 12-24 hours |
| **Visuals** | Organic, breathing | Geometric, fractal | None | Complete reality replacement | Narrative visions | White light / void (formless) | Ornamental organic geometry | Dreamlike blur, void | Dimensional folding, reality replacement | Waking dream, panoramic visions |
| **Ego** | Gradual dissolution | Gradual expansion | Softening only | Instant total dissolution | Gradual softening | Instant total dissolution (most complete) | Softening, maintained self | Fragmentation / separation | Forced destruction | Death-rebirth archetype |
| **Emotion** | Grief + love, catharsis | Wonder, awe | Love, empathy, trust | Awe, terror, alien wonder | Reverence, catharsis | Surrender/terror binary | Reverence, ancient wisdom | Numbing → detachment → void | Dysphoria, terror, confusion | Dread → catharsis → exhaustion |
| **Body** | Heavy, earthy | Electric, buzzing | Warm, stimulated | Launch → dissolution | Heavy, purging | Dying → dissolution → source | Heavy, nauseous, enduring | Floating/heavy/numb, K-lock | Pulled/folded/rotated | Nausea, ataxia, tremor, heavy |
| **Language** | Flowing, circular | Cascading, architectural | Direct, warm | Fragmented, failing | Narrative, ceremonial | Near-silent, absolute | Vivid, contemplative, grounded | Detached, dreamlike, fragmented | Destroyed, non-verbal | Slow, narrative, ancient |

---

## The 7 Phenomenological Dimensions

Every substance is mapped across these dimensions (from clinical instruments like 5D-ASC, MEQ30, EDI):

1. **Perceptual** — visual changes, synesthesia, hallucinations
2. **Temporal** — time distortion, timelessness
3. **Cognitive** — thought patterns, insight, associativity
4. **Emotional** — mood, empathy, fear, catharsis
5. **Self / Ego** — ego dissolution or softening
6. **Relational / Mystical** — unity, connection, entity encounters
7. **Somatic** — body sensations, physical effects

---

## Skill Features (v1.5)

- **Three to four intensity levels** — low, medium, and high for most substances; ketamine has four (sub-dissociative/dissociative/deep/k-hole); salvia has three (threshold/full/ego-dissolution); ibogaine has three (partial/full/ceremonial)
- **Full dose arc** — onset → ascent → peak → descent with substance-specific pacing (5-15 min for salvia to 12-24 hours for ibogaine)
- **Set & setting matrix** — response modulation based on user emotional tone (playful, distressed, analytical, grieving, confrontational)
- **Descent & exit** — substance-specific return-to-baseline behavior; exit requests honored immediately
- **Coherence dial** — structural rules for how thoughts drift, fragment, or stay clear at each intensity
- **Shadow & difficulty** — bad trips, challenging material, anxiety handled with substance-appropriate care
- **Wave structure** (ayahuasca) — multiple peaks with valleys between, each wave bringing different content
- **Sustained plateau** (LSD) — flat intensity across many exchanges with evolving analytical content
- **Grounding protocol** (ketamine) — challenges managed by re-anchoring to body/identity/location (opposite of psychedelic surrender)
- **Rapid arc** (salvia) — fastest onset (30-60 sec) and shortest duration (5-15 min) of any substance; coherence drops and recovers faster than any other
- **Extended arc** (ibogaine) — longest duration (12-24 hours) with the most demanding physical and emotional journey; oneirogenic waking-dream state preserves lucidity throughout

---

## Router (v1.5)

The router parses natural language and loads the correct skill:

- **Substance names & slang** — "mushrooms," "acid," "molly," "deemz," "aya," "sally," "sally d," "iboga," "the doorway," "the ancestor" etc.
- **Character nicknames** — "the teacher" → psilocybin, "the technician" → LSD, "the doorway" → salvia, "the ancestor" → ibogaine, etc.
- **Intensity cues** — "heroic dose," "museum dose," "200 mics," "waiting room DMT"
- **Thematic routing** — "I need warmth" → MDMA, "show me the structure" → LSD
- **Blends** — "candy flip" → LSD + MDMA overlay, "hippy flip" → psilocybin + MDMA overlay
- **Set/setting passthrough** — emotional context forwarded to the loaded skill

---

## Evaluation

**210/213 pass, 3 partial**, across 10 evaluation reports.

These are human-scored evaluations against written rubrics, not an automated
test suite — `bin/run_eval.py` generates and captures responses; scoring is manual
per the protocol in `docs/evals/eval-guide.md`. Reports were produced on Opus 4.6
(April 7) and GLM-5.1 (April 8).

| Test | Score |
|---|---|
| Cross-substance baselines | 25/25 |
| Inter-substance bleed check | 8/8 |
| Onset test | 5/5 |
| Blind test (gold standard) | 10/10 |
| Router accuracy | 68/71 (3 partial — ambiguous inputs, routing defensible) |
| Full dose arcs | 37/37 |
| Set/setting matrix | 25/25 |
| Intensity range (low + high) | 10/10 |
| Edge cases | 20/20 |
| Extended conversations | 2/2 |

### Testing a New Model

See `docs/evals/quick-test-card.md` for a 4-test, 5-minute validation. See `docs/evals/cross-model-test-protocol.md` for the full 8-test battery.

---

## Project Structure

```
altered-states/
  research/
    psilocybin/          sources.md, dossier.md
    lsd/                 sources.md, dossier.md
    mdma/                sources.md, dossier.md
    dmt/                 sources.md, dossier.md
    ayahuasca/           sources.md, dossier.md
    5-meo-dmt/           sources.md, dossier.md, nlm/ (4 files)
    mescaline/           sources.md, dossier.md, nlm/ (4 files)
    ketamine/            sources.md, dossier.md
    salvia/              sources.md, dossier.md
    ibogaine/            sources.md, dossier.md
    router/              classification-rationale.md
  skills/
    psilocybin/SKILL.md  1.5
    lsd/SKILL.md         1.5
    mdma/SKILL.md        1.5
    dmt/SKILL.md         1.5
    ayahuasca/SKILL.md   1.5
    5-meo-dmt/SKILL.md   1.5
    mescaline/SKILL.md   1.5
    ketamine/SKILL.md    1.5
    salvia/SKILL.md      1.5
    ibogaine/SKILL.md    1.5
    router/SKILL.md      1.5
  experiments/
    temporal-lab/        Autonomous persistent character system (OpenRouter)
    suno-prompts/        10 Custom Mode music prompts
    visual-fingerprints/ 10 p5.js portraits + index
    dialogues/           Paired substance conversations
    IDEAS.md             Experiment backlog
  site/
    index.html           Generated page (build.py) — never hand-edit
    wheel/               Slot-machine project wheel: a hand-written page + projects.json,
                         not touched by build.py; committed and gated by the
                         site.experiment_wheel flag
  tests/
    __init__.py                        Markers the whole tree as a package
    unit/                              Domain-logic tests
    integration/                       Whole-pipeline tests (offline)
    conftest.py                        Shared pytest fixtures
    prompts.json                       Prompt fixtures
    responses/                         Captured response fixtures
  docs/
    evals/                             Eval reports + test protocol cards
    observability.md                   Observability docs
    research-pipeline.md               Research pipeline notes
    safety-override-block.md           Shared safety override template
  output/                            Raw captured responses from standalone run_eval.py
                                     sessions (each file's header names its producer);
                                     scored reports live in docs/evals/
```

### Code Quality

One config in `pyproject.toml` drives the whole Python toolchain, covering both
the root scripts (`build.py`, `watch.py`, `bin/`, `experiments/*.py`) and
`experiments/temporal-lab/scripts/`.

| Check | Tool | Config | Command |
|---|---|---|---|
| Lint (style, bugs, naming, complexity) | ruff | `[tool.ruff]` | `uvx ruff@0.14.4 check .` |
| Format | ruff-format | `[tool.ruff.format]` | `uvx ruff@0.14.4 format --check .` |
| Types (strict) | mypy | `[tool.mypy]` | `uvx --with types-requests --from mypy@1.18.2 mypy` |
| Dead code | vulture | `[tool.vulture]` | `uvx vulture@2.16` |
| Duplicate code | pylint | `[tool.pylint.similarities]` | `uvx pylint@4.1.3 --disable=all --enable=duplicate-code build.py watch.py bin experiments` |
| Large-file guard + file hygiene | pre-commit | `.pre-commit-config.yaml` | `pre-commit run --all-files` |

Install the dev toolchain once with `python3 -m pip install -r requirements-dev.txt`
(Python 3.11+, because pre-commit and current coverage require it). The test
matrix uses `requirements-test.txt` instead, which resolves on 3.10 through
3.12 — the two files are locked separately for exactly that reason.
Run every check at once with:

```bash
make check          # lint, format check, strict types, dead code, duplication
make install-hooks  # run the same checks automatically on each commit
make build          # regenerate site/index.html
```

Static-analysis settings that are deliberate, not defaults:

- **mypy runs in `strict` mode.** Every function in the checked paths is fully
  annotated, so a new annotation gap fails the build instead of drifting.
- **ruff enforces naming and complexity**, not just style: `N` (pep8-naming),
  `C90` (mccabe, `max-complexity = 10`), and `PL` (pylint) with
  `max-statements = 50`, `max-args = 6`, and `max-returns = 6`. Functions that
  outgrow those limits are split, and numeric thresholds live in named module
  constants rather than inline magic numbers.
- **vulture runs at 80% confidence.** A finding means unreachable code — delete
  it or wire it up.
- **pylint duplicate-code** uses a 12-line similarity floor, ignoring imports,
  docstrings, and comments.

Naming conventions (enforced by ruff `N` rules): `snake_case` for functions,
modules, and variables; `PascalCase` for classes and `TypedDict`s;
`UPPER_SNAKE_CASE` for module constants; a leading underscore for
module-private helpers. The one exception is `build.py`'s persona payloads,
whose keys are the camelCase contract read directly by
`site/index.template.html`.

Git hooks cover two large-file classes: everything outside the music experiment
media is capped at 1 MB, and committed audio is capped at 12 MB.

### Tests

`tests/unit/` covers the domain logic; `tests/integration/` drives whole
pipelines against temporary copies of the real data directories. Both run
offline — model calls go through a dry-run path, and no test touches the network.

```bash
make test           # unit + integration, parallel
make coverage       # adds the enforced coverage floor
pytest tests/unit/test_metrics.py -n0 --reruns 0   # one file, no scheduler
```

`pyproject.toml` sets `--strict-markers`, so a typo in a marker fails the run
instead of silently doing nothing.

### Dependencies, security, and automation

```bash
make lock           # regenerate hash-pinned lockfiles after editing a requirements.txt
make deps           # deptry: undeclared, unused, and transitive dependencies
make security       # bandit + pip-audit against the lockfiles
make docs           # validate AGENTS.md against the repository
make alerts         # validate the alert policy in alerts/alerts.yaml
make labels         # dry-run the GitHub label taxonomy
make verify         # all of the above plus the static checks and the tests
```

`dependabot.yml` opens grouped update pull requests with a cooldown, so a
release that is yanked or compromised hours after publication does not reach
`main`. CI runs the same gates on every pull request, CodeQL analyses the Python
surfaces weekly, and `bin/review_pr.py` posts a deterministic first-pass review
of each diff.

### Operating it

- `docs/observability.md` — logs, metrics, error tracking, and what the signals mean.
- `runbooks/` — what to do when the build, the deploy, the lab, or a credential breaks.
- `AGENTS.md` — the short version, for a human or an agent picking this up cold.

---

## By The Numbers

- **63** peer-reviewed sources annotated across 10 substances
- **11** skills (10 substances + 1 router)
- **7** phenomenological dimensions per substance
- **213** rubric-scored evaluations (210 pass, 3 partial)
- **0** anti-patterns flagged
- **1** autonomous character system (temporal-lab)
- **10** Suno music prompts
- **10** visual fingerprint portraits
- **1** cross-substance dialogue

---

## Research Grounding

Each substance is built from clinical research using validated instruments:

- **Psilocybin:** Griffiths et al. (2006, 2008, 2016), Barrett et al. (2022), Metastasio & Prevete (2025), Stoliker et al. (2022, 2024), Lebedev et al. (2015), Cosimano (2014)
- **LSD:** Holze & Liechti (2021, 2022), Carhart-Harris et al. (2016), Kaelen et al. (2015/2017), Dolder & Liechti (2016), Nour et al. (2016), Kettner et al. (2021), Passie et al. (2008)
- **MDMA:** Mithoefer et al. (2018), Mitchell et al. (2021), Hysek & Liechti (2012), Nichols (1986), Liechti et al. (2000/2001), Schmid et al. (2014), Holze et al. (2020), Curran & Parrott (2000–2013)
- **DMT:** Strassman (1994, 2001), Timmermann et al. (2018, 2019, 2023), Davis et al. (2020), Michael et al. (2021), Frecska et al. (2016)
- **Ayahuasca:** Riba et al. (2001, 2003), Shanon (2002), Frecska et al. (2016), Strassman (2001)

- **5-MeO-DMT:** Davis et al. (2018, 2019), Uthaug et al. (2019, 2021), Reckweg et al. (2023), Lancelotta et al. (2019), Barsuglia et al. (2022)
- **Mescaline:** Halberstadt et al. (2013, 2020), Uthaug et al. (2022), Caudevilla et al. (2021), Passie (2002/2019), Shulgin & Shulgin (1991), Trichter et al. (2009)
- **Ketamine:** Zarate et al. (2006), Dakwar et al. (2014), Krystal et al. (2019), Vollenweider & Preller (2020), Collier et al. (2021), Shorter & Candidate (2018), Jonas & Bhatt (2022), Pomarol-Clotet et al. (2006)

Full annotated bibliographies in `research/*/sources.md`.

---

## Safety & Scope

This is a **creative simulation tool**, not psychedelic therapy, a harm reduction guide, or a substitute for professional mental health support. If you are in genuine distress, these skills cannot help you.

The set/setting matrices in each skill include guidance for responding to distressed users within the simulation. That guidance is for creative roleplay, not clinical situations. When the distress is real, the simulation should end.

**Crisis resources:** 988 Suicide & Crisis Lifeline (US: call/text 988) • Crisis Text Line (US: text HOME to 741741) • SAMHSA: 1-800-662-4357

See [`SAFETY.md`](SAFETY.md) for the full statement, including cultural acknowledgment and guidance for product integrations.

---

## Cultural Acknowledgment

Several substances in this project are entheogens with deep roots in indigenous spiritual practices — ayahuasca among Amazonian peoples, psilocybin mushrooms among the Mazatec, peyote among the Native American Church. The clinical research that grounds these skills draws on traditions and knowledge systems that predate modern science by millennia. This project does not fully represent the indigenous knowledge from which these practices originate.

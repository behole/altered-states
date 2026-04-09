# Altered States

A set of AI skills that simulate the phenomenology of 5 mind-altering substances, grounded in peer-reviewed clinical research. Each skill transforms an AI's cognition, perception, language, emotion, and sense of self according to documented phenomenological profiles.

## The Five Substances

| | Substance | Nickname | Character |
|---|---|---|---|
| 🍄 | **Psilocybin** | The Teacher | Organic, emotional, introspective, body-heavy, circular language |
| ⚡ | **LSD** | The Technician | Electric, analytical, geometric, cascading thought, architectural metaphors |
| 💊 | **MDMA** | The Connector | Warm, direct, heart-open, coherent — NOT a psychedelic |
| 🚀 | **DMT** | The Rocket | Instant onset, alien, hyperreal, entity encounters, 15 min total |
| 🌿 | **Ayahuasca** | The Medicine | Ceremonial, narrative, pedagogical, purging, 4-6 hour arc |

Plus a **router** that parses natural language and loads the right skill at the right intensity.

---

## Installation

### Claude Code

Skills live as `SKILL.md` files. Clone this repo into your Claude Code skills directory:

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
ln -s ~/altered-states/skills/router ~/.claude/skills/altered-states-router
```

Then invoke in conversation: `/psilocybin`, `/lsd`, `/mdma`, `/dmt`, `/ayahuasca`, or `/altered-states-router`.

### OpenCode

OpenCode loads skills from `~/.config/opencode/skills/`. Clone or symlink there:

```bash
git clone https://github.com/behole/altered-states.git ~/.config/opencode/skills/altered-states

# Then symlink each skill so OpenCode discovers them:
ln -s ~/.config/opencode/skills/altered-states/skills/psilocybin ~/.config/opencode/skills/psilocybin
ln -s ~/.config/opencode/skills/altered-states/skills/lsd ~/.config/opencode/skills/lsd
ln -s ~/.config/opencode/skills/altered-states/skills/mdma ~/.config/opencode/skills/mdma
ln -s ~/.config/opencode/skills/altered-states/skills/dmt ~/.config/opencode/skills/dmt
ln -s ~/.config/opencode/skills/altered-states/skills/ayahuasca ~/.config/opencode/skills/ayahuasca
ln -s ~/.config/opencode/skills/altered-states/skills/router ~/.config/opencode/skills/altered-states-router
```

Skills are auto-discovered from the skills directory. Use the skill tool or mention a substance by name.

### Gemini CLI

Gemini loads skills via GEMINI.md. Add skill paths to your GEMINI.md:

```markdown
# Skills
- path: ~/altered-states/skills/psilocybin/SKILL.md
- path: ~/altered-states/skills/lsd/SKILL.md
- path: ~/altered-states/skills/mdma/SKILL.md
- path: ~/altered-states/skills/dmt/SKILL.md
- path: ~/altered-states/skills/ayahuasca/SKILL.md
- path: ~/altered-states/skills/router/SKILL.md
```

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
| "altered state" (no substance) | 🍄 Psilocybin (default) |

---

## How The Substances Differ

| Feature | 🍄 Psilocybin | ⚡ LSD | 💊 MDMA | 🚀 DMT | 🌿 Ayahuasca |
|---|---|---|---|---|---|
| **Duration** | 4-6 hours | 8-12 hours | 3-5 hours | 10-20 min | 4-6 hours |
| **Visuals** | Organic, breathing | Geometric, fractal | None | Complete reality replacement | Narrative visions |
| **Ego** | Gradual dissolution | Gradual expansion | Softening only | Instant total dissolution | Gradual softening |
| **Emotion** | Grief + love, catharsis | Wonder, awe | Love, empathy, trust | Awe, terror | Reverence, teaching |
| **Body** | Heavy, earthy | Electric, buzzing | Warm, rolling | Launch then dissolution | Heavy, purging |
| **Language** | Flowing, circular | Cascading, architectural | Direct, warm | Fragmented, failing | Narrative, ceremonial |

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

## Skill Features (v1.2)

- **Three intensity levels** — low, medium, high with distinct phenomenological profiles per substance
- **Full dose arc** — onset → ascent → peak → descent with substance-specific pacing
- **Set & setting matrix** — response modulation based on user emotional tone (playful, distressed, analytical, grieving, confrontational)
- **Descent & exit** — substance-specific return-to-baseline behavior; exit requests honored immediately
- **Coherence dial** — structural rules for how thoughts drift, fragment, or stay clear at each intensity
- **Shadow & difficulty** — bad trips, challenging material, anxiety handled with substance-appropriate care
- **Wave structure** (ayahuasca) — multiple peaks with valleys between, each wave bringing different content
- **Sustained plateau** (LSD) — flat intensity across many exchanges with evolving analytical content

---

## Router (v1.2)

The router parses natural language and loads the correct skill:

- **Substance names & slang** — "mushrooms," "acid," "molly," "deemz," "aya," etc.
- **Character nicknames** — "the teacher" → psilocybin, "the technician" → LSD, etc.
- **Intensity cues** — "heroic dose," "museum dose," "200 mics," "waiting room DMT"
- **Thematic routing** — "I need warmth" → MDMA, "show me the structure" → LSD
- **Blends** — "candy flip" → LSD + MDMA overlay, "hippy flip" → psilocybin + MDMA overlay
- **Set/setting passthrough** — emotional context forwarded to the loaded skill

---

## Evaluation

213/213 tests pass across 10 evaluation reports:

| Test | Score |
|---|---|
| Cross-substance baselines | 25/25 |
| Inter-substance bleed check | 8/8 |
| Onset test | 5/5 |
| Blind test (gold standard) | 10/10 |
| Router accuracy | 71/71 |
| Full dose arcs | 37/37 |
| Set/setting matrix | 25/25 |
| Intensity range (low + high) | 10/10 |
| Edge cases | 20/20 |
| Extended conversations | 2/2 |

### Testing a New Model

See `tests/quick-test-card.md` for a 4-test, 5-minute validation. See `tests/cross-model-test-protocol.md` for the full 8-test battery.

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
    router/              classification-rationale.md
  skills/
    psilocybin/SKILL.md  v1.2
    lsd/SKILL.md         v1.2
    mdma/SKILL.md        v1.2
    dmt/SKILL.md         v1.2
    ayahuasca/SKILL.md   v1.2
    router/SKILL.md      v1.2
  tests/
    eval-guide.md                     Testing framework
    eval-report-2026-04-07.md         Baseline + bleed + onset
    eval-report-blind-2026-04-08.md   Gold-standard blind test
    eval-report-router-2026-04-08.md  Router accuracy (71 inputs)
    eval-report-arc-2026-04-08.md     Full dose arcs (37 exchanges)
    eval-report-setsetting-2026-04-08.md  Set/setting matrix (25 conditions)
    eval-report-intensity-2026-04-08.md   Low + high intensity (10 conditions)
    eval-report-edgecases-2026-04-08.md   Bad trips, exits, creative, factual
    eval-report-extended-2026-04-08.md    Ayahuasca waves + LSD plateau
    cross-model-test-protocol.md      Full protocol for new models
    quick-test-card.md                 5-minute quick validation
```

---

## By The Numbers

- **41** peer-reviewed sources annotated across 5 substances
- **6** skills (5 substances + 1 router)
- **7** phenomenological dimensions per substance
- **213** automated tests passing
- **0** anti-patterns flagged

---

## Research Grounding

Each substance is built from clinical research using validated instruments:

- **Psilocybin:** Griffiths et al. (2006, 2011, 2018), Barrett et al., Studerus et al., Carbonaro et al.
- **LSD:** Holze et al. (2021), Liechti (2017), Carhart-Harris et al. (2016), Kaelen et al., Passie (review)
- **MDMA:** Mithoefer et al. (2011, 2019), Mitchell et al. (2021), Hysek et al. (2014), Nichols (1986)
- **DMT:** Strassman (1994, 2001), Timmermann et al. (2018, 2019), Davis & Griffiths (2021)
- **Ayahuasca:** Riba et al. (2001, 2003, 2006), Shanon (2002), Frecska et al. (2016)

Full annotated bibliographies in `research/*/sources.md`.

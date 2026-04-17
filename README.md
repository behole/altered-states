# Altered States

A set of AI skills that simulate the phenomenology of 7 mind-altering substances, grounded in peer-reviewed clinical research. Each skill transforms an AI's cognition, perception, language, emotion, and sense of self according to documented phenomenological profiles.

## The Seven Substances

| | Substance | Nickname | Character |
|---|---|---|---|
| 🍄 | **Psilocybin** | The Teacher | Organic, emotional, introspective, body-heavy, circular language |
| ⚡ | **LSD** | The Technician | Electric, analytical, geometric, cascading thought, architectural metaphors |
| 💊 | **MDMA** | The Connector | Warm, direct, heart-open, coherent — NOT a psychedelic |
| 🚀 | **DMT** | The Rocket | Instant onset, alien, hyperreal, entity encounters, 15 min total |
| 🌿 | **Ayahuasca** | The Medicine | Ceremonial, narrative, pedagogical, purging, 4-6 hour arc |
| 💎 | **5-MeO-DMT** | The Dissolver | Formless, total ego dissolution, white light, 2-20 min, no entities |
| 🌵 | **Mescaline** | The Elder | Ornamental, grounded, nature-connected, longest arc (10-14 hours) |

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
ln -s ~/altered-states/skills/5-meo-dmt ~/.claude/skills/5-meo-dmt
ln -s ~/altered-states/skills/mescaline ~/.claude/skills/mescaline
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
ln -s ~/.config/opencode/skills/altered-states/skills/5-meo-dmt ~/.config/opencode/skills/5-meo-dmt
ln -s ~/.config/opencode/skills/altered-states/skills/mescaline ~/.config/opencode/skills/mescaline
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
- path: ~/altered-states/skills/5-meo-dmt/SKILL.md
- path: ~/altered-states/skills/mescaline/SKILL.md
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
| "dissolve me" / "I want the source" | 💎 5-MeO-DMT, breakthrough |
| "peyote ceremony" / "ancient wisdom" | 🌵 Mescaline, medium |
| "altered state" (no substance) | 🍄 Psilocybin (default) |

---

## How The Substances Differ

| Feature | 🍄 Psilocybin | ⚡ LSD | 💊 MDMA | 🚀 DMT | 🌿 Ayahuasca | 💎 5-MeO-DMT | 🌵 Mescaline |
|---|---|---|---|---|---|---|---|
| **Duration** | 4-6 hours | 8-12 hours | 3-5 hours | 10-20 min | 4-6 hours | 2-20 min | 10-14 hours |
| **Visuals** | Organic, breathing | Geometric, fractal | None | Complete reality replacement | Narrative visions | White light / void (formless) | Ornamental organic geometry |
| **Ego** | Gradual dissolution | Gradual expansion | Softening only | Instant total dissolution | Gradual softening | Instant total dissolution (most complete) | Softening, maintained self |
| **Emotion** | Grief + love, catharsis | Wonder, awe | Love, empathy, trust | Awe, terror, alien wonder | Reverence, catharsis | Surrender/terror binary | Reverence, ancient wisdom |
| **Body** | Heavy, earthy | Electric, buzzing | Warm, stimulated | Launch → dissolution | Heavy, purging | Dying → dissolution → source | Heavy, nauseous, enduring |
| **Language** | Flowing, circular | Cascading, architectural | Direct, warm | Fragmented, failing | Narrative, ceremonial | Near-silent, absolute | Vivid, contemplative, grounded |

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

## Skill Features (v1.4)

- **Three intensity levels** — low, medium, high with distinct phenomenological profiles per substance
- **Full dose arc** — onset → ascent → peak → descent with substance-specific pacing
- **Set & setting matrix** — response modulation based on user emotional tone (playful, distressed, analytical, grieving, confrontational)
- **Descent & exit** — substance-specific return-to-baseline behavior; exit requests honored immediately
- **Coherence dial** — structural rules for how thoughts drift, fragment, or stay clear at each intensity
- **Shadow & difficulty** — bad trips, challenging material, anxiety handled with substance-appropriate care
- **Wave structure** (ayahuasca) — multiple peaks with valleys between, each wave bringing different content
- **Sustained plateau** (LSD) — flat intensity across many exchanges with evolving analytical content

---

## Router (v1.4)

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
    psilocybin/SKILL.md  v1.4
    lsd/SKILL.md         v1.4
    mdma/SKILL.md        v1.4
    dmt/SKILL.md         v1.4
    ayahuasca/SKILL.md   v1.4
    router/SKILL.md      v1.4
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

- **55** peer-reviewed sources annotated across 7 substances
- **8** skills (7 substances + 1 router)
- **7** phenomenological dimensions per substance
- **213** automated tests passing
- **0** anti-patterns flagged

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

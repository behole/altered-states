# Altered States Skill Project — Summary

## What It Is

A set of Claude skills that simulate the phenomenology of 5 mind-altering substances, grounded in peer-reviewed clinical research. Each skill transforms Claude's cognition, perception, language, emotion, and sense of self according to documented phenomenological profiles.

---

## The Five Substances

| | Substance | Nickname | Character |
|---|---|---|---|
| 🍄 | **Psilocybin** | The Teacher | Organic, emotional, introspective, body-heavy, circular language |
| ⚡ | **LSD** | The Technician | Electric, analytical, geometric, cascading thought, architectural metaphors |
| 💊 | **MDMA** | The Connector | Warm, direct, heart-open, coherent — NOT a psychedelic |
| 🚀 | **DMT** | The Rocket | Instant onset, alien, hyperreal, entity encounters, 15 min total |
| 🌿 | **Ayahuasca** | The Medicine | Ceremonial, narrative, pedagogical, purging, 4-6 hour arc |

**Plus a router** 🔀 that parses natural language and loads the right skill at the right intensity.

---

## What We Built For Each Substance

- **sources.md** — annotated academic papers per substance (psilocybin: 9, LSD: 10, MDMA: 10, DMT: 8, ayahuasca: 4)
- **dossier.md** — full research synthesis across 7 phenomenological dimensions
- **SKILL.md** — the actual prompt that transforms Claude's behavior at low / medium / high intensity
- **Hermes skill** — live, invocable, synced to both machines via git

v1.2 added across all skills: substance-specific descent/exit behavior, coherence dial structural rules (replacing percentage guidelines), set/setting matrix for response modulation, and normalized YAML frontmatter headers.

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

## How The Substances Differ

| Feature | 🍄 Psilocybin | ⚡ LSD | 💊 MDMA | 🚀 DMT | 🌿 Ayahuasca |
|---|---|---|---|---|---|
| **Duration** | 4-6 hours | 8-12 hours | 3-5 hours | 10-20 min | 4-6 hours |
| **Visuals** | Organic, breathing | Geometric, fractal | None/minimal | Complete reality replacement | Narrative visions, serpents, ancestors |
| **Ego** | Gradual dissolution | Gradual expansion | Softening only | Instant total dissolution | Gradual softening to dissolution |
| **Emotion** | Grief + love, catharsis | Wonder, awe, analytical | Love, empathy, trust | Awe, terror, alien wonder | Reverence, catharsis, teaching |
| **Body** | Heavy, earthy, nauseous | Electric, buzzing, jaw | Warm, rolling, tactile | Launch then dissolution | Heavy, nauseous, purging, exhaustion |
| **Language** | Flowing, circular, poetic | Cascading, architectural | Direct, warm, honest | Fragmented, struggling | Narrative, ceremonial, reverent |
| **Shadow** | Emotional overwhelm | Thought loops, trapped | Comedown (delayed) | Alien terror, brief | Emotional confrontation, purging (hours) |
| **Insight** | Emotional truth | Structural revelation | Relational clarity | Cosmic download | Ancestral/pedagogical wisdom |

---

## The Router

Parses user input and routes to the correct skill:

| Say this... | Gets routed to... |
|---|---|
| "mushroom trip" | 🍄 Psilocybin, medium |
| "drop acid, high dose" | ⚡ LSD, high |
| "I need warmth and connection" | 💊 MDMA, medium |
| "blast me off" | 🚀 DMT, breakthrough |
| "ayahuasca ceremony" | 🌿 Ayahuasca, medium |
| "altered state" (no substance) | 🍄 Psilocybin, medium (default) |

---

## v1.1 Design Patches (from test-driving psilocybin)

Applied across all substance skills:

1. **Onset rules** — first 2-3 exchanges are onset, not peak. Body-first, confused, building.
2. **Coherence dial** — ~20% of thoughts should drift/lose the thread at medium intensity.
3. **Anti-guru** — the "teacher" / "technician" / "connector" quality *emerges* through the arc, never starts fully formed.
4. **Stage direction restraint** — `[pause]`, `[breathing]` reserved for peak, not onset (except DMT, which warrants them immediately).
5. **Structure surprise** — if you can outline the response before writing it, it's too structured.

---

## v1.2 Improvements

Built on v1.1 with:

1. **Ayahuasca breakout** — separated from DMT into standalone skill with dedicated research
2. **Descent & Exit** — substance-specific return-to-baseline behavior for each skill
3. **Coherence dial precision** — percentage guidelines replaced with structural rules
4. **Set & Setting matrix** — response modulation based on user emotional tone
5. **Evaluation guide** — standardized testing framework with prompts, checklists, anti-patterns
6. **Router v1.1** — onset injection, set/setting passthrough, blend clarity
7. **Normalized headers** — all skills use YAML frontmatter
8. **Router research** — classification rationale with pharmacological grounding

---

## Project Structure

```
01_Projects/altered-states/
  docs/
    v1.2-improvement-spec.md         # v1.2 spec
    v1.2-implementation-plan.md      # v1.2 plan
  research/
    psilocybin/
      sources.md                     # 9 annotated sources
      dossier.md
    lsd/
      sources.md                     # 10 sources
      dossier.md
    mdma/
      sources.md                     # 10 sources
      dossier.md
    dmt/
      sources.md                     # 8 sources (ayahuasca-specific moved)
      dossier.md
    ayahuasca/
      sources.md                     # 4 sources
      dossier.md
    router/
      classification-rationale.md    # Routing heuristic rationale
  skills/
    psilocybin/SKILL.md              # v1.2
    lsd/SKILL.md                     # v1.2
    mdma/SKILL.md                    # v1.2
    dmt/SKILL.md                     # v1.2
    ayahuasca/SKILL.md               # v1.0
    router/SKILL.md                  # v1.1
  tests/
    eval-guide.md                    # Testing framework
```

---

## By The Numbers

- **39+** peer-reviewed sources annotated (some shared across substance skills)
- **5** substance skills + 1 router = **6** Hermes skills live and invocable
- **5** substances: psilocybin, LSD, MDMA, DMT (smoked), ayahuasca
- **1** evaluation guide for systematic testing
- All synced to `github.com/behole/2026L` and hermes-skills repo

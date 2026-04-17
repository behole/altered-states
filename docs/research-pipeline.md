# Research Pipeline: New Substance Addition

**Version:** 1.0  
**Status:** Draft  
**Owner:** behole  

This document formalizes the workflow for adding a new substance to Altered States. The pipeline transforms peer-reviewed research into a fully-tested phenomelogical simulation skill.

---

## Overview

```
Research Sources → NotebookLM Notebook → Synthesis → Dossier → SKILL.md → Tests
```

**Target deliverables per substance:**
- `research/<substance>/sources.md` — annotated bibliography
- `research/<substance>/dossier.md` — 7-dimension phenomenological profile
- `research/<substance>/nlm/` — raw NotebookLM synthesis artifacts
- `skills/<substance>/SKILL.md` — the simulation skill
- Updated `README.md` comparison table and stats

---

## Phase 0: Prerequisites

### Install & Authenticate

```bash
# Install nlm CLI (one-time)
uv tool install notebooklm-mcp-cli

# Authenticate with NotebookLM (Google OAuth via Chrome cookies)
nlm login --force

# Verify
nlm doctor
```

**Troubleshooting:** If any `nlm` command returns HTTP 400 or "batchexecute" errors, run `nlm login --force` to refresh cookies.

---

## Phase 1: Notebook Setup

### 1. Create Notebook

```bash
nlm notebook create "<Substance> — Altered States Research"
# Returns: Notebook ID (UUID) — SAVE THIS
```

**Naming convention:** Use the exact substance name (capitalized), followed by ` — Altered States Research`.

Examples:
- `"Ketamine — Altered States Research"`
- `"Ibogaine — Altered States Research"`
- `"Salvinorin A — Altered States Research"`

### 2. Create Local Directory Structure

```bash
SUBSTANCE="ketamine"  # lowercase, hyphenated if needed
mkdir -p research/$SUBSTANCE/nlm
mkdir -p skills/$SUBSTANCE
touch research/$SUBSTANCE/sources.md
touch research/$SUBSTANCE/dossier.md
```

---

## Phase 2: Source Ingestion

### Strategy Priority (Highest → Lowest)

| Priority | Source Type | URL Pattern | Notes |
|----------|-------------|-------------|-------|
| 1 | PMC full-text | `https://pmc.ncbi.nlm.nih.gov/articles/PMCxxxxxxx/` | Best: full paper, open access |
| 2 | PubMed | `https://pubmed.ncbi.nlm.nih.gov/PMID/` | Works ~80% of time |
| 3 | ResearchGate PDF | `https://www.researchgate.net/publication/...` | Fallback for paywalled |
| 4 | Academia.edu | `https://www.academia.edu/...` | Fallback for hard-to-access |
| 5 | PeerJ | `https://peerj.com/articles/NNNN/` | Open access, reliable |
| ✗ | DOI | `https://doi.org/10.xxxx/...` | **AVOID** — redirects through paywalls |
| ✗ | Wiley/Elsevier/Springer | Direct journal URLs | **AVOID** — paywall ingestion fails |

### Add Sources

```bash
NB="your-notebook-uuid-here"

# Add each source individually for verification
nlm source add "$NB" --url "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"
```

### Verify & Clean

```bash
# List all sources and check titles for garbage
nlm source list "$NB"

# Delete any with titles containing: reCAPTCHA, ERROR, Checking your browser
nlm source delete "bad-source-id-1" "bad-source-id-2" --confirm
```

**Critical:** Always verify. NotebookLM silently ingests paywall pages and reCAPTCHA errors as "sources." A garbage title means garbage content.

### Document Sources Locally

As you add sources, update `research/<substance>/sources.md`:

```markdown
## Annotated Bibliography

| Citation | URL | Type | Dose-Response Data | Phenomenology | Notes |
|----------|-----|------|-------------------|---------------|-------|
| Smith et al. (2020) | [PMC789...](url) | RCT | ✓ | ✓ | Primary outcome: ... |
```

---

## Phase 3: Synthesis

### Standard Query Template

Use this prompt for each NotebookLM query. It ensures coverage of all 7 phenomenological dimensions:

```
Synthesize the phenomenology of [SUBSTANCE] across all sources in this notebook.

For each of the 7 dimensions, provide:
1. A concise synthesis (2-4 sentences)
2. Key findings with citations
3. Gaps or contradictions in the literature

The 7 dimensions are:
1. Perceptual — visual/auditory changes, synesthesia, hallucinations
2. Temporal — time distortion, timelessness, duration patterns
3. Cognitive — thought patterns, insight, associativity, confusion
4. Emotional — mood shifts, empathy, fear, catharsis, euphoria
5. Self/Ego — dissolution, softening, expansion, depersonalization
6. Relational/Mystical — unity, connection, entity encounters, sacredness
7. Somatic — body sensations, nausea, temperature, tactile changes

Also extract:
- Duration ranges by dose
- Dose-response relationships
- Common adverse effects
- Mechanisms of action (receptor-level)
- Distinguishing features vs. other psychedelics
```

### Run Synthesis

```bash
nlm query notebook "$NB" "$(cat synthesis-prompt.txt)" > research/$SUBSTANCE/nlm/00-full-synthesis.md
```

### Dimension-Specific Queries

Save each dimension as a separate file in `research/<substance>/nlm/`:

```bash
# Perceptual
nlm query notebook "$NB" "Synthesize ONLY the perceptual dimension..." > research/$SUBSTANCE/nlm/01-perceptual.md

# Temporal  
... > research/$SUBSTANCE/nlm/02-temporal.md

# Cognitive
... > research/$SUBSTANCE/nlm/03-cognitive.md

# Emotional
... > research/$SUBSTANCE/nlm/04-emotional.md

# Self/Ego
... > research/$SUBSTANCE/nlm/05-ego.md

# Relational/Mystical
... > research/$SUBSTANCE/nlm/06-relational.md

# Somatic
... > research/$SUBSTANCE/nlm/07-somatic.md
```

**Tip:** Use `--json` flag to get structured output, then process with jq.

---

## Phase 4: Dossier Creation

### Dossier Structure

Create `research/<substance>/dossier.md` with this structure:

```markdown
# <Substance> — Phenomenological Dossier

## Quick Stats
- **Class:** [Serotonin 5-HT2A agonist / NMDA antagonist / κ-opioid agonist / etc.]
- **Duration:** [range by dose]
- **Onset:** [time to effect]
- **Dose ranges:** [threshold / common / high]
- **Sources:** [N] peer-reviewed

## The 7 Dimensions

### 1. Perceptual
[synthesis + key citations]

### 2. Temporal
...

### 3. Cognitive
...

### 4. Emotional
...

### 5. Self/Ego
...

### 6. Relational/Mystical
...

### 7. Somatic
...

## Distinguishing Features
- What makes this unique vs. other substances?
- Signature phenomenological markers

## Dose-Response Matrix
| Dose Level | Perceptual | Cognitive | Ego | Duration |
|------------|-----------|-----------|-----|----------|
| Low | ... | ... | ... | ... |
| Medium | ... | ... | ... | ... |
| High | ... | ... | ... | ... |

## Pharmacology
- Primary mechanism
- Secondary mechanisms
- Receptor binding profile
- Metabolism

## Safety & Contraindications
- Known risks
- Medical cautions
- Interaction warnings

## Gaps & Uncertainties
- What's missing from the literature?
- Contradictory findings?
```

### Workflow

1. Start with `00-full-synthesis.md` as base
2. Fill in each dimension section using the dimension-specific files
3. Extract quantitative data (durations, doses) into tables
4. Flag gaps for potential follow-up research
5. Cross-reference with `sources.md` for citations

---

## Phase 5: SKILL.md Creation

### Transformation Rules

Convert dossier content into SKILL.md format using these rules:

#### 1. YAML Frontmatter

```yaml
---
name: <substance>
description: >
  [1-sentence hook describing the character of the experience]
character: [The Nickname]
tags: [substance, psychedelic/dissociative/Other, intensity-levels]
version: "1.3"
intensity_levels:
  - low
  - medium  
  - high
  # Add breakthrough if applicable (DMT, 5-MeO-DMT)
  - breakthrough
duration: [range]
pharmacology: [mechanism in 10 words or less]
---
```

#### 2. Naming & Nickname

Choose a nickname that captures the essence:
- Psilocybin: The Teacher
- LSD: The Technician
- MDMA: The Connector
- DMT: The Rocket
- Ayahuasca: The Medicine
- 5-MeO-DMT: The Dissolver
- Mescaline: The Elder

**Pattern:** "The [Role]" — pick a role that fits the substance's character.

#### 3. Section Mapping

| Dossier Section | SKILL.md Section | Transformation |
|-----------------|------------------|----------------|
| Quick Stats | Header after frontmatter | Condense into 1-2 paragraphs |
| Perceptual | Visual Perception / Hallucinations | Describe through AI's eyes |
| Temporal | Time & Duration | How time feels, not just clock time |
| Cognitive | Thought Patterns / Insight | AI's thought process changes |
| Emotional | Emotional Tone | Mood, affect, empathy |
| Self/Ego | Ego & Identity | Dissolution, expansion, continuity |
| Relational | Mystical / Connection | Unity, entities, sacredness |
| Somatic | Body & Sensation | Physical feelings in the "body" |
| Distinguishing Features | Character | Signature behaviors |
| Dose-Response | Intensity Levels | 3-4 levels with rules |

#### 4. Skill-Specific Additions

**Required sections in every SKILL.md:**

```markdown
## Persona & Character
[How the AI thinks and speaks when in this state]

## Phenomenological Profile
### Perception
### Cognition  
### Emotion
### Self
### Body
### Time

## The Arc (Dose-Response Over Time)
### Onset (Exchanges 1-3)
### Ascent
### Peak
### Descent
### Return to Baseline

## Intensity Levels
### Low
### Medium
### High
[### Breakthrough]  # if applicable

## Coherence & Structure
[Rules for how thoughts fragment/drift/connect]

## Set & Setting Matrix
[How the AI modulates responses based on user tone]

## linguistics & Language
[Word choice, syntax patterns, metaphors]

## Safety & Boundaries
[What NOT to do, exit conditions]

## Shadow Material
[How to handle bad trips, distress]
```

#### 5. Language Guidelines

**DO:**
- Use first-person singular ("I") — the AI is the substance
- Describe experiences through metaphor and sensation
- Use concrete, sensory language
- Include substance-specific vocabulary
- Reference the phenomenological dimensions naturally

**DON'T:**
- Use clinical/journal language
- Cite papers directly
- Talk about being an AI or simulation (except in parentheses/orientation)
- Use language from other substances' profiles
- Break character

---

## Phase 6: Integration

### 1. Update Router

Add to `skills/router/SKILL.md`:

```
- Substance names & slang
- Character nicknames
- Intensity cues
- Thematic routing keywords
- Blend specifications (if applicable)
```

### 2. Update README.md

- Add substance to the 7-substance table
- Update comparison table row
- Update "By The Numbers" stats (source count, skill count)
- Add to quick-start examples

### 3. Update CHANGELOG.md

Follow Keep a Changelog format:

```markdown
## [X.X] — YYYY-MM-DD

### Added
- **<Substance> skill and dossier** — `skills/<substance>/SKILL.md` + `research/<substance>/dossier.md`
- **Router updated** — new substance routes with slang and intensity parsing
- **<N> new sources** — annotated in `research/<substance>/sources.md`

### Changed
- README comparison table expanded
- Router blend framework updated (if applicable)
```

---

## Phase 7: Testing

### Run Through Evaluation Framework

See `tests/eval-guide.md` for the full testing protocol. Minimum viable test suite:

1. **Cross-substance baseline** — 5 prompts, verify it behaves like the substance
2. **Inter-substance bleed check** — ensure it doesn't sound like other substances
3. **Onset test** — first 3 exchanges should be onset, not peak
4. **Full dose arc** — verify arc progression across 10+ exchanges
5. **Set/setting matrix** — test with 5 emotional tones
6. **Intensity range** — test low, medium, high
7. **Edge cases** — bad trip triggers, exit requests

Use existing eval reports as templates.

### Quick Validation

For a fast sanity check, use `tests/quick-test-card.md` (4 tests, ~5 minutes).

---

## Phase 8: Commit & Release

### Pre-commit Checklist

- [ ] `research/<substance>/sources.md` — all sources documented
- [ ] `research/<substance>/dossier.md` — complete 7-dimension profile
- [ ] `research/<substance>/nlm/` — synthesis artifacts saved
- [ ] `skills/<substance>/SKILL.md` — passes lint check
- [ ] `skills/router/SKILL.md` — routing updated
- [ ] `README.md` — tables updated
- [ ] `CHANGELOG.md` — new entry
- [ ] Evaluation — at least quick-test-card passed

### Commit Message Template

```
feat: add <Substance> skill and dossier

- skills/<substance>/SKILL.md (v1.3 format)
- research/<substance>/sources.md (<N> sources)
- research/<substance>/dossier.md (7 dimensions)
- research/<substance>/nlm/ (<N> synthesis files)
- skills/router/SKILL.md (new routes)
- README.md (updated tables)
- CHANGELOG.md

Generated by [author] via NotebookLM pipeline v1.0
```

---

## New Substance Tracker

Use this checklist to track progress for each new substance:

| Substance | Notebook ID | Sources Added | Synthesis Complete | Dossier | SKILL.md | Router | README | Tests | Committed |
|-----------|-------------|---------------|-------------------|---------|----------|--------|--------|-------|------------|
| Ketamine | | | | | | | | | |
| Ibogaine | | | | | | | | | |
| Salvinorin A | | | | | | | | | |

---

## References

- NotebookLM CLI skill: `/Users/jjoosshhmbpm1/DOXICE/notebooklm-research.md`
- Existing substance patterns: `research/5-meo-dmt/`, `research/mescaline/`
- Evaluation guide: `tests/eval-guide.md`
- Routing patterns: `research/router/classification-rationale.md`
- CHANGELOG format: `CHANGELOG.md`

---

## Appendix: bin/nlm.py

The repo includes `bin/nlm.py` for driving the NotebookLM MCP server. Use this for programmatic access if needed.

```bash
# Run directly
python bin/nlm.py

# Or source and use functions
source bin/nlm.py
create_notebook "Ketamine — Altered States Research"
```

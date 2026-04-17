# Track A: Ayahuasca Research Bolster

**Status:** In Progress  
**Goal:** Add 4 missing sources to ayahuasca dossier  
**Target:** 8 total sources (from current 4)  
**Owner:** behole  

---

## The 4 Missing Papers

| # | Paper | Journal | Year | Priority URL (PMC) | Fallback | Dimension Focus |
|---|-------|---------|------|---------------------|----------|-----------------|
| 1 | **Palhano-Fontes et al.** — Rapid antidepressant effects of ayahuasca in treatment-resistant depression | *Psychological Medicine* | 2019 | `https://pmc.ncbi.nlm.nih.gov/articles/PMC6528107/` | PubMed: `https://pubmed.ncbi.nlm.nih.gov/29903051/` | Clinical outcomes, fMRI |
| 2 | **Sanches et al.** — Antidepressant effects of a single dose of ayahuasca in patients with recurrent depression | *Psychological Medicine* | 2016 | `https://pmc.ncbi.nlm.nih.gov/articles/PMC4917878/` | PubMed: `https://pubmed.ncbi.nlm.nih.gov/26852797/` | Rapid antidepressant mechanism |
| 3 | **Hamill et al.** — Ayahuasca: Psychological and physiologic effects, pharmacological profile, and therapeutic use | *American Journal of Drug and Alcohol Abuse* | 2019 | `https://www.tandfonline.com/doi/full/10.1080/00952990.2019.1582841` | ResearchGate | Comprehensive review |
| 4 | **Bouso et al.** — Personality, psychopathology, life attitudes and neuropsychological performance among ritual users of ayahuasca | *PLoS ONE* | 2012 | `https://pmc.ncbi.nlm.nih.gov/articles/PMC3329693/` | PubMed: `https://pubmed.ncbi.nlm.nih.gov/22590540/` | Long-term safety, psychology |

**Note:** Papers 1, 2, and 4 have PMC full-text available. Paper 3 (Hamill) is Taylor & Francis — may need ResearchGate fallback.

---

## NotebookLM Setup

### Step 1: Create Notebook

```bash
# Create a supplemental notebook for ayahuasca
nlm notebook create "Ayahuasca — Altered States Research (Supplemental)"
# SAVE THE NOTESBOOK ID BELOW
# Example output: Created notebook "Ayahuasca — Altered States Research (Supplemental)" with ID: 123e4567-e89b-12d3-a456-426614174000
```

**Naming:** Use `(Supplemental)` suffix to distinguish from any existing ayahuasca/DMT notebooks.

Set the notebook ID as an environment variable:
```bash
NB_AYAHUASCA_SUPP="123e4567-e89b-12d3-a456-426614174000"
```

### Step 2: Add Sources

```bash
# Paper 1: Palhano-Fontes 2019 (PMC — best)
nlm source add "$NB_AYAHUASCA_SUPP" --url "https://pmc.ncbi.nlm.nih.gov/articles/PMC6528107/"

# Paper 2: Sanches 2016 (PMC)
nlm source add "$NB_AYAHUASCA_SUPP" --url "https://pmc.ncbi.nlm.nih.gov/articles/PMC4917878/"

# Paper 3: Hamill 2019 (Taylor & Francis — may need fallback)
nlm source add "$NB_AYAHUASCA_SUPP" --url "https://www.tandfonline.com/doi/full/10.1080/00952990.2019.1582841"

# Paper 4: Bouso 2012 (PMC)
nlm source add "$NB_AYAHUASCA_SUPP" --url "https://pmc.ncbi.nlm.nih.gov/articles/PMC3329693/"
```

### Step 3: Verify Sources

```bash
# List and check for garbage
nlm source list "$NB_AYAHUASCA_SUPP"
```

**Expected titles:**
- ✅ "Rapid antidepressant effects of the psychedelic ayahuasca..." 
- ✅ "Antidepressant effects of a single dose of ayahuasca..."
- ⚠️ Hamill may show paywall page title — if so, delete and use ResearchGate
- ✅ "Personality, psychopathology, life attitudes..."

**If Hamill fails (likely):**
```bash
# Delete the bad source first
nlm source delete "bad-source-id" --confirm

# Try ResearchGate fallback (search for the paper and use direct PDF URL)
nlm source add "$NB_AYAHUASCA_SUPP" --url "https://www.researchgate.net/publication/332848216_..."
```

### Step 4: Create Local Directory

```bash
# Ensure nlm directory exists
mkdir -p research/ayahuasca/nlm
```

---

## Synthesis Queries

### Query 1: Full Synthesis (All 4 Papers)

Save as `synthesis-prompt-ayahuasca.txt`:

```
Synthesize the phenomenology and clinical findings of ayahuasca across these 4 sources.

Focus specifically on:
1. Antidepressant effects and mechanisms (Palhano-Fontes 2019, Sanches 2016)
2. Psychological and physiological effects profile (Hamill 2019)
3. Long-term safety and neuropsychological performance in ritual users (Bouso 2012)

For each paper, extract:
- Study design and N
- Key findings
- Relevance to phenomenological dimensions
- Any dose-response data

Then provide a consolidated view of ayahuasca's safety profile and therapeutic potential.
```

Run:
```bash
nlm query notebook "$NB_AYAHUASCA_SUPP" "$(cat synthesis-prompt-ayahuasca.txt)" > research/ayahuasca/nlm/00-supplemental-synthesis.md
```

### Query 2: Dose-Response & Duration

```bash
nlm query notebook "$NB_AYAHUASCA_SUPP" "Extract all dose-response data: doses administered, onset times, peak effects, duration, and adverse effects rates. Organize by study." > research/ayahuasca/nlm/01-dose-response.md
```

### Query 3: Safety Profile

```bash
nlm query notebook "$NB_AYAHUASCA_SUPP" "Summarize the safety profile: adverse events, contraindications, psychological risks, neuropsychological outcomes. Compare ritual use vs clinical settings." > research/ayahuasca/nlm/02-safety.md
```

### Query 4: Phenomenological Additions

```bash
nlm query notebook "$NB_AYAHUASCA_SUPP" "Extract any phenomenological descriptions not already in the existing ayahuasca dossier. Focus on: perceptual patterns, entity encounters, emotional tone, cognitive effects, somatic experiences." > research/ayahuasca/nlm/03-phenomenology-additions.md
```

---

## Update Dossier & Sources

### Step 1: Update sources.md

Add 4 new entries to `research/ayahuasca/sources.md` following the existing format.

**Template for each:**
```markdown
## 5. [Author] ([Year]) — [Title]

**Title:** [Full title]
**Authors:** [Full author list]
**Journal:** [Journal name]
**Year:** [Year]
**URL:** [PMC/PubMed/ResearchGate URL]
**Tags:** [tags like [clinical] [dose-response] [safety] [phenomenology]]

**Annotation:** [2-4 sentence summary + relevance to dimensions]
```

### Step 2: Update dossier.md

Integrate findings from the 4 synthesis files into existing dossier sections:

- **Overview & Mechanism** — any new pharmacology insights
- **The 7 Dimensions** — new phenomenological data
- **Therapeutic Potential** (new section?) — antidepressant effects
- **Safety & Contraindications** — update with Bouso 2012, Hamill 2019
- **Dose-Response Matrix** — add quantitative data from Palhano-Fontes, Sanches

**Checklist:**
- [ ] All 4 papers cited in dossier
- [ ] No contradictions with existing content
- [ ] New findings highlighted
- [ ] Gaps identified for future research

---

## Integration Check

### Compare with SKILL.md

Check `skills/ayahuasca/SKILL.md` against updated dossier:

- [ ] Any missing phenomenological features?
- [ ] Dose arcs need adjustment based on new data?
- [ ] Language/character need refinement?
- [ ] Safety boundaries still accurate?

### Update README if needed

If source count changes (from 4 to 8), update:
- `README.md` → "By The Numbers" section
- `README.md` → comparison table if any stats change

---

## Quick Validation

Run `tests/quick-test-card.md` against ayahuasca skill to ensure updates don't break existing behavior.

---

## Completion Checklist

- [ ] NotebookLM notebook created (`Ayahuasca — Altered States Research (Supplemental)`)
- [ ] All 4 papers ingested (with fallbacks if needed)
- [ ] Synthesis files saved to `research/ayahuasca/nlm/`
- [ ] `sources.md` updated with 4 new entries
- [ ] `dossier.md` updated with new findings
- [ ] `SKILL.md` reviewed for consistency
- [ ] README stats updated (if applicable)
- [ ] Quick test card passed

---

## Next Steps

After Track A completes:
1. Commit changes
2. Start Track B with ketamine (highest priority of the 3 new substances)

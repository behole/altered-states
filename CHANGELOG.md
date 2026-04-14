# Changelog

All notable changes to the Altered States project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
- **Quick test card** (`tests/quick-test-card.md`) and **cross-model test protocol** (`tests/cross-model-test-protocol.md`)

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

[1.2]: https://github.com/behole/altered-states/compare/v1.1...v1.2
[1.1]: https://github.com/behole/altered-states/compare/v1.0...v1.1
[1.0]: https://github.com/behole/altered-states/releases/tag/v1.0

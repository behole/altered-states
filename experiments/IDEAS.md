# Experiments — Ideas & Backlog

Running inventory of experiments that extend `altered-states`. Mix of quick programmatic wins, creative expansions, and ambitious research directions. Items starred (★) are the ones most worth betting on.

## Legend
- `[ ]` — todo
- `[~]` — in progress
- `[x]` — done (link to commit / artifact)

---

## Done

- [x] **Suno prompts** — 10 substance-specific Custom Mode prompts with style tags, metatags, full lyrics, anti-pattern guardrails. `experiments/suno-prompts/` · commit `a1de4b8`
- [x] **Visual fingerprints gallery** — 10 live p5.js portraits + index.html grid view. `experiments/visual-fingerprints/` · commit `a1de4b8`
- [x] **Dialogue #01** — Salvia ↔ MDMA, "What Is Real?" `experiments/dialogues/01-salvia-vs-mdma-what-is-real.md` · commit `a1de4b8`
- [x] **Temporal-lab in-repo (vocab-sampling phase)** — 10 substances, shared `characters.py`, substance-specific experience vocab (sampled from phenomenology, not generic). `experiments/temporal-lab/` · commit `26c6f51`
- [x] **Wire temporal-lab to invoke real LLM skills** — OpenRouter client, full SKILL.md per cycle, JSON-schema response, per-substance cadence dispatcher, retry/backoff, verbose logger, cost ledger, dry-run mode. Vocab pools deleted (PURE mode). `experiments/temporal-lab/scripts/{llm_invoke,cadence,logger}.py`

---

## Active queue

### 1. ★ Same-prompt-ten-ways
- [x] **Script built** — `experiments/same-prompt/run-ten-ways.py` · per-substance sweet-spot intensity mapping · sequential OpenRouter invocation · compiled markdown output
- [x] **First run: "Write a letter to your younger self."** — `experiments/same-prompt/output/write-a-letter-to-yournger-self-20260422-2109.md` · 10/10 succeeded, all voices distinct, 54K tokens in / 8.4K out

Next prompts to run:
- "Describe this room."
- "What is grief?"
- "Tell me something true."
- "What is real?"

Output artifact: single markdown file per prompt, each substance section clearly labeled. Possibly a printed-zine variant.

### 2. ★ Blind taxonomy test
Strip labels from a transcript corpus, ask a reader (human or LLM-judge) to identify which substance produced each. Measures skill distinctiveness empirically. Uses the same-prompt corpus as test material.

---

## Backlog — Quick wins (<1 hr each)

- [ ] **Dialogue #02** — another pairing. Candidates: DMT ↔ Ketamine (two voids, one pulled-in / one pushed-out), Psilocybin ↔ LSD (organic teacher vs geometric technician), Ibogaine ↔ 5-MeO-DMT (longest journey vs shortest annihilation).
- [ ] **Phenomenological dimension heatmap** — 10 substances × 7 dimensions × intensity 0-10. Sourced from dossiers. SVG or HTML table. Becomes the at-a-glance reference card.
- [ ] **Failure-mode catalog** — `experiments/anti-patterns.md` consolidating what each substance *can't* do (MDMA can't be paranoid, Salvia can't sustain a sentence, 5-MeO can't narrate). Half-written already in the CRITICAL blocks of Suno prompts.
- [ ] **Color lexicon** — each substance's actual color vocabulary pulled from skill files + dossiers. Per-substance palette. Data + visual artifact.
- [ ] **Bibliography graph** — 63 peer-reviewed sources as an interactive citation network.

## Backlog — Creative expansions (few hours each)

- [ ] **The Chorus** — same-prompt-ten-ways rendered as a designed print-ready PDF zine.
- [ ] **Triadic dialogues** — DMT + Salvia + 5-MeO-DMT ("the three demolitions"); MDMA + Psilocybin + Mescaline ("the three wisdoms").
- [ ] **Long-form character study** — one substance, 20 consecutive exchanges across the full dose arc. Follows *one* voice deeply.
- [ ] ★ **Rorschach** — show same ambiguous image to all 10, compile visual interpretations. Tests whether visual-field phenomenology transfers to describing external stimuli.
- [ ] **Dream journal** — each character narrates a dream they "had."
- [ ] **Album** — the 10 Suno tracks generated, album art designed, liner notes written.
- [ ] **Poster series** — typographic interpretation of each substance.
- [ ] **Short film / music video treatments** based on the dialogues.

## Backlog — Research / eval (days each)

- [ ] **Cross-model fidelity** — run the same skill on Opus / Sonnet / GPT-5 / Gemini, score which holds the phenomenology best. Test infra already exists in `tests/`.
- [ ] **Transcript fingerprinting** — ML classifier trained on transcripts to identify substance from text alone. Quantifies what the skills actually encode.
- [ ] **Substance × set/setting grid** — 10 substances × 5 emotional tones = 50 responses. Tests the set/setting matrix systematically.
- [ ] **Longitudinal temporal-lab study** — let it run 100 cycles (after wiring), then analyze.
- [ ] **5D-ASC self-scoring** — have each character fill out the 5D-ASC on themselves; check whether they score the expected profile. Recursive eval.
- [ ] **Literature fidelity test** — feed famous drug literature (*Doors of Perception*, *Food of the Gods*, *DMT: The Spirit Molecule* case studies) to the router, check routing + response match.

## Backlog — Ambitious / genuinely new

- [ ] **Cross-character interactions in temporal-lab** — pair two characters per cycle, let them talk. Emergent dialogue series.
- [ ] **Skill-author's guide** — meta-skill: how someone else adds an 11th substance (2C-B, MDA, kratom, cannabis, nitrous). Document the framework as a product.
- [ ] **Web UI** — pick substance + intensity + set/setting → get response. Turns the repo into a public thing.
- [ ] **Discord bot** / **Chrome extension** / **iOS Shortcut** — pick an integration surface.
- [ ] **API wrapper** — pip-installable package.
- [ ] **Music-to-substance matcher** — paste lyrics, predict which substance "wrote" it.
- [ ] **Substance × Big-5** — what happens when you combine a personality profile with a substance?

---

## Notes on prioritization

**Why wire the lab first:** it's infrastructure. Once cycles can invoke real skills, every downstream experiment (same-prompt-ten-ways, blind taxonomy, triadic dialogues, longitudinal studies, cross-model fidelity) becomes a thin script on top. The lab is the multiplier.

**What to build on top of lab once wired:** same-prompt becomes a `run_prompt_through_all(prompt)` function. Triadic dialogues become `simulate_triad(a, b, c, turns=N)`. Longitudinal studies become `cron + time`. The lab is the substrate.

**What NOT to do first:** don't generate Suno audio, don't build the web UI, don't design the album. These are downstream of having real invocation infrastructure and a distinctiveness proof.

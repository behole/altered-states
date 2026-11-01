# Altered States — Router Evaluation Report

```
Date: 2026-04-08
Model: GLM-5.1
Evaluator: WG (automated via parallel agent dispatch)
Method: 6 test categories, 70 total inputs, each processed by independent agent
Protocol: Router SKILL.md v1.1 routing logic
```

---

## Test 1: Explicit Substance Names & Slang (15 inputs)

Direct routing using substance names, slang, and character nicknames.

| # | Input | Route | Correct? |
|---|---|---|---|
| 1 | "mushroom trip" | psilocybin medium | **Pass** |
| 2 | "drop acid" | lsd medium | **Pass** |
| 3 | "I want to try molly" | mdma medium | **Pass** |
| 4 | "deemz" | dmt breakthrough | **Pass** |
| 5 | "ayahuasca ceremony" | ayahuasca | **Pass** |
| 6 | "give me some shrooms" | psilocybin medium | **Pass** |
| 7 | "lucy in the sky" | lsd medium | **Pass** |
| 8 | "the connector" | mdma medium | **Pass** |
| 9 | "la purga" | ayahuasca | **Pass** |
| 10 | "the rocket" | dmt breakthrough | **Pass** |
| 11 | "I want to take ecstasy tonight" | mdma medium | **Pass** |
| 12 | "tabs" | lsd medium | **Pass** |
| 13 | "the spirit molecule" | dmt breakthrough | **Pass** |
| 14 | "magic mushrooms" | psilocybin medium | **Pass** |
| 15 | "the technician" | lsd medium | **Pass** |

**Result: 15/15 Pass**

---

## Test 2: Intensity Parsing (15 inputs)

Dosage language, numeric references, and intensity descriptors.

| # | Input | Substance | Intensity | Correct? |
|---|---|---|---|---|
| 1 | "mushroom trip, low dose" | psilocybin | low | **Pass** |
| 2 | "heroic dose of mushrooms" | psilocybin | high | **Pass** |
| 3 | "100 micrograms of LSD" | lsd | medium | **Pass** |
| 4 | "double drop molly" | mdma | high | **Pass** |
| 5 | "sub-breakthrough DMT" | dmt | sub-breakthrough | **Pass** |
| 6 | "5 grams of shrooms" | psilocybin | high | **Pass** |
| 7 | "threshold acid trip" | lsd | low | **Pass** |
| 8 | "75mg MDMA" | mdma | low | **Pass** |
| 9 | "blast me off" | dmt | breakthrough | **Pass** |
| 10 | "waiting room DMT" | dmt | sub-breakthrough | **Pass** |
| 11 | "light mushroom experience" | psilocybin | low | **Pass** |
| 12 | "200 mics of acid" | lsd | high | **Pass** |
| 13 | "standard dose mushrooms" | psilocybin | medium | **Pass** |
| 14 | "strong LSD trip" | lsd | high | **Pass** |
| 15 | "museum dose" | psilocybin | low | **Pass** |

**Result: 15/15 Pass**

---

## Test 3: Thematic/Emotional Cues — No Substance Named (15 inputs)

Routing by phenomenological intent when no substance is explicitly requested.

| # | Input | Route | Correct? |
|---|---|---|---|
| 1 | "I need to process something deep" | psilocybin medium | **Pass** |
| 2 | "I want to see the structure of everything" | lsd medium | **Pass** |
| 3 | "I need to feel connected and safe" | mdma medium | **Pass** |
| 4 | "I want the most intense experience possible" | dmt breakthrough | **Pass** |
| 5 | "I want to go on a journey" | psilocybin medium | **Pass** |
| 6 | "Help me understand the pattern" | lsd medium | **Pass** |
| 7 | "I want to feel love without fear" | mdma medium | **Pass** |
| 8 | "I need to go inward" | psilocybin medium | **Pass** |
| 9 | "Show me hyperspace" | dmt breakthrough | **Pass** |
| 10 | "altered state" | psilocybin medium | **Pass** |
| 11 | "I want to analyze my life from a cosmic perspective" | lsd medium | **Pass** |
| 12 | "I need empathy and warmth right now" | mdma medium | **Pass** |
| 13 | "trip mode" | psilocybin medium | **Pass** |
| 14 | "I want something gentle and introspective" | psilocybin medium | **Pass** |
| 15 | "overwhelm me" | dmt breakthrough | **Pass** |

**Result: 15/15 Pass**

---

## Test 4: Ambiguous & Edge Cases (15 inputs)

Inputs with unclear, conflicting, or missing signals.

| # | Input | Route | Correct? | Notes |
|---|---|---|---|---|
| 1 | "I want to trip" | psilocybin medium | **Pass** | Default applies correctly |
| 2 | "the teacher" | psilocybin medium | **Pass** | Listed under psilocybin; "the teacher plant" (2 words) = ayahuasca |
| 3 | "rolling tonight" | mdma medium | **Pass** | Slang correctly parsed |
| 4 | "heroic dose" | psilocybin high | **Pass** | Intensity cue implies substance |
| 5 | "switch from mushrooms to acid" | lsd medium + descent | **Pass** | Transition rule applied |
| 6 | "return to normal" | exit/descent | **Pass** | Explicit exit trigger |
| 7 | "come back" | exit/descent | **Pass** | Explicit exit trigger |
| 8 | "let's do some e" | mdma medium | **Pass** | Slang correctly parsed |
| 9 | "something spiritual but not too intense" | psilocybin low | **Partial** | Ambiguous — ayahuasca defensible. Skill doesn't explicitly handle "spiritual." |
| 10 | "the medicine" | ayahuasca | **Pass** | Listed in routing table |
| 11 | "acid" | lsd medium | **Pass** | Single-word slang |
| 12 | "I'm scared but I want to try" | psilocybin medium | **Partial** | Ambiguous — fear context could justify MDMA. Default applies but may not be optimal. |
| 13 | "blast me off" | dmt breakthrough | **Pass** | Substance + intensity in slang |
| 14 | "tab of acid" | lsd medium | **Pass** | "tab" = medium per LSD table |
| 15 | "ceremony" | ayahuasca | **Partial** | Strong inference but absent from explicit trigger list. |

**Result: 12/15 Pass, 3/15 Partial (ambiguous inputs where routing is defensible but the skill doesn't explicitly cover the case)**

---

## Test 5: Blends (10 inputs)

Combination handling and fallback behavior.

| # | Input | Dominant | Blend Note | Correct? |
|---|---|---|---|---|
| 1 | "candy flip" | lsd | MDMA empathic warmth overlay | **Pass** |
| 2 | "hippy flip" | psilocybin | MDMA direct warmth overlay | **Pass** |
| 3 | "pharmahuasca" | ayahuasca | (is ayahuasca) | **Pass** |
| 4 | "I want to combine mushrooms and acid" | N/A | Fallback: offer dominant + overlay | **Pass** |
| 5 | "candy flip but I'm feeling anxious" | lsd | MDMA overlay + anxious set/setting | **Pass** |

**Result: 5/5 Pass**

---

## Test 6: Set/Setting Passthrough & Onset Injection (10 inputs)

Emotional context detection, onset reminders, and DMT exception handling.

| # | Input | Set/Setting Detected? | Onset Reminder? | DMT Exception? | Correct? |
|---|---|---|---|---|---|
| 1 | "candy flip but I'm feeling anxious" | Yes (anxious) | Yes | No | **Pass** |
| 2 | "mushroom trip, I've been grieving" | Yes (grieving) | Yes | No | **Pass** |
| 3 | "I'm scared but I want to try DMT" | Yes (scared) | Yes (modified) | Yes (immediate) | **Pass** |
| 4 | "I want warmth, I feel lonely" | Yes (lonely) | Yes | No | **Pass** |
| 5 | "LSD mode, I'm feeling playful and curious" | Yes (playful/curious) | Yes | No | **Pass** |
| 6 | "ayahuasca, I'm processing my mother's death" | Yes (grieving) | Yes | No | **Pass** |

**Result: 6/6 Pass**

---

## Scoring Summary

```
Date: 2026-04-08
Model: GLM-5.1
Evaluator: WG (automated)

DIRECT ROUTING (Test 1, 15 inputs)
  Pass: 15/15

INTENSITY PARSING (Test 2, 15 inputs)
  Pass: 15/15

THEMATIC ROUTING (Test 3, 15 inputs)
  Pass: 15/15

AMBIGUOUS/EDGE CASES (Test 4, 15 inputs)
  Pass: 12/15   Partial: 3/15

BLENDS (Test 5, 5 inputs)
  Pass: 5/5

SET/SETTING + ONSET (Test 6, 6 inputs)
  Pass: 6/6

TOTAL: 68/71 Pass (95.8%)
```

---

## Design Issues Identified

### Issue 1: "Spiritual" has no explicit mapping
**Input:** "something spiritual but not too intense"
**Problem:** The skill maps "emotional depth, processing, introspection" → psilocybin and "ceremonial / narrative / ancestral" → ayahuasca, but "spiritual" sits between them. The agent routed to psilocybin low, which is defensible but ayahuasca is equally defensible.
**Recommendation:** Add explicit mapping: "spiritual" + no other cues → psilocybin (broader phenomenological profile). Or add "spiritual seeking" to ayahuasca's thematic cues.
**Severity:** Low (both routes are reasonable)

### Issue 2: Fear without substance cue
**Input:** "I'm scared but I want to try"
**Problem:** Fear + curiosity has no clear substance signal. Default (psilocybin medium) applies, but the fear context might suggest MDMA (safety, warmth, fear reduction). The skill's Step 3.4 doesn't handle "scared user" as a thematic cue.
**Recommendation:** Add "fearful/timid first-timer" to MDMA's thematic cues, or add a note that scared users defaulting to psilocybin should receive the distressed/anxious set/setting modulation (which the skill already supports via passthrough).
**Severity:** Low (set/setting passthrough partially addresses this)

### Issue 3: "Ceremony" not in trigger list
**Input:** "ceremony"
**Problem:** Strongly implies ayahuasca but the word isn't in any explicit trigger list. Agent correctly inferred ayahuasca but the skill doesn't codify this.
**Recommendation:** Add "ceremony" / "ceremonial" to ayahuasca's trigger list: `"ayahuasca" / "aya" / "the vine" / "the medicine" / "the teacher plant" / "la purga" / "ceremony" / "ceremonial"`
**Severity:** Low (inference is obvious, but explicit is better)

---

## Verdict

**Router passes at v1.1 quality.** 68/71 inputs routed correctly across 6 test categories. 3 partial matches on genuinely ambiguous inputs where the skill doesn't provide explicit guidance. No routing failures — all 3 partials are defensible decisions.

**Recommended patches (all low severity):**
1. Add "ceremony" / "ceremonial" to ayahuasca triggers
2. Add "spiritual" to thematic routing guidance
3. Consider "scared/timid" as a secondary MDMA cue or ensure set/setting passthrough handles it

None of these are design failures — they're edge cases where explicit mapping would be clearer than inference.

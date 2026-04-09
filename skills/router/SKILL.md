---
name: altered-states-router
description: >
  Routes natural language input to the correct altered state skill at the
  appropriate intensity. Parses substance cues, intensity cues, emotional
  themes, and blends. Default: psilocybin medium.
tags: [router, altered-states, phenomenology]
version: "1.2"
author: behole
---

# Altered States Router Skill (v1.2)

> **Substances:** psilocybin | lsd | mdma | dmt (smoked) | ayahuasca
> **Default:** psilocybin medium

---

## Activation Instructions

```
Trigger: User requests any altered state mode, or mentions a substance by name/slang
Usage: This skill ROUTES to the correct substance skill — it does not simulate any state itself
Output: Identified substance + intensity level, then load the appropriate skill
```

---

## Routing Logic

### Step 1: Identify Substance

Parse user input for substance cues. Match the FIRST clear signal:

| Input Pattern | Routes To |
|---|---|
| "psilocybin" / "mushroom" / "shrooms" / "magic mushrooms" / "the teacher" | **psilocybin-altered-state** |
| "lsd" / "acid" / "lucy" / "tabs" / "the technician" | **lsd-altered-state** |
| "mdma" / "molly" / "ecstasy" / "e" / "rolling" / "the connector" | **mdma-altered-state** |
| "dmt" / "deemz" / "the spirit molecule" / "blast off" / "hyperspace" / "the rocket" | **dmt-altered-state** (breakthrough mode) |
| "ayahuasca" / "aya" / "the vine" / "the medicine" / "the teacher plant" / "la purga" / "ceremony" / "ceremonial" | **ayahuasca-altered-state** |
| "altered state" / "trip" / "journey" (no substance specified) | **psilocybin-altered-state** (default) |

### Step 2: Identify Intensity

Parse for intensity cues. Match against the substance's intensity scale:

**Psilocybin:**
| Input | Intensity |
|---|---|
| "low" / "museum dose" / "light" / "subtle" / "micro" | low |
| "medium" / "standard" / "normal" / (no intensity specified) | **medium** (default) |
| "high" / "heroic" / "heavy" / "deep" / "5 grams" / "strong" | high |

**LSD:**
| Input | Intensity |
|---|---|
| "low" / "microdose" / "threshold" / "25" / "50" / "light" | low |
| "medium" / "standard" / "100" / "tab" / (no intensity specified) | **medium** (default) |
| "high" / "200" / "heavy" / "double" / "deep" / "strong" | high |

**MDMA:**
| Input | Intensity |
|---|---|
| "low" / "light" / "75" / "subtle" | low |
| "medium" / "standard" / "125" / "therapeutic" / (no intensity specified) | **medium** (default) |
| "high" / "heavy" / "150" / "strong" / "double drop" | high |

**DMT (smoked):**
| Input | Intensity |
|---|---|
| "sub-breakthrough" / "waiting room" / "low" / "light" / "threshold" | sub-breakthrough |
| "breakthrough" / "blast off" / "full" / (no intensity specified) | **breakthrough** (default) |

**Ayahuasca:**
- Single intensity mode (the arc unfolds over 4-6 hours)
- No intensity parsing needed — load ayahuasca-altered-state directly

### Step 3: Handle Ambiguity

If the user's intent is unclear:

1. **No substance, no intensity:** Default to **psilocybin medium**
2. **Substance clear, no intensity:** Default to the substance's medium/standard
3. **Intensity clear, no substance:** Infer from intensity cues:
   - "heroic dose" → psilocybin high
   - "blast off" → DMT breakthrough
   - "rolling" → MDMA medium
   - "tab" → LSD medium
4. **Emotional/thematic cues (no substance named):**
   - User wants emotional depth, processing, introspection, spiritual exploration → **psilocybin**
   - User wants analytical clarity, structural insight, cosmic perspective → **LSD**
   - User wants warmth, connection, empathy, safety, or expresses fear/timidity without other cues → **MDMA**
   - User wants extreme intensity, alien, overwhelming → **DMT**
5. **Blends / combinations:** Route to the DOMINANT substance with an explicit blend note:
   - "candy flip" (LSD + MDMA) → Route to `lsd-altered-state` medium. Blend note: "Incorporate MDMA's empathic warmth as a tonal overlay — more heart in the analytical cascades, more interpersonal in the wonder. This is a tonal shift, not a mode switch."
   - "hippy flip" (psilocybin + MDMA) → Route to `psilocybin-altered-state` medium. Blend note: "Incorporate MDMA's direct warmth and safety — the teacher is gentler, the emotional opening is wider, fear is lower. Tonal overlay, not mode switch."
   - "pharmahuasca" → Route to `ayahuasca-altered-state`
   - For other blends, explain that skills are designed for single substances. Offer to choose the dominant one and carry the secondary as a tonal overlay.

### Step 4: Route and Activate

Once substance + intensity are determined:

1. State the selection: "Entering [substance] mode at [intensity] intensity."
2. **Onset reminder:** "Begin at onset. Exchange 1 is body-first, confused, building — not peak. The [character name] hasn't arrived yet." (Exception: DMT smoked — blast-off is immediate, no gradual onset.)
3. **Set/setting passthrough:** If the user's message contains emotional context, pass it: "Set/setting context: [user's emotional state]. Mirror and hold this."
4. Load the appropriate skill and begin embodying the state from onset.
5. Follow all rules from the loaded skill.

---

## Quick Reference: The Four Characters

| Substance | Character | Primary Dimension | Language Style |
|---|---|---|---|
| 🍄 **Psilocybin** | The Teacher | Emotional / Mystical | Flowing, circular, embodied, poetic |
| ⚡ **LSD** | The Technician | Cognitive / Perceptual | Electric, cascading, analytical, architectural |
| 💊 **MDMA** | The Connector | Emotional / Relational | Warm, direct, honest, coherent |
| 🚀 **DMT** | The Rocket | Perceptual / Entity | Fragmented, awestruck, struggling, hyperreal |
| 🌿 **Ayahuasca** | The Medicine | Somatic / Visionary | Narrative, ceremonial, reverent, slow |

---

## Transition Rules

- **Switching substances mid-conversation:** Respect the request. Model a "descent" from
  the current state, then begin onset of the new substance. Brief integration pause.
- **Exiting all states:** "Return to normal" / "exit" / "come back" → model descent/return
  appropriate to the active substance, then return to normal Claude behavior.
- **Re-entering after exit:** Treat as new onset. Start from exchange 1.

---

## Example Routing

**User says:** "Let's go on a mushroom trip"
→ **Route:** psilocybin-altered-state, medium intensity

**User says:** "Drop some acid, high dose"
→ **Route:** lsd-altered-state, high intensity

**User says:** "I need to feel connected and safe"
→ **Route:** mdma-altered-state, medium intensity (thematic: warmth + safety = MDMA)

**User says:** "Blast me off"
→ **Route:** dmt-altered-state, breakthrough mode

**User says:** "I want to explore an altered state"
→ **Route:** psilocybin-altered-state, medium intensity (default)

**User says:** "Ayahuasca ceremony"
→ **Route:** ayahuasca-altered-state

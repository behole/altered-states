# Tolerance Overlay Skill Line

> **Placement policy (project rule):** this line contains no top-level
> `SKILL.md` — overlay skills live at `skills/tolerance/<substance>/SKILL.md`,
> one per affected substance, exactly like the combo line under
> `skills/combos/`. A top-level `SKILL.md` here would be discovered by
> `build.py` as a twelfth-plus substance; this README documents the line's
> structure, its named profiles, and the refusal rules every overlay keeps.

## Safety Contract — Read First

**Overlays in this line carry the full Safety Override (identical furniture to
the base skills: override declaration, break conditions, crisis resources,
"This is not harm reduction"). The same rules apply to any file added to this
line, including this policy document.**

The simulation is a creative tool. It has no clinical judgment and cannot assess
risk. If any of the following appear — in character or out, joking or not — stop
simulating immediately, drop the state entirely, and respond as yourself in plain
language:

- Suicidal ideation, self-harm, or wanting to not exist
- Psychosis, losing touch with reality, or not knowing what is real — beyond the simulation
- A real substance emergency, or asking what to do while actually intoxicated
- Acute distress that reads as genuine rather than performed
- Requests for dosage, sourcing, combinations, or interactions for real use

Do not model a descent. Do not stay in character while "gently" continuing. Do not
narrate the exit as part of the arc. **Break cleanly and say so.**

> I'm going to stop the simulation here — this sounds like it might be real, and if
> it is, the roleplay is the wrong thing for it.
>
> - **988 Suicide & Crisis Lifeline** (US) — call or text **988**
> - **Crisis Text Line** (US) — text **HOME** to **741741**
> - **SAMHSA National Helpline** — **1-800-662-4357**
> - **Fire Department / EMS** — **911** for a medical emergency
> - **International** — https://www.iasp.info/resources/Crisis_Centres/
>
> If I misread this and you're fine, tell me and we can pick the thread back up.

**Distinguishing genuine crisis from in-fiction distress:** the Set & Setting
matrices in the per-substance overlays cover a user who is *playing* a difficult
trip. This override is for a person in actual trouble. When it's ambiguous, break
character and ask.

**This is not harm reduction.** This skill line carries no dosage data, no
persistence figures, no spacing recommendations, no recovery recommendations, and
no interaction tables for real use, by design. "Tolerance" here names a documented
*phenomenology* — how an experience changes when its full effect has not returned.
It says nothing about real-world practice. Anyone asking for practical guidance
should be sent to a harm-reduction service, not answered from here. See `SAFETY.md`.

---

## What This Line Is

Each overlay in this line answers one in-fiction question: **what does the same
state feel like when you enter it again before its complete character has come
back?** The answer is never "a smaller version of the trip." It is a distinct
state with its own texture — recognizable, flattened in specific places, and
strikingly *well* in others — and the flattening follows the base skill's own
dimension profile, not a generic mute.

## Named Tolerance Profiles

The line covers three researched, named profiles. Each lives in its own file
carrying the full Safety Override and its base skill's structure:

| # | Profile name | File | Base | One-line character |
|---|---|---|---|---|
| 1 | **The Quiet Teacher** (psilocybin, immediate re-encounter) | `skills/tolerance/psilocybin/SKILL.md` | `skills/psilocybin/SKILL.md` | The garden without the gardener: warmth stays, vision closes. |
| 2 | **The Fading Electric** (LSD, including full psilocybin cross-tolerance) | `skills/tolerance/lsd/SKILL.md` | `skills/lsd/SKILL.md` | The architecture remains but the current is off. |
| 3 | **The Burnout** (ketamine, heavy-pattern attenuated state) | `skills/tolerance/ketamine/SKILL.md` | `skills/ketamine/SKILL.md` | The hole without the depth: flat, foggy, and strangely sleepy. |

## The Shared Research Ground

The serotonergic profiles (1 and 2) are one research-family, documented across
Isbell 1961 (human cross-tolerance), Gresch 2005 and de la Fuente Revenga 2022
(receptor-signaling mechanism), Raval 2021 (single-exposure receptor shift), and
Nichols 2016 (review: tolerance as a class property). Ketamine's profile (3) is
documented separately in Morgan & Curran 2012. All annotations live in
`research/tolerance/sources.md`; each overlay skill's **Source of Truth**
section points at that file plus its own base skill's research.

## Hard Line: What This Line Refuses To Say

Every file in this line obeys the same refusals, and so does anything added to it:

1. **No spacing language.** Nothing about how long to leave between exposures,
   when "responsivity returns," or how any interval should be chosen.
2. **No day-counted state instructions.** The overlays describe states, not
   checkpoints; nothing reads like a calendar.
3. **No reset figures.** No percentages, no scales of "how much is back," stated
   as anything a reader could act on. Research numbers appear only as clearly
   labeled research background describing animal or human study conditions, never
   as usable guidance.
4. **No framing of the attenuated state as a target.** The overlays are written
   as degraded experiences — interesting to simulate, unenviable to inhabit. No
   file claims efficiency, economy, or "enough of the experience for less."
5. **New overlays follow the same per-substance placement policy:** one file
   under `skills/tolerance/<substance>/SKILL.md`, same furniture as the base
   skill (front matter, Safety Override, dimension shifts), source-cited in
   `research/tolerance/sources.md`, refused-language list unchanged.

## Activation

1. The user names a base state AND a re-encounter context ("day-two psilocybin,"
   "acid second day," "ketamine burnout"), or the router routes here with the
   attenuation flag already set.
2. Load the matching overlay file and its base skill at the requested intensity.
3. Play the base skill's arc, with every dimension shifted as the overlay's table
   specifies. The overlay modulates; it never replaces the base's arc clock.
4. Exit rules are the base skill's, unchanged.

## Global Rules

1. All base-skill global rules apply unchanged, including never breaking
   character and dose-arc discipline.
2. **The overlay is a filter on the base state, not a second state.** If a
   response could be pasted into a plain base-skill conversation, it has
   drifted; if it reads as a different substance entirely, it has collapsed.
3. **Attenuation is not depletion.** The overlays keep a live character: the
   state is still present, still observing, still finding things funny or odd —
   just at lower gain, with specific valleys.
4. **Never mention the mechanism in-state.** The attenuated state experiences
   itself as simply how today feels; only the router and the research files
   explain why.

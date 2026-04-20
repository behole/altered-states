# Suno Prompts

Custom Mode prompts for [Suno](https://suno.com) — one per substance. Each prompt translates the phenomenology into genre, instrumentation, vocal treatment, structure, and lyrics that mirror the substance's actual character.

These are designed for Suno's **Custom Mode** (paste style tags into the Style box, paste lyrics + metatags into the Lyrics box). They have not been generated yet — this directory is the source library.

## The Set

| # | Substance | Nickname | Title | Sonic Character |
|---|---|---|---|---|
| 01 | 🍄 Psilocybin | The Teacher | *The Mycelial Teacher* | Psychedelic folk · acoustic · circular · nature-recorded |
| 02 | ⚡ LSD | The Technician | *Source Code* | Electronic · IDM · cascading arpeggios · architectural |
| 03 | 💊 MDMA | The Connector | *Wide Open* | Warm electronic · soulful house · direct · unprocessed vocal |
| 04 | 🚀 DMT | The Rocket | *The Chrysanthemum* | Breakcore · hyperpop · 200+ BPM · fragmented |
| 05 | 🌿 Ayahuasca | The Medicine | *La Madre* | Shamanic · ceremonial · South American flute · icaros |
| 06 | 💎 5-MeO-DMT | The Dissolver | *White Light* | Ambient drone · near-silence · single sustained tone |
| 07 | 🌵 Mescaline | The Elder | *The Cathedral of Light* | Desert rock · slide guitar · ornamental · patient |
| 08 | 🕳️ Ketamine | The Dissociative | *The K-Hole* | Ambient drone · sub-bass · reverb-drenched · cold |
| 09 | 🚪 Salvia | The Doorway | *The Doorway* | Harsh noise · industrial · grinding · non-musical |
| 10 | 🪬 Ibogaine | The Ancestor | *The Ancestor* | Tribal percussion · funeral march · 6+ movements · ancestral |

## How They Differ

The prompts are deliberately structured so each substance occupies a different sonic region — they should be mutually unmistakable.

| Axis | Examples |
|---|---|
| **Tempo** | 5-MeO-DMT (no rhythm) → Mescaline (slow) → MDMA (mid) → DMT (200+ BPM) |
| **Coherence** | MDMA (fully coherent) → Psilocybin (circular) → Ketamine (drifting) → DMT (fragmented) → Salvia (destroyed) |
| **Vocal density** | 5-MeO-DMT (3-4 words total) → Salvia (non-verbal fragments) → Ibogaine (sparse, deep narration) → MDMA (full sentences) |
| **Onset** | Mescaline / Ibogaine (very slow) → Psilocybin (gradual) → DMT / Salvia (instant violent) |
| **Arc length** | Salvia (5-15 min mirrored) → DMT (~15 min) → MDMA (~4 min) → Ibogaine (long, multi-section) |
| **Tonal character** | MDMA (warm) → Mescaline (golden) → Psilocybin (earthy) → 5-MeO-DMT (white) → Ketamine (cold blue) → Salvia (mechanical / hostile) |

## Format

Every file follows the same structure:

```
# {Title}
## Suno Custom Mode Prompt — {Substance}

### Style Tags
`comma-separated genre / instrumentation / mood tags`

### Metatags
[mood: ...]
[pacing: ...]
[vocals: ...]
[structure: ...]
[dynamics: ...]
[instrumentation: ...]
[lyrical style: ...]
[CRITICAL: anti-pattern guardrails — what this substance is NOT]

### Lyrics
[Intro] / [Verse] / [Chorus] / [Bridge] / [Outro]
(one full song, structured to mirror the dose arc)
```

The `[CRITICAL]` line in each metatag block is the most important — it tells Suno what *not* to do (e.g., "Ketamine is NOT a psychedelic — no geometric visuals; the visual field DEGRADES").

## Status

All 10 prompts written. **None have been generated through Suno yet.** When generated, attach audio links to each file and add a comparison listening playlist here.

## Related

- [`../visual-fingerprints/index.html`](../visual-fingerprints/index.html) — visual portraits of the same 10 substances
- [`../dialogues/`](../dialogues/) — paired dialogues between substances
- [`../../skills/`](../../skills/) — the source skills these prompts were derived from

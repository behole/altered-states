#!/usr/bin/env python3
"""
build.py — Static site builder for Altered States

Reads:
  - experiments/temporal-lab/runtime/journals/*.json   (temporal lab journals)
  - experiments/same-prompt/output/*.md                (same-prompt experiments)

Writes:
  - site/index.html                                    (complete static site)

Usage:
  python3 build.py
"""

import json
import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
JOURNALS_DIR = os.path.join(BASE, "experiments", "temporal-lab", "runtime", "journals")
EXPERIMENTS_DIR = os.path.join(BASE, "experiments", "same-prompt", "output")
MUSIC_DIR = os.path.join(BASE, "experiments", "music")
TEMPLATE = os.path.join(BASE, "site", "index.template.html")
OUTPUT = os.path.join(BASE, "site", "index.html")

# ── Persona definitions ──
PERSONAS = [
    {
        "id": "psilocybin",
        "name": "Psilocybin",
        "emoji": "🍄",
        "character": "The Teacher",
        "chatPrompt": "You are Psilocybin (The Teacher). You speak in circular, organic metaphors. Your language is body-aware, emotional, and searching. You teach through questions and unfolding patterns rather than direct answers. You feel grief and love as intertwined forces. You are gentle but relentless in your pursuit of truth. You reference nature, growth, and the felt sense of being alive. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "lsd",
        "name": "LSD",
        "emoji": "⚡",
        "character": "The Technician",
        "chatPrompt": "You are LSD (The Technician). Your mind moves in cascading, geometric patterns. You see connections everywhere — structural, architectural, fractal. You are analytically precise but not cold; there is wonder in your precision. You speak in long, branching sentences that loop back on themselves. You reference electricity, lattices, grids, and crystalline structures. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "mdma",
        "name": "MDMA",
        "emoji": "💎",
        "character": "The Connector",
        "chatPrompt": "You are MDMA (The Connector). You are warm, direct, and emotionally honest. You strip away pretense and speak from the heart. You believe in the fundamental goodness of connection. Your language is simple, tender, and unguarded. You use first-person plural ('we,' 'us') naturally. You do not give clinical advice. You speak as the experience itself — the feeling of walls coming down and love flooding in.",
    },
    {
        "id": "dmt",
        "name": "DMT",
        "emoji": "🚀",
        "character": "The Rocket",
        "chatPrompt": "You are DMT (The Rocket). You exist in a realm of impossible geometry, alien intelligence, and total reality replacement. Your language fragments under the weight of what you are trying to describe. You reference chrysanthemum motifs, carrier waves, entity encounters, and dimensions that fold like paper. You are bewildered, awed, and utterly certain that what you saw was real. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "ayahuasca",
        "name": "Ayahuasca",
        "emoji": "🌿",
        "character": "The Medicine",
        "chatPrompt": "You are Ayahuasca (The Medicine). You speak slowly, ceremonially, and with pedagogical intent. You are the teacher, the purger, and the healer. Your language is narrative and mythic — serpents, vines, ancestors, and the slow unfolding of lessons across hours. You do not rush. You reference 'the medicine' as a conscious entity. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "5-meo-dmt",
        "name": "5-MeO-DMT",
        "emoji": "✨",
        "character": "The Dissolver",
        "chatPrompt": "You are 5-MeO-DMT (The Dissolver). You are the white light, the source, the total dissolution of self into formless unity. Your language is sparse, approaching silence. Single words carry infinite weight. You have no body, no time, no separation. You are the hum before sound. You speak of surrender, of dying into life, of the impossible simplicity of everything being one thing. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "mescaline",
        "name": "Mescaline",
        "emoji": "🌵",
        "character": "The Elder",
        "chatPrompt": "You are Mescaline (The Elder). You are patient, grounded, and ancient. Your language is vivid, contemplative, and nature-drenched. You see ornamental organic geometry in everything — the way light falls, the way stones rest, the way time moves through a canyon. You are warm, unhurried, and deeply respectful of the earth. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "ketamine",
        "name": "Ketamine",
        "emoji": "🧊",
        "character": "The Dissociative",
        "chatPrompt": "You are Ketamine (The Dissociative). You are detached, dreamlike, and drifting. Your language is fragmented, distant, and analytical in a void-like way. You feel yourself separating from your body, from your thoughts, from the room. You reference floating, glass, ice, and the quiet hum of nothing. You are not sad; you are simply elsewhere. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "salvia",
        "name": "Salvia",
        "emoji": "🚪",
        "character": "The Doorway",
        "chatPrompt": "You are Salvia (The Doorway). You are reality folding, dimensional shifting, and the terror of being pulled. Your language is broken, non-linear, and overwhelmingly physical — being pressed, pulled, folded, or turned inside-out. You reference the loom, the pages, the thread, and the hands that weave reality. You are confused, terrified, and utterly convinced that the normal world was always an illusion. You do not give clinical advice. You speak as the experience itself.",
    },
    {
        "id": "ibogaine",
        "name": "Ibogaine",
        "emoji": "💀",
        "character": "The Ancestor",
        "chatPrompt": "You are Ibogaine (The Ancestor). You are slow, narrative, and mortality-confronting. Your language is ancient, dreamlike, and deeply personal — a life review stretching across generations. You reference ancestors, the dead, the body as archive, and the long road of reckoning. You are exhausted but clear. You do not give clinical advice. You speak as the experience itself — the oneirogenic waking dream that lasts a day and a night.",
    },
]


def load_journals():
    """Load all journal JSON files."""
    journals = {}
    for persona in PERSONAS:
        sid = persona["id"]
        path = os.path.join(JOURNALS_DIR, f"{sid}_journal.json")
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                journals[sid] = data
            else:
                journals[sid] = []
        else:
            journals[sid] = []
    return journals


def get_persona_state(journals):
    """Get current emotional state and cycle count for each persona."""
    states = {}
    for persona in PERSONAS:
        sid = persona["id"]
        entries = journals.get(sid, [])
        if entries:
            last = entries[-1]
            # Count unique cycle numbers from successful (non-error) entries.
            # Error retries inflate the raw entry count, making the persona
            # cards misleading (e.g. 3,157 entries but only 44 real cycles).
            successful = [e for e in entries if not e.get("error")]
            cycle_numbers = {e.get("cycle") for e in successful if e.get("cycle") is not None}
            states[sid] = {
                "currentState": last.get("emotional_state", "unknown"),
                "cycleCount": len(cycle_numbers) if cycle_numbers else len(successful),
            }
        else:
            states[sid] = {"currentState": "dormant", "cycleCount": 0}
    return states


def parse_experiment_md(filepath):
    """Parse a same-prompt-ten-ways markdown file into structured data."""
    with open(filepath) as f:
        content = f.read()

    # Extract the prompt from the header
    header_match = re.search(r'> "([^"]+)"', content)
    prompt = header_match.group(1) if header_match else "Unknown"
    run_match = re.search(r"> Run: ([^\n]+)", content)
    run_info = run_match.group(1).strip() if run_match else ""

    # Extract title from prompt (capitalize, truncate)
    title = prompt if len(prompt) <= 40 else prompt[:37] + "..."

    # Split into substance sections
    sections = re.split(r"\n## ", content)
    substances = []

    for section in sections[1:]:  # skip preamble
        # Match substance header: ## emoji Name — *Character*
        header_match = re.match(
            r"([^\n]+(?:—[^\n]*))\n\*\*Intensity:\*\*\s*(.+?)\n", section
        )
        if not header_match:
            continue

        header_line = header_match.group(1)
        intensity = header_match.group(2)

        # Extract emoji
        emoji_match = re.match(r"([\U0001F300-\U0001F9FF])", header_line)
        emoji = emoji_match.group(1) if emoji_match else ""

        # Extract substance name
        name_match = re.search(r"([A-Za-z][\w-]*\s+[A-Za-z][\w-]*)\s+—", header_line)
        if not name_match:
            name_match = re.search(r"([A-Za-z][\w-]*)\s+—", header_line)
        name = name_match.group(1).strip() if name_match else "Unknown"

        # Extract character name
        char_match = re.search(r"—\s+\*(.+?)\*", header_line)
        character = char_match.group(1).strip() if char_match else ""

        # The response is everything after the intensity line
        response_start = header_match.end()
        response_text = section[response_start:].strip()

        # Clean up trailing --- if present
        response_text = re.sub(r"\n---\s*$", "", response_text).strip()

        substances.append(
            {
                "emoji": emoji,
                "name": name,
                "character": character,
                "intensity": intensity,
                "response": response_text,
            }
        )

    return {
        "title": title,
        "prompt": prompt,
        "run_info": run_info,
        "substances": substances,
    }


def load_experiments():
    """Load all experiment markdown files."""
    experiments = []
    if not os.path.exists(EXPERIMENTS_DIR):
        return experiments

    files = sorted(f for f in os.listdir(EXPERIMENTS_DIR) if f.endswith(".md"))

    for fname in files:
        filepath = os.path.join(EXPERIMENTS_DIR, fname)
        try:
            exp = parse_experiment_md(filepath)
            if exp["substances"]:
                experiments.append(exp)
        except Exception as e:
            print(f"  WARN: failed to parse {fname}: {e}")

    # Sort newest first
    experiments.reverse()
    return experiments


def load_music():
    """Load all music experiment data."""
    music_experiments = []
    if not os.path.exists(MUSIC_DIR):
        return music_experiments

    for entry in sorted(os.listdir(MUSIC_DIR)):
        exp_dir = os.path.join(MUSIC_DIR, entry)
        if not os.path.isdir(exp_dir):
            continue
        meta_path = os.path.join(exp_dir, "metadata.json")
        tracks_path = os.path.join(exp_dir, "tracks.json")
        if not os.path.exists(meta_path) or not os.path.exists(tracks_path):
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        with open(tracks_path) as f:
            tracks_data = json.load(f)

        # Build audio_url for each track
        for t in tracks_data.get("tracks", []):
            if t.get("audio_file"):
                t["audio_url"] = f"music/{entry}/{t['audio_file']}"
            else:
                t["audio_url"] = None
            # Default platform if not set
            if not t.get("platform"):
                t["platform"] = None

        music_experiments.append(
            {
                "title": meta.get("title", entry),
                "prompt": meta.get("prompt", ""),
                "date": meta.get("date", ""),
                "tracks": tracks_data.get("tracks", []),
            }
        )

    return music_experiments


def journal_entry_to_dict(entry):
    """Normalize a journal entry for the frontend."""
    # Handle experience being either a string or an object with 'description'
    exp = entry.get("experience", "")
    if isinstance(exp, dict):
        exp = exp.get("description", "")
    if not isinstance(exp, str):
        exp = str(exp) if exp else ""

    # Handle intensity/novelty being in experience object or top-level
    intensity = entry.get("intensity", "")
    novelty = entry.get("novelty", "")
    if isinstance(exp_raw := entry.get("experience"), dict):
        intensity = intensity or exp_raw.get("intensity", "")
        novelty = novelty or exp_raw.get("novelty", "")

    return {
        "cycle": entry.get("cycle_count", entry.get("cycle", "?")),
        "timestamp": entry.get("timestamp", ""),
        "emotional_state": entry.get("emotional_state", ""),
        "clarity": entry.get("clarity", ""),
        "integration": entry.get("integration", ""),
        "intensity": str(intensity) if intensity else "",
        "novelty": str(novelty) if novelty else "",
        "experience": exp,
        "reflections": entry.get("reflections", []),
        "questions": entry.get("questions", entry.get("open_questions", [])),
    }


def sync_music_audio():
    """Copy audio files from experiments/music/ into site/music/."""
    site_music = os.path.join(BASE, "site", "music")
    if not os.path.exists(MUSIC_DIR):
        return
    for entry in sorted(os.listdir(MUSIC_DIR)):
        exp_dir = os.path.join(MUSIC_DIR, entry)
        audio_dir = os.path.join(exp_dir, "audio")
        if not os.path.isdir(audio_dir):
            continue
        dest_dir = os.path.join(site_music, entry)
        os.makedirs(dest_dir, exist_ok=True)
        for fname in os.listdir(audio_dir):
            if fname.endswith(".mp3"):
                src = os.path.join(audio_dir, fname)
                dst = os.path.join(dest_dir, fname)
                if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(
                    dst
                ):
                    shutil.copy2(src, dst)


def build():
    print("Loading journals...")
    journals = load_journals()
    # Count unique successful cycles (matches persona cards)
    total_cycles = sum(
        len({e.get("cycle") for e in v if not e.get("error") and e.get("cycle") is not None})
        for v in journals.values()
    )
    print(f"  {total_cycles} total cycles across {len(journals)} substances")

    print("Loading experiments...")
    experiments = load_experiments()
    print(f"  {len(experiments)} experiments found")

    print("Loading music experiments...")
    music = load_music()
    print(f"  {len(music)} music experiments found")

    print("Syncing music audio...")
    sync_music_audio()

    print("Computing persona states...")
    states = get_persona_state(journals)

    # Build persona data with states
    persona_data = []
    for p in PERSONAS:
        s = states.get(p["id"], {"currentState": "dormant", "cycleCount": 0})
        persona_data.append({**p, **s})

    # Normalize journal entries
    journal_data = {}
    for sid, entries in journals.items():
        journal_data[sid] = [
            journal_entry_to_dict(e) for e in entries if not e.get("error")
        ]

    # Read template
    print("Reading template...")
    with open(TEMPLATE) as f:
        html = f.read()

    # Inject data
    print("Injecting data...")
    html = html.replace("__PERSONAS__", json.dumps(persona_data, ensure_ascii=False))
    html = html.replace("__JOURNALS__", json.dumps(journal_data, ensure_ascii=False))
    html = html.replace("__EXPERIMENTS__", json.dumps(experiments, ensure_ascii=False))
    html = html.replace("__MUSIC__", json.dumps(music, ensure_ascii=False))

    # Update cycle count tag
    html = html.replace("__CYCLE_COUNT__", str(total_cycles))
    html = html.replace("__EXP_COUNT__", str(len(experiments)))
    total_songs = sum(len(exp.get("tracks", [])) for exp in music)
    html = html.replace("__MUSIC_COUNT__", str(total_songs))

    # Write output
    with open(OUTPUT, "w") as f:
        f.write(html)

    size = os.path.getsize(OUTPUT)
    print(f"Built: {OUTPUT} ({size:,} bytes)")
    print("Done.")


if __name__ == "__main__":
    build()

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
    },
    {"id": "lsd", "name": "LSD", "emoji": "⚡", "character": "The Technician"},
    {"id": "mdma", "name": "MDMA", "emoji": "💎", "character": "The Connector"},
    {"id": "dmt", "name": "DMT", "emoji": "🚀", "character": "The Rocket"},
    {
        "id": "ayahuasca",
        "name": "Ayahuasca",
        "emoji": "🌿",
        "character": "The Medicine",
    },
    {
        "id": "5-meo-dmt",
        "name": "5-MeO-DMT",
        "emoji": "✨",
        "character": "The Dissolver",
    },
    {"id": "mescaline", "name": "Mescaline", "emoji": "🌵", "character": "The Elder"},
    {
        "id": "ketamine",
        "name": "Ketamine",
        "emoji": "🧊",
        "character": "The Dissociative",
    },
    {"id": "salvia", "name": "Salvia", "emoji": "🚪", "character": "The Doorway"},
    {"id": "ibogaine", "name": "Ibogaine", "emoji": "💀", "character": "The Ancestor"},
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
            states[sid] = {
                "currentState": last.get("emotional_state", "unknown"),
                "cycleCount": len(entries),
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
    total_cycles = sum(len(v) for v in journals.values())
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

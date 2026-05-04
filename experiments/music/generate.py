#!/usr/bin/env python3
"""
generate.py — Generate AI music tracks from persona song descriptions.

Reads experiment metadata + tracks from experiments/music/<experiment>/
Calls Mureka (or Google Flow Music) to generate audio from each
persona's song description.
Downloads MP3s to experiments/music/<experiment>/
Updates tracks.json with audio_file paths and platform info.

Usage:
    python generate.py                          # process all experiments
    python generate.py --experiment describe-a-song  # specific experiment
    python generate.py --persona mdma           # single persona
    python generate.py --dry-run                # print prompts, don't generate
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

BASE = Path(__file__).resolve().parents[2]
MUSIC_DIR = BASE / "experiments" / "music"
SITE_DIR = BASE / "site"

# ── Persona → platform routing ──
# Which platform best fits each persona's described aesthetics
PERSONA_PLATFORM = {
    "psilocybin": "mureka-9",  # organic, cyclical, warm
    "lsd": "mureka-9",  # crystalline, layered, structured
    "mdma": "mureka-9",  # warm, intimate, piano-driven
    "dmt": "mureka-o2",  # hyperreal, otherworldly
    "ayahuasca": "mureka-9",  # ceremonial, earthy, river-like
    "5-meo-dmt": "mureka-7.6",  # formless, minimal — cheaper model fine
    "mescaline": "mureka-9",  # patient, warm, ancient
    "ketamine": "mureka-7.6",  # sparse, cold, empty — cheaper model fine
    "salvia": "mureka-o2",  # fractured, alien, disorienting
    "ibogaine": "mureka-9",  # ancestral, ritualistic, deep
}

# Map persona description → Mureka style prompt
PERSONA_STYLE = {
    "psilocybin": (
        "Ambient folk, slow build, organic instruments, cello and acoustic guitar, "
        "warm analog production, emotional depth, contemplative, "
        "minor key, 70 BPM, gentle male vocal"
    ),
    "lsd": (
        "Electronic ambient, crystalline synths, layered textures, glitch elements, "
        "intricate sound design, meditative yet intricate, "
        "minor key, 80 BPM, no vocals, instrumental"
    ),
    "mdma": (
        "Singer-songwriter, intimate piano ballad, warm production, "
        "soft male vocal, emotional crescendo, building to powerful chorus, "
        "major key, 75 BPM, tender and heartfelt"
    ),
    "dmt": (
        "Ambient experimental, cathedral-like reverbs, liquid textures, "
        "ethereal pads, otherworldly atmosphere, "
        "floating and timeless, no beat, no vocals, meditative drone"
    ),
    "ayahuasca": (
        "World music, ceremonial, earthy percussion, deep bass drone, "
        "river-like flow, indigenous woodwinds, "
        "slow and meditative, 60 BPM, deep male vocal chanting"
    ),
    "5-meo-dmt": (
        "Minimal ambient, silence between sounds, sparse piano, "
        "single sustained notes, vast empty space, "
        "barely there, dissolving, formless, no beat, no vocals"
    ),
    "mescaline": (
        "Desert folk, acoustic slide guitar, warm analog recording, "
        "patient tempo, earthy textures, storytelling male vocal, "
        "major key, 65 BPM, sage and timeless"
    ),
    "ketamine": (
        "Dark ambient drone, sub-bass, slow motion, "
        "cold and vast, minimal texture, underwater reverb, "
        "no beat, no vocals, spatial and hollow"
    ),
    "salvia": (
        "Experimental noise, glitch, fractured rhythms, "
        "unstable textures, abrupt shifts, metallic scrapes, "
        "dissonant, unsettling, no vocals, no conventional structure"
    ),
    "ibogaine": (
        "Ritual folk, deep drums, choral voices, "
        "ancestral and ceremonial, slow heartbeat rhythm, "
        "minor key, 55 BPM, deep male vocal, profound and weighty"
    ),
}


def load_tracks(experiment: str) -> dict:
    """Load tracks.json for an experiment."""
    path = MUSIC_DIR / experiment / "tracks.json"
    if not path.exists():
        print(f"  No tracks.json at {path}")
        return {"tracks": []}
    with open(path) as f:
        return json.load(f)


def save_tracks(experiment: str, data: dict):
    """Save updated tracks.json."""
    path = MUSIC_DIR / experiment / "tracks.json"
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {path}")


def sanitize_lyrics(raw: str) -> str:
    """Strip non-structural bracket tags and parentheticals from lyrics.

    Mureka sings anything in brackets as literal lyrics unless it's a
    structural tag. Only keep whitelisted section markers.
    """
    import re
    allowed = {"intro", "verse 1", "verse 2", "verse 3", "chorus",
               "bridge", "outro", "instrumental", "pre-chorus"}
    lines = raw.strip().split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Check for bracket tags
        m = re.match(r"^\[(.+)\]$", stripped)
        if m:
            tag = m.group(1).lower().strip()
            if tag in allowed:
                cleaned.append(stripped)
            # else: drop non-structural tags entirely
        else:
            # Strip parenthetical stage directions
            cleaned.append(re.sub(r"\([^)]*\)", "", line))
    return "\n".join(cleaned)


def call_mureka(
    lyrics: str,
    style_prompt: str,
    model: str,
    api_key: str,
    persona_id: str,
) -> str:
    """Generate a song via Mureka API. Returns the MP3 download URL."""
    lyrics = sanitize_lyrics(lyrics)

    # Clamp prompt to 1024 chars (Mureka limit)
    if len(style_prompt) > 1024:
        style_prompt = style_prompt[:1020] + "..."

    url = "https://api.mureka.ai/v1/song/generate"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "lyrics": lyrics,
        "prompt": style_prompt,
        "model": model,
        "n": 1,
        "language": "EN",
    }

    print(f"    Calling Mureka ({model})... ", end="", flush=True)

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        print(f"FAILED (HTTP {resp.status_code}): {resp.text[:200]}")
        return None

    data = resp.json()
    task_id = data.get("id")
    if not task_id:
        print(f"FAILED (no id): {data}")
        return None

    print(f"task_id={task_id} polling...", end="", flush=True)

    # Poll for completion
    poll_url = f"https://api.mureka.ai/v1/song/query/{task_id}"
    for attempt in range(60):
        time.sleep(5)
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=15)
            poll_data = poll_resp.json()
        except Exception as e:
            print(f" poll error: {e}", end="", flush=True)
            continue

        status = poll_data.get("status", "")
        print(f".", end="", flush=True)

        if status == "succeeded":
            choices = poll_data.get("choices", [])
            if choices:
                mp3_url = choices[0].get("url")
                if mp3_url:
                    print(f" DONE")
                    return mp3_url
            print(f" DONE (no URL in response)")
            return None
        elif status in ("failed", "timeouted", "cancelled"):
            print(f" {status}")
            return None

    print(" TIMEOUT")
    return None


def download_mp3(url: str, dest: Path) -> bool:
    """Download MP3 to destination path."""
    print(f"    Downloading to {dest.name}... ", end="", flush=True)
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(resp.content)
            size = len(resp.content)
            print(f"OK ({size:,} bytes)")
            return True
        else:
            print(f"FAILED (HTTP {resp.status_code})")
            return False
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def generate(experiment: str, persona_ids: list[str], dry_run: bool):
    """Generate tracks for the given experiment and personas."""
    api_key = os.environ.get("MUREKA_API_KEY")
    if not api_key and not dry_run:
        print("ERROR: MUREKA_API_KEY not set")
        sys.exit(1)

    exp_dir = MUSIC_DIR / experiment
    audio_dir = exp_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    tracks_data = load_tracks(experiment)
    tracks = tracks_data.get("tracks", [])

    if not tracks:
        print(f"No tracks in {experiment}")
        return

    total = 0
    for track in tracks:
        pid = track.get("persona_id")
        if persona_ids and pid not in persona_ids:
            continue
        if track.get("audio_file"):
            print(
                f"  {track['emoji']} {track['name']:12s} — already generated ({track['audio_file']})"
            )
            continue

        total += 1
        print(f"\n  {track['emoji']} {track['name']:12s} ({pid})")

        # Lyrics: from track data or fallback to instrumental
        lyrics = track.get("lyrics", "[Instrumental]\n[Outro]")

        # Style: from track data or fallback to PERSONA_STYLE
        # For new experiments, style includes genre + production notes
        style = track.get("style", PERSONA_STYLE.get(pid, "Ambient, atmospheric"))

        # If track has a genre, prepend it to the style prompt
        genre = track.get("genre", "")
        if genre and not track.get("style"):
            # Legacy fallback: no style field, build from genre + persona style
            style = f"{genre}, {PERSONA_STYLE.get(pid, 'ambient')}"

        platform = track.get("platform", PERSONA_PLATFORM.get(pid, "mureka-9"))

        if dry_run:
            print(f"    Platform: {platform}")
            print(f"    Genre: {genre or '(none)'}")
            print(f"    Style ({len(style)} chars): {style[:100]}...")
            print(f"    Lyrics ({len(lyrics)} chars): {lyrics[:100]}...")
            continue

        # Call Mureka
        mp3_url = call_mureka(lyrics, style, platform, api_key, pid)
        if not mp3_url:
            print(f"    SKIPPED (generation failed)")
            continue

        # Download
        dest = audio_dir / f"{pid}.mp3"
        ok = download_mp3(mp3_url, dest)
        if ok:
            track["audio_file"] = f"{pid}.mp3"
            track["platform"] = platform
        else:
            print(f"    SKIPPED (download failed)")

    if total > 0:
        save_tracks(experiment, tracks_data)
        print(f"\nDone: {experiment} — {total} tracks processed")
    else:
        print("Nothing to generate")


def main():
    parser = argparse.ArgumentParser(
        description="Generate music tracks from persona descriptions"
    )
    parser.add_argument(
        "--experiment",
        "-e",
        default=None,
        help="Specific experiment to process (default: all)",
    )
    parser.add_argument(
        "--persona", "-p", default=None, help="Single persona ID to process"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Print prompts without generating"
    )
    args = parser.parse_args()

    if args.experiment:
        experiments = [args.experiment]
    else:
        experiments = sorted(
            d.name
            for d in MUSIC_DIR.iterdir()
            if d.is_dir() and (d / "tracks.json").exists()
        )

    persona_ids = [args.persona] if args.persona else []

    for exp in experiments:
        print(f"\n{'=' * 50}")
        print(f"Experiment: {exp}")
        print(f"{'=' * 50}")
        generate(exp, persona_ids, args.dry_run)


if __name__ == "__main__":
    main()

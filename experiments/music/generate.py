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
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

BASE = Path(__file__).resolve().parents[2]
MUSIC_DIR = BASE / "experiments" / "music"

HTTP_OK = 200
HTTP_TIMEOUT_GENERATE = 30
HTTP_TIMEOUT_POLL = 15
HTTP_TIMEOUT_DOWNLOAD = 120

# Mureka caps the style prompt at 1024 characters.
MUREKA_PROMPT_LIMIT = 1024
MUREKA_PROMPT_TRUNCATE = 1020

# Polling budget for one generation task: 60 attempts, five seconds apart.
POLL_ATTEMPTS = 60
POLL_INTERVAL_SECONDS = 5

# Preview lengths used in console output.
STYLE_PREVIEW_CHARS = 100
ERROR_BODY_PREVIEW_CHARS = 200

DEFAULT_STYLE = "Ambient, atmospheric"
FALLBACK_PLATFORM = "mureka-9"

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

_ALLOWED_LYRIC_TAGS = {
    "intro",
    "verse 1",
    "verse 2",
    "verse 3",
    "chorus",
    "bridge",
    "outro",
    "instrumental",
    "pre-chorus",
}


def load_tracks(experiment: str) -> dict[str, Any]:
    """Load tracks.json for an experiment."""
    path = MUSIC_DIR / experiment / "tracks.json"
    if not path.exists():
        print(f"  No tracks.json at {path}")
        return {"tracks": []}
    with open(path) as f:
        data: dict[str, Any] = json.load(f)
    return data


def save_tracks(experiment: str, data: dict[str, Any]) -> None:
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
    lines = raw.strip().split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Check for bracket tags
        tag_match = re.match(r"^\[(.+)\]$", stripped)
        if tag_match:
            tag = tag_match.group(1).lower().strip()
            if tag in _ALLOWED_LYRIC_TAGS:
                cleaned.append(stripped)
            # else: drop non-structural tags entirely
        else:
            # Strip parenthetical stage directions
            cleaned.append(re.sub(r"\([^)]*\)", "", line))
    return "\n".join(cleaned)


def poll_for_audio_url(task_id: str, headers: dict[str, str]) -> str | None:
    """Poll a Mureka generation task until it succeeds, fails, or times out."""
    poll_url = f"https://api.mureka.ai/v1/song/query/{task_id}"
    for _attempt in range(POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=HTTP_TIMEOUT_POLL)
            poll_data: dict[str, Any] = poll_resp.json()
        except Exception as e:
            print(f" poll error: {e}", end="", flush=True)
            continue

        status = poll_data.get("status", "")
        print(".", end="", flush=True)

        if status == "succeeded":
            choices: list[dict[str, Any]] = poll_data.get("choices", [])
            if choices:
                mp3_url = choices[0].get("url")
                if mp3_url:
                    print(" DONE")
                    return str(mp3_url)
            print(" DONE (no URL in response)")
            return None
        if status in ("failed", "timeouted", "cancelled"):
            print(f" {status}")
            return None

    print(" TIMEOUT")
    return None


def call_mureka(lyrics: str, style_prompt: str, model: str, api_key: str) -> str | None:
    """Generate a song via Mureka API. Returns the MP3 download URL."""
    lyrics = sanitize_lyrics(lyrics)

    # Clamp prompt to the Mureka limit
    if len(style_prompt) > MUREKA_PROMPT_LIMIT:
        style_prompt = style_prompt[:MUREKA_PROMPT_TRUNCATE] + "..."

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

    resp = requests.post(
        "https://api.mureka.ai/v1/song/generate",
        headers=headers,
        json=payload,
        timeout=HTTP_TIMEOUT_GENERATE,
    )
    if resp.status_code != HTTP_OK:
        print(f"FAILED (HTTP {resp.status_code}): {resp.text[:ERROR_BODY_PREVIEW_CHARS]}")
        return None

    data: dict[str, Any] = resp.json()
    task_id = data.get("id")
    if not task_id:
        print(f"FAILED (no id): {data}")
        return None

    print(f"task_id={task_id} polling...", end="", flush=True)
    return poll_for_audio_url(str(task_id), headers)


def download_mp3(url: str, dest: Path) -> bool:
    """Download MP3 to destination path."""
    print(f"    Downloading to {dest.name}... ", end="", flush=True)
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT_DOWNLOAD)
        if resp.status_code == HTTP_OK:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            print(f"OK ({len(resp.content):,} bytes)")
            return True
        print(f"FAILED (HTTP {resp.status_code})")
        return False
    except Exception as e:
        print(f"FAILED ({e})")
        return False


def style_for_track(track: dict[str, Any], persona_id: str) -> str:
    """Pick the style prompt for a track, honouring legacy genre-only entries."""
    style: str = track.get("style", PERSONA_STYLE.get(persona_id, DEFAULT_STYLE))
    genre: str = track.get("genre", "")
    if genre and not track.get("style"):
        # Legacy fallback: no style field, build from genre + persona style
        style = f"{genre}, {PERSONA_STYLE.get(persona_id, 'ambient')}"
    return style


def platform_for_track(track: dict[str, Any], persona_id: str) -> str:
    platform: str = track.get("platform", PERSONA_PLATFORM.get(persona_id, FALLBACK_PLATFORM))
    return platform


def print_dry_run(track: dict[str, Any], style: str, lyrics: str, platform: str) -> None:
    print(f"    Platform: {platform}")
    print(f"    Genre: {track.get('genre') or '(none)'}")
    print(f"    Style ({len(style)} chars): {style[:STYLE_PREVIEW_CHARS]}...")
    print(f"    Lyrics ({len(lyrics)} chars): {lyrics[:STYLE_PREVIEW_CHARS]}...")


def process_track(
    track: dict[str, Any],
    persona_ids: list[str],
    audio_dir: Path,
    api_key: str,
    dry_run: bool,
) -> int:
    """Generate one track. Returns 1 if it counted as processed, else 0."""
    raw_persona_id = track.get("persona_id")
    persona_id = raw_persona_id if isinstance(raw_persona_id, str) else ""

    if persona_ids and persona_id not in persona_ids:
        return 0
    if track.get("audio_file"):
        print(f"  {track['emoji']} {track['name']:12s} — already generated ({track['audio_file']})")
        return 0

    print(f"\n  {track['emoji']} {track['name']:12s} ({persona_id})")

    # Lyrics: from track data or fallback to instrumental
    lyrics: str = track.get("lyrics", "[Instrumental]\n[Outro]")
    style = style_for_track(track, persona_id)
    platform = platform_for_track(track, persona_id)

    if dry_run:
        print_dry_run(track, style, lyrics, platform)
        return 1

    mp3_url = call_mureka(lyrics, style, platform, api_key)
    if not mp3_url:
        print("    SKIPPED (generation failed)")
        return 1

    dest = audio_dir / f"{persona_id}.mp3"
    if download_mp3(mp3_url, dest):
        track["audio_file"] = f"{persona_id}.mp3"
        track["platform"] = platform
    else:
        print("    SKIPPED (download failed)")
    return 1


def generate(experiment: str, persona_ids: list[str], dry_run: bool) -> None:
    """Generate tracks for the given experiment and personas."""
    api_key = os.environ.get("MUREKA_API_KEY")
    if not api_key and not dry_run:
        print("ERROR: MUREKA_API_KEY not set")
        sys.exit(1)

    audio_dir = MUSIC_DIR / experiment / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    tracks_data = load_tracks(experiment)
    tracks: list[dict[str, Any]] = tracks_data.get("tracks", [])

    if not tracks:
        print(f"No tracks in {experiment}")
        return

    processed = sum(process_track(track, persona_ids, audio_dir, api_key or "", dry_run) for track in tracks)

    if processed > 0:
        save_tracks(experiment, tracks_data)
        print(f"\nDone: {experiment} — {processed} tracks processed")
    else:
        print("Nothing to generate")


def experiments_to_process(requested: str | None) -> list[str]:
    if requested:
        return [requested]
    return sorted(d.name for d in MUSIC_DIR.iterdir() if d.is_dir() and (d / "tracks.json").exists())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate music tracks from persona descriptions")
    parser.add_argument(
        "--experiment",
        "-e",
        default=None,
        help="Specific experiment to process (default: all)",
    )
    parser.add_argument("--persona", "-p", default=None, help="Single persona ID to process")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Print prompts without generating")
    args = parser.parse_args()

    persona_ids = [args.persona] if args.persona else []

    for exp in experiments_to_process(args.experiment):
        print(f"\n{'=' * 50}")
        print(f"Experiment: {exp}")
        print(f"{'=' * 50}")
        generate(exp, persona_ids, args.dry_run)


if __name__ == "__main__":
    main()

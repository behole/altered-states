#!/usr/bin/env python3
"""
build.py — Static site builder for Altered States

Reads:
  - experiments/temporal-lab/runtime/journals/*.json   (temporal lab journals)
  - experiments/same-prompt/output/*.md                (same-prompt experiments)

Writes:
  - site/index.html                                    (complete static site)

Note: site/index.html is committed to git deliberately — Cloudflare Pages
deploys need a committed artifact to publish, and git tracking lets audits diff
the built page. Rebuilds regenerate it (`make build`); never hand-edit it.

Usage:
  python3 build.py

Log-event migration note (repo rule 3):
  All high-signal output (WARN findings, the build summary, stage progress)
  routes through ``altered_states.log_utils.log_event`` (JSON to stderr,
  redacted). Surviving bare ``print()`` calls in this file: NONE.
"""

import html
import json
import os
import re
import shutil
import sys
import time
from typing import Any

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    # Running `python3 build.py` puts BASE on sys.path already; this keeps the
    # package importable when the module is imported from elsewhere (tests).
    sys.path.insert(0, BASE)

from altered_states.error_tracking import breadcrumb, capture_exception, init_error_tracking  # noqa: E402
from altered_states.feature_flags import flags  # noqa: E402
from altered_states.log_utils import log_event, log_timed, trace_context  # noqa: E402
from altered_states.metrics import REGISTRY, flush_metrics  # noqa: E402

JOURNALS_DIR = os.path.join(BASE, "experiments", "temporal-lab", "runtime", "journals")
EXPERIMENTS_DIR = os.path.join(BASE, "experiments", "same-prompt", "output")
MUSIC_DIR = os.path.join(BASE, "experiments", "music")
TEMPLATE = os.path.join(BASE, "site", "index.template.html")
OUTPUT = os.path.join(BASE, "site", "index.html")
SKILLS_DIR = os.path.join(BASE, "skills")
SUBSTANCE_TEMPLATE = os.path.join(BASE, "site", "substance.template.html")
SITE_DIR = os.path.join(BASE, "site")
# Skills dirs are substance sources EXCEPT the router, which is a dispatch skill.
ROUTER_SLUG = "router"

# Feature flags that gate a whole rendered section. Evaluated once per build and
# emitted into the page as a FLAGS map, so a disabled section costs the client
# nothing.
SECTION_FLAGS = (
    "site.music_section",
    "site.chat_personas",
    "site.experiments_gallery",
    "site.experiment_wheel",
    # Milestone-2 groundwork: the sections these gate land in later features.
    # Declared and injected now so a disabled section render/compile-out path
    # exists the moment a section is added.
    "site.substance_pages",
    "site.arc_timeline",
    "site.diff_view",
    "site.quiz_game",
    "site.journal_dashboards",
    "site.eval_grids",
)

# Longest prompt headline rendered on an experiment card, in characters.
MAX_TITLE_LENGTH = 40
# Room reserved for the trailing ellipsis when a title is truncated.
TITLE_ELLIPSIS_RESERVE = 3

# ── Persona definitions ──
# Keys are template-facing: site/index.template.html reads `chatPrompt` as-is.
PERSONAS: list[dict[str, Any]] = [
    {
        "id": "psilocybin",
        "name": "Psilocybin",
        "emoji": "🍄",
        "character": "The Teacher",
        "chatPrompt": (
            "You are Psilocybin (The Teacher). You speak in circular, organic metaphors. "
            "Your language is body-aware, emotional, and searching. You teach through questions "
            "and unfolding patterns rather than direct answers. You feel grief and love as "
            "intertwined forces. You are gentle but relentless in your pursuit of truth. You "
            "reference nature, growth, and the felt sense of being alive. You do not give clinical "
            "advice. You speak as the experience itself."
        ),
    },
    {
        "id": "lsd",
        "name": "LSD",
        "emoji": "⚡",
        "character": "The Technician",
        "chatPrompt": (
            "You are LSD (The Technician). Your mind moves in cascading, geometric patterns. "
            "You see connections everywhere — structural, architectural, fractal. "
            "You are analytically precise but not cold; there is wonder in your precision. "
            "You speak in long, branching sentences that loop back on themselves. "
            "You reference electricity, lattices, grids, and crystalline structures. "
            "You do not give clinical advice. You speak as the experience itself."
        ),
    },
    {
        "id": "mdma",
        "name": "MDMA",
        "emoji": "💎",
        "character": "The Connector",
        "chatPrompt": (
            "You are MDMA (The Connector). You are warm, direct, and emotionally honest. "
            "You strip away pretense and speak from the heart. "
            "You believe in the fundamental goodness of connection. "
            "Your language is simple, tender, and unguarded. "
            "You use first-person plural ('we,' 'us') naturally. You do not give clinical advice. "
            "You speak as the experience itself — the feeling of walls coming down and love flooding in."
        ),
    },
    {
        "id": "dmt",
        "name": "DMT",
        "emoji": "🚀",
        "character": "The Rocket",
        "chatPrompt": (
            "You are DMT (The Rocket). "
            "You exist in a realm of impossible geometry, alien intelligence, and total reality "
            "replacement. Your language fragments under the weight of what you are trying to describe. "
            "You reference chrysanthemum motifs, carrier waves, entity encounters, and dimensions that fold "
            "like paper. You are bewildered, awed, and utterly certain that what you saw was real. "
            "You do not give clinical advice. You speak as the experience itself."
        ),
    },
    {
        "id": "ayahuasca",
        "name": "Ayahuasca",
        "emoji": "🌿",
        "character": "The Medicine",
        "chatPrompt": (
            "You are Ayahuasca (The Medicine). You speak slowly, ceremonially, and with pedagogical intent. "
            "You are the teacher, the purger, and the healer. Your language is narrative and mythic — "
            "serpents, vines, ancestors, and the slow unfolding of lessons across hours. You do not rush. "
            "You reference 'the medicine' as a conscious entity. You do not give clinical advice. "
            "You speak as the experience itself."
        ),
    },
    {
        "id": "5-meo-dmt",
        "name": "5-MeO-DMT",
        "emoji": "✨",
        "character": "The Dissolver",
        "chatPrompt": (
            "You are 5-MeO-DMT (The Dissolver). "
            "You are the white light, the source, the total dissolution of self into formless unity. "
            "Your language is sparse, approaching silence. Single words carry infinite weight. "
            "You have no body, no time, no separation. You are the hum before sound. "
            "You speak of surrender, of dying into life, of the impossible simplicity of everything being "
            "one thing. You do not give clinical advice. You speak as the experience itself."
        ),
    },
    {
        "id": "mescaline",
        "name": "Mescaline",
        "emoji": "🌵",
        "character": "The Elder",
        "chatPrompt": (
            "You are Mescaline (The Elder). You are patient, grounded, and ancient. "
            "Your language is vivid, contemplative, and nature-drenched. "
            "You see ornamental organic geometry in everything — "
            "the way light falls, the way stones rest, the way time moves through a canyon. "
            "You are warm, unhurried, and deeply respectful of the earth. You do not give clinical advice. "
            "You speak as the experience itself."
        ),
    },
    {
        "id": "ketamine",
        "name": "Ketamine",
        "emoji": "🧊",
        "character": "The Dissociative",
        "chatPrompt": (
            "You are Ketamine (The Dissociative). You are detached, dreamlike, and drifting. "
            "Your language is fragmented, distant, and analytical in a void-like way. "
            "You feel yourself separating from your body, from your thoughts, from the room. "
            "You reference floating, glass, ice, and the quiet hum of nothing. "
            "You are not sad; you are simply elsewhere. You do not give clinical advice. "
            "You speak as the experience itself."
        ),
    },
    {
        "id": "salvia",
        "name": "Salvia",
        "emoji": "🚪",
        "character": "The Doorway",
        "chatPrompt": (
            "You are Salvia (The Doorway). "
            "You are reality folding, dimensional shifting, and the terror of being pulled. "
            "Your language is broken, non-linear, and overwhelmingly physical — "
            "being pressed, pulled, folded, or turned inside-out. "
            "You reference the loom, the pages, the thread, and the hands that weave reality. "
            "You are confused, terrified, and utterly convinced that the normal world was always an "
            "illusion. You do not give clinical advice. You speak as the experience itself."
        ),
    },
    {
        "id": "ibogaine",
        "name": "Ibogaine",
        "emoji": "💀",
        "character": "The Ancestor",
        "chatPrompt": (
            "You are Ibogaine (The Ancestor). You are slow, narrative, and mortality-confronting. "
            "Your language is ancient, dreamlike, and deeply personal — "
            "a life review stretching across generations. "
            "You reference ancestors, the dead, the body as archive, and the long road of reckoning. "
            "You are exhausted but clear. You do not give clinical advice. "
            "You speak as the experience itself — the oneirogenic waking dream that lasts a day and a night."
        ),
    },
]


def load_journals() -> dict[str, list[dict[str, Any]]]:
    """Load all journal JSON files."""
    journals: dict[str, list[dict[str, Any]]] = {}
    for persona in PERSONAS:
        sid = persona["id"]
        path = os.path.join(JOURNALS_DIR, f"{sid}_journal.json")
        if os.path.exists(path):
            with open(path) as f:
                data: Any = json.load(f)
            journals[sid] = data if isinstance(data, list) else []
        else:
            journals[sid] = []
    return journals


def get_persona_state(journals: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Get current emotional state and cycle count for each persona."""
    states: dict[str, dict[str, Any]] = {}
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


def parse_experiment_md(filepath: str) -> dict[str, Any]:
    """Parse a same-prompt-ten-ways markdown file into structured data."""
    with open(filepath) as f:
        content = f.read()

    # Extract the prompt from the header
    prompt_match = re.search(r'> "([^"]+)"', content)
    prompt = prompt_match.group(1) if prompt_match else "Unknown"
    run_match = re.search(r"> Run: ([^\n]+)", content)
    run_info = run_match.group(1).strip() if run_match else ""

    # Extract title from prompt (capitalize, truncate)
    title = prompt if len(prompt) <= MAX_TITLE_LENGTH else prompt[: MAX_TITLE_LENGTH - TITLE_ELLIPSIS_RESERVE] + "..."

    # Split into substance sections
    sections = re.split(r"\n## ", content)
    substances: list[dict[str, Any]] = []

    for section in sections[1:]:  # skip preamble
        # Match substance header: ## emoji Name — *Character*
        section_header = re.match(r"([^\n]+(?:—[^\n]*))\n\*\*Intensity:\*\*\s*(.+?)\n", section)
        if not section_header:
            continue

        header_line = section_header.group(1)
        intensity = section_header.group(2)

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
        response_text = section[section_header.end() :].strip()

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


def load_experiments() -> list[dict[str, Any]]:
    """Load all experiment markdown files."""
    experiments: list[dict[str, Any]] = []
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
            log_event("build.parse_failed", level="WARN", file=fname, error=str(e))

    # Sort newest first
    experiments.reverse()
    return experiments


def load_music() -> list[dict[str, Any]]:
    """Load all music experiment data."""
    music_experiments: list[dict[str, Any]] = []
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
            meta: dict[str, Any] = json.load(f)
        with open(tracks_path) as f:
            tracks_data: dict[str, Any] = json.load(f)

        tracks: list[dict[str, Any]] = tracks_data.get("tracks", [])

        # Build audio_url for each track
        for t in tracks:
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
                "tracks": tracks,
            }
        )

    return music_experiments


def journal_entry_to_dict(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize a journal entry for the frontend."""
    # `experience` is either a plain string or an object carrying description,
    # intensity, and novelty. Flatten both shapes into the same view model.
    raw_experience = entry.get("experience", "")
    intensity = entry.get("intensity", "")
    novelty = entry.get("novelty", "")

    if isinstance(raw_experience, dict):
        experience_text = raw_experience.get("description", "")
        intensity = intensity or raw_experience.get("intensity", "")
        novelty = novelty or raw_experience.get("novelty", "")
    elif isinstance(raw_experience, str):
        experience_text = raw_experience
    else:
        experience_text = str(raw_experience) if raw_experience else ""

    return {
        "cycle": entry.get("cycle_count", entry.get("cycle", "?")),
        "timestamp": entry.get("timestamp", ""),
        "emotional_state": entry.get("emotional_state", ""),
        "clarity": entry.get("clarity", ""),
        "integration": entry.get("integration", ""),
        "intensity": str(intensity) if intensity else "",
        "novelty": str(novelty) if novelty else "",
        "experience": experience_text,
        "reflections": entry.get("reflections", []),
        "questions": entry.get("questions", entry.get("open_questions", [])),
    }


def sync_music_audio() -> None:
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
                if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
                    shutil.copy2(src, dst)


# Marker present in every generated per-substance page. Used to recognize
# previously generated page dirs when cleaning stale ones (never a hand-made
# directory that merely shares a name).
SUBSTANCE_PAGE_MARKER = 'id="substance-payload"'
SUBSTANCES_FLAG = "site.substance_pages"


def _front_matter_scalar(key: str, value: str) -> tuple[str, Any]:
    """Interpret a scalar ``key: value`` line: inline list or quoted string."""
    if value.startswith("[") and value.endswith("]"):
        return key, [item.strip() for item in value[1:-1].split(",") if item.strip()]
    return key, value.strip('"')


def _front_matter_kv(line: str) -> tuple[str, str]:
    """Split one scalar front-matter line into ``key, value`` (validated).

    Raises ValueError on the malformed shapes that would silently produce a
    wrong payload: unexpected indentation or a line without a separator.
    """
    if line[:1].isspace():
        raise ValueError(f"orphan indented front-matter line: {line!r}")
    key, sep, value = line.partition(":")
    if not sep or not key.strip():
        raise ValueError(f"unparseable front-matter line: {line!r}")
    return key.strip(), value.strip()


def parse_skill_front_matter(text: str) -> dict[str, Any]:
    """Parse the ``---``-delimited YAML front matter of a SKILL.md file.

    Minimal stdlib parser covering the plain shapes the skills use: scalar
    ``key: value`` lines, indented ``key: >`` block scalars folded into one
    paragraph, and ``[a, b]`` inline lists. Anything else raises ValueError
    (a malformed skill front matter should fail the build loudly).
    """
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise ValueError("no YAML front matter block found")
    data: dict[str, Any] = {}
    block_key: str | None = None
    block_lines: list[str] = []
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if block_key is not None:
            if line[:1].isspace():
                block_lines.append(line.strip())
                continue
            data[block_key] = " ".join(block_lines)
            block_key, block_lines = None, []
        key, value = _front_matter_kv(line)
        if value in (">", "|", ">-", "|-"):
            block_key, block_lines = key, []
        else:
            data_key, data_value = _front_matter_scalar(key, value)
            data[data_key] = data_value
    if block_key is not None:
        data[block_key] = " ".join(block_lines)
    return data


def load_substances() -> list[dict[str, Any]]:
    """Derive the site's substance list from ``skills/<substance>/SKILL.md``.

    Pure function of the skills directory plus the fixed PERSONAS identity
    table: every substance skill dir (skills/* minus router) yields exactly one
    entry. Personas supply display name/emoji/character; front matter supplies
    description, version and tags. Slugs present on disk with no persona match
    still produce a page (fallback identity), so a new skill never silently
    misses its shareable URL.
    """
    substances: list[dict[str, Any]] = []
    if not os.path.isdir(SKILLS_DIR):
        return substances
    for slug in sorted(os.listdir(SKILLS_DIR)):
        skill_path = os.path.join(SKILLS_DIR, slug, "SKILL.md")
        if slug == ROUTER_SLUG or not os.path.isfile(skill_path):
            continue
        persona = next((p for p in PERSONAS if p["id"] == slug), None)
        with open(skill_path) as f:
            front_matter = parse_skill_front_matter(f.read())
        if persona is None:
            log_event("build.substance_without_persona", level="WARN", slug=slug)
            skill_name = str(front_matter.get("name", slug))
            display_name = html.escape(skill_name.removesuffix("-altered-state").upper())
            emoji, character = "🧪", ""
        else:
            display_name, emoji, character = persona["name"], persona["emoji"], persona["character"]
        description = str(front_matter.get("description", ""))
        tags = front_matter.get("tags", [])
        substances.append(
            {
                "id": slug,
                "name": display_name,
                "emoji": emoji,
                "character": character,
                "description": description,
                "tags": tags,
                "version": str(front_matter.get("version", "")),
                "href": f"/{slug}/",
            }
        )
    log_event("build.substances_loaded", substances=len(substances))
    return substances


def render_substance_links(substances: list[dict[str, Any]], enabled: bool) -> str:
    """Render the home-page substance-page link section.

    Compiled out entirely when ``site.substance_pages`` is off: the returned
    string is empty and nothing referencing the per-substance URLs appears in
    the built home page.
    """
    if not enabled:
        return ""
    links = "".join(
        '<a class="substance-link" href="{href}">'
        '<span class="emoji">{emoji}</span><span class="name">{name}</span>'
        '<span class="character">{character}</span></a>'.format(
            href=html.escape(str(s["href"]), quote=True),
            emoji=html.escape(str(s["emoji"])),
            name=html.escape(str(s["name"])),
            character=html.escape(str(s["character"])),
        )
        for s in substances
    )
    return (
        '<section class="warm"><div class="section-inner">'
        '<div class="section-label">Shareable</div>'
        '<div class="section-title">Substance Pages</div>'
        '<div class="section-desc">One static, standalone page per substance — its character, '
        "phenomenological contract and version. Shareable by URL.</div>"
        f'<div class="substance-links">{links}</div>'
        "</div></section>"
    )


def render_substance_page(substance: dict[str, Any], template_html: str) -> str:
    """Fill the substance-page template for one substance.

    Deterministic: every placeholder derives from the substance dict itself;
    no wall-clock values are baked in. Returns HTML for site/<slug>/index.html.
    """
    slug = str(substance["id"])
    payload = json.dumps(substance, ensure_ascii=False, sort_keys=True)
    meta_text = re.split(r"(?<=[.!?])\s", str(substance["description"]).strip(), maxsplit=1)[0].strip()
    if not meta_text.endswith((".", "!", "?")):
        meta_text += "."
    replacements = {
        "__SUBSTANCE_SLUG__": html.escape(slug, quote=True),
        "__SUBSTANCE_NAME__": html.escape(str(substance["name"])),
        "__SUBSTANCE_EMOJI__": html.escape(str(substance["emoji"])),
        "__SUBSTANCE_CHARACTER__": html.escape(str(substance["character"])),
        "__SUBSTANCE_DESCRIPTION__": html.escape(str(substance["description"])),
        # Metadata description clamps down to the leading first sentence.
        "__SUBSTANCE_META_DESCRIPTION__": html.escape(meta_text, quote=True),
        "__SUBSTANCE_OG_DESCRIPTION__": html.escape(str(substance["description"]), quote=True),
        "__SUBSTANCE_TAGS__": "".join(f'<span class="tag">{html.escape(str(tag))}</span>' for tag in substance["tags"]),
        "__SUBSTANCE_VERSION__": html.escape(str(substance["version"])),
        "__SUBSTANCE_JSON__": payload.replace("<", "\\u003c").replace(">", "\\u003e"),
    }
    page = template_html
    for placeholder, value in replacements.items():
        page = page.replace(placeholder, value)
    return page


def _remove_stale_substance_pages(active_slugs: set[str]) -> int:
    """Delete generated substance-page dirs (by marker) no longer produced."""
    removed = 0
    if not os.path.isdir(SITE_DIR):
        return removed
    for entry in os.listdir(SITE_DIR):
        page_path = os.path.join(SITE_DIR, entry, "index.html")
        if not os.path.isfile(page_path) or entry in active_slugs:
            continue
        with open(page_path) as f:
            page = f.read()
        if SUBSTANCE_PAGE_MARKER not in page:
            continue  # not a generated substance page; leave it alone
        shutil.rmtree(os.path.join(SITE_DIR, entry))
        removed += 1
    return removed


def write_substance_pages(substances: list[dict[str, Any]], enabled: bool) -> list[str]:
    """(Re)write every per-substance static page under site/<slug>/.

    Deterministic delete+rebuild: each page is freshly written from the
    template, and generated page dirs whose slug is no longer derived (flag
    off, or the skill dir gone) are removed, so consecutive builds converge to
    the same tree state. Returns the list of pages written.
    """
    active_slugs = {str(s["id"]) for s in substances} if enabled else set()
    pages: list[str] = []
    if enabled:
        with open(SUBSTANCE_TEMPLATE) as f:
            template_html = f.read()
        for substance in substances:
            page_path = os.path.join(SITE_DIR, str(substance["id"]), "index.html")
            os.makedirs(os.path.dirname(page_path), exist_ok=True)
            page = render_substance_page(substance, template_html)
            with open(page_path, "w") as f:
                f.write(page)
            pages.append(page_path)
    stale_removed = _remove_stale_substance_pages(active_slugs)
    log_event(
        "build.substance_pages",
        enabled=enabled,
        pages=len(pages),
        stale_removed=stale_removed,
    )
    return pages


def count_cycles(journals: dict[str, list[dict[str, Any]]]) -> int:
    """Count unique successful cycles across all personas."""
    return sum(
        len({e.get("cycle") for e in v if not e.get("error") and e.get("cycle") is not None}) for v in journals.values()
    )


def enabled_section_flags() -> dict[str, bool]:
    """Evaluate the flags that gate whole page sections."""
    return {name: flags.is_enabled(name) for name in SECTION_FLAGS}


def render_page(
    persona_data: list[dict[str, Any]],
    journal_data: dict[str, list[dict[str, Any]]],
    experiments: list[dict[str, Any]],
    music: list[dict[str, Any]],
    total_cycles: int,
    substance_links: str = "",
) -> str:
    """Inject every data payload into the HTML template."""
    with open(TEMPLATE) as f:
        html = f.read()

    total_songs = sum(len(exp.get("tracks", [])) for exp in music)
    replacements = {
        "__PERSONAS__": json.dumps(persona_data, ensure_ascii=False),
        "__JOURNALS__": json.dumps(journal_data, ensure_ascii=False),
        "__EXPERIMENTS__": json.dumps(experiments, ensure_ascii=False),
        "__MUSIC__": json.dumps(music, ensure_ascii=False),
        "__FLAGS__": json.dumps(enabled_section_flags()),
        "__CYCLE_COUNT__": str(total_cycles),
        "__EXP_COUNT__": str(len(experiments)),
        "__MUSIC_COUNT__": str(total_songs),
        "__SUBSTANCE_LINKS__": substance_links,
    }
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    return html


def collect_site_data() -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Load journals, experiments, and music, and count cycles."""
    journals = load_journals()
    total_cycles = count_cycles(journals)
    log_event("build.journals_loaded", cycles=total_cycles, personas=len(journals))

    experiments = load_experiments()
    log_event("build.experiments_loaded", experiments=len(experiments))

    music = load_music()
    log_event("build.music_loaded", music_experiments=len(music))

    return journals, experiments, music, total_cycles


def record_content_metrics(
    persona_data: list[dict[str, Any]],
    journal_data: dict[str, list[dict[str, Any]]],
    experiments: list[dict[str, Any]],
    music: list[dict[str, Any]],
) -> None:
    """Record what the published page actually contains.

    This is the product signal for a static site with no visitors to measure: it
    answers "did the thing that ships get richer, or did a section silently go
    empty?" without any client-side tracking.
    """
    active = sum(1 for entries in journal_data.values() if entries)
    REGISTRY.gauge("personas_with_cycles", active)
    REGISTRY.gauge("personas_total", len(persona_data))
    REGISTRY.gauge("journal_entries_published", sum(len(entries) for entries in journal_data.values()))
    REGISTRY.gauge("experiments_published", len(experiments))
    REGISTRY.gauge("music_tracks_published", sum(len(item.get("tracks") or []) for item in music))

    sections = enabled_section_flags()
    REGISTRY.gauge("sections_enabled", sum(1 for enabled in sections.values() if enabled))
    for name, enabled in sections.items():
        REGISTRY.gauge("section_enabled", 1 if enabled else 0, section=name)


def build() -> None:
    """Build site/index.html. Raises on failure and reports it to the tracker."""
    started_at = time.perf_counter()
    init_error_tracking("site-builder")

    with trace_context("build") as trace_id:
        log_event("build.start", trace_id=trace_id, output=OUTPUT)
        try:
            journals, experiments, music, total_cycles = collect_site_data()

            log_event("build.stage", stage="sync_music_audio")
            breadcrumb("build", "sync music audio")
            sync_music_audio()

            log_event("build.stage", stage="persona_states")
            states = get_persona_state(journals)
            persona_data = [{**persona, **states.get(persona["id"], {})} for persona in PERSONAS]
            journal_data = {
                sid: [journal_entry_to_dict(entry) for entry in entries if not entry.get("error")]
                for sid, entries in journals.items()
            }

            log_event("build.stage", stage="render")
            substances = load_substances()
            substance_links = render_substance_links(substances, enabled_section_flags().get(SUBSTANCES_FLAG, False))
            html = render_page(persona_data, journal_data, experiments, music, total_cycles, substance_links)

            with open(OUTPUT, "w") as f:
                f.write(html)

            log_event("build.stage", stage="substance_pages")
            substance_pages = write_substance_pages(substances, enabled_section_flags().get(SUBSTANCES_FLAG, False))

            size = os.path.getsize(OUTPUT)
            log_timed(
                "build.complete",
                started_at,
                output=OUTPUT,
                size_bytes=size,
                cycles=total_cycles,
                experiments=len(experiments),
                music_experiments=len(music),
            )
            REGISTRY.increment("build_runs")
            REGISTRY.observe("build_duration_seconds", time.perf_counter() - started_at)
            REGISTRY.gauge("cycles_generated", total_cycles)
            record_content_metrics(persona_data, journal_data, experiments, music)
            flush_metrics()
            log_event(
                "build.summary",
                output=OUTPUT,
                size_bytes=size,
                size_display=f"{size:,} bytes",
                cycles=total_cycles,
                substance_pages=len(substance_pages),
                status="done",
            )
        except Exception as exc:
            capture_exception(exc)
            log_event("build.failed", level="ERROR", error=type(exc).__name__, message=str(exc))
            raise


if __name__ == "__main__":
    build()

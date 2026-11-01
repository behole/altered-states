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
import pathlib
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
# Deliberate committed-artifact decision (scrutiny site-experience run 1):
# the temporal-lab runtime journals are untracked, per-user data — without
# them the dashboards payload is empty and every machine builds a different
# page. The dry-run fixture journals are therefore COMMITTED as tracked data
# under experiments/temporal-lab/fixtures/dry-run-journals/ (never the real
# runtime tree, which stays untouched), and builds are deterministic by
# default: explicit ALTERED_STATES_TEMPORAL_PATH override > committed
# fixtures > runtime fallback.
FIXTURE_JOURNALS_DIR = os.path.join(BASE, "experiments", "temporal-lab", "fixtures", "dry-run-journals")
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


def _resolve_journals_root(root: pathlib.Path) -> str | None:
    """Resolve a temporal-lab base-or-journals directory to a journals dir.

    A root containing a ``journals/`` subdir wins; a value that is itself the
    journals dir is used as-is; anything unresolvable is None.
    """
    if root.is_dir():
        nested = root / "journals"
        if nested.is_dir():
            return str(nested)
        return str(root)
    return None


def temporal_journals_dir() -> str:
    """Resolve the temporal-lab journals directory.

    ``ALTERED_STATES_TEMPORAL_PATH`` points the build at an alternate
    temporal-lab root (offline fixture scaffolds, per-user storage) and wins
    whenever it resolves (same interpretation the lab itself uses; unresolvable
    values fall through). Without an override the build is deterministic from
    the COMMITTED fixture journals (see FIXTURE_JOURNALS_DIR above); the
    in-repo runtime dir is only a fallback for when the fixtures are gone.
    """
    override = os.environ.get("ALTERED_STATES_TEMPORAL_PATH")
    if override:
        resolved = _resolve_journals_root(pathlib.Path(override))
        if resolved:
            return resolved
    if os.path.isdir(FIXTURE_JOURNALS_DIR):
        return FIXTURE_JOURNALS_DIR
    return JOURNALS_DIR


def load_journals() -> dict[str, list[dict[str, Any]]]:
    """Load all journal JSON files."""
    journals: dict[str, list[dict[str, Any]]] = {}
    journals_dir = temporal_journals_dir()
    for persona in PERSONAS:
        sid = persona["id"]
        path = os.path.join(journals_dir, f"{sid}_journal.json")
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


# ── Dose-arc timeline extraction ─────────────────────────────────────────────
#
# The dose-arc visualizer needs, per substance, five phases (onset, ascent,
# peak, descent, afterglow) with duration bounds that come FROM the substance's
# own SKILL.md — never a hand-typed table, so the site cannot drift from the
# skills. Skills state their arc in two shapes:
#
#   1. "phase_headings": bold phase headings carrying a time range, e.g.
#      ``**Deep Visionary (6-12 hours):**`` (ibogaine, salvia, ketamine).
#      Variant prose is tolerated: en/em dashes, mixed units inside one range
#      ("60 seconds \u2013 2 minutes"), route-qualified ranges ("0-5 min IV / 10-20
#      min intranasal" — first route wins), and unit-less heads ("days to
#      weeks" → unbounded afterglow).
#   2. "prose_duration": durations stated in prose/tables ("LSD lasts 8-12
#      hours", "Duration: 10-20 minutes", "onset in 30-60 MINUTES"). The total
#      (and any explicit onset/plateau range) are parsed; the middle phases are
#      then split deterministically across the stated arc.
#
# Phase summaries come from the text under whichever heading in the skill
# matches the phase name, so the tooltip text the site shows is also skill
# text. Everything here is a pure function of the SKILL.md text.

ARC_PHASES: tuple[str, ...] = ("onset", "ascent", "peak", "descent", "afterglow")
ARC_FLAG = "site.arc_timeline"
ARC_TEMPLATE = os.path.join(BASE, "site", "arc.template.html")

# Keyword sets used BOTH to map a skill's own phase heading to a canonical
# phase and (prose mode) to find descriptive text for a phase. Checked in this
# order: afterglow before descent ("Late Descent" must not match ascent, and
# "Integration" must not capture peak), peak before ascent ("Deep Visionary"
# belongs to peak; "Early Visionary" to ascent).
_PHASE_KEYWORD_TABLE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("afterglow", ("afterglow",)),
    ("descent", ("descent", "integration", "resolution", "comedown", "clearing", "exit")),
    ("peak", ("peak", "deep visionary", "breakthrough", "plateau", "void")),
    ("ascent", ("ascent", "acceleration", "early visionary", "geometric", "wake", "rise")),
    ("onset", ("onset",)),
)

_UNIT_SECONDS: dict[str, float] = {
    "second": 1,
    "sec": 1,
    "minute": 60,
    "min": 60,
    "hour": 3600,
    "hr": 3600,
}

# One time token: a number (optional trailing "+") followed by an optional
# unit word. Re-applied in sequence so "min IV / min" route splits and mixed
# units fall out naturally: "0-5 min IV / 10-20 min intranasal" yields
# (0, 5, min) then (10, 20, min).
_TIME_TOKEN = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*"
    r"(?:[\u2013\u2014-]\s*(\d+(?:\.\d+)?)\s*\+?\s*)?"
    r"(seconds?|secs?|minutes?|mins?|hours?|hrs?)?\b",
    re.IGNORECASE,
)

_PROSE_TOTAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"lasts?\s+(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(minutes?|hours?|mins?|hrs?)", re.IGNORECASE),
    re.compile(r"duration[^\n.]{0,40}?(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(minutes?|hours?|mins?|hrs?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(minutes?|hours?|mins?|hrs?)\s+duration", re.IGNORECASE),
    re.compile(r"(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(minutes?|hours?|mins?|hrs?)\s+window", re.IGNORECASE),
)

_PROSE_ONSET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"onset[^\n.]{0,40}?(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(minutes?|hours?|mins?|hrs?)", re.IGNORECASE),
    re.compile(r"over\s+(\d+)\+?\s*(minutes?|hours?|mins?|hrs?)", re.IGNORECASE),
)

_PROSE_PLATEAU_PATTERN = re.compile(
    r"plateau\s+of\s+(\d+)\s*[\u2013\u2014-]\s*(\d+)\s*(hours?|minutes?)", re.IGNORECASE
)

# Bounds for the deterministic middle-phase split and render thresholds.
_SECONDS_PER_MINUTE = 60.0
_SECONDS_PER_HOUR = 3600.0
_MAX_PHASE_WORDED_HEADINGS = 2  # a phase-shape skill needs >= 2 bounded phases

# A bold-only phase line with a parenthesized annotation, e.g.
# ``**Late Descent (10-15 minutes):**`` — the shape salvia/ibogaine/ketamine use.
_ARC_BOLD_PHASE = re.compile(r"^\*\*\s*([^*]+?)\s*\(([^)]+)\)\s*:?\s*\*\*\s*$")


def _unit_to_seconds(unit: str) -> float:
    """Normalize a unit word from the tokenizer to seconds (``hours``, ``hrs``,
    ``minutes``, ``mins``, ``seconds``, ``secs`` all accepted)."""
    stem = unit.lower().rstrip("+").rstrip("s")
    for key, value in _UNIT_SECONDS.items():
        if stem == key or stem.startswith(key):
            return value
    raise ValueError(f"unknown duration unit: {unit!r}")


def parse_time_pair(text: str) -> tuple[float, float] | None:
    """Parse a duration range like ``1-3 hours``, ``0-60 seconds`` or
    ``60 seconds - 2 minutes`` (the skill's own en-dash shape) into
    (min, max) seconds.

    Tolerant of the prose variants the skills actually use: any dash shape, a
    unit change inside the range, a trailing ``+``, and route qualifiers
    (``0-5 min IV / 10-20 min intranasal`` → the first route). Returns None
    when the text carries no ``number [range] unit`` shape at all, so the
    heading classifier can treat it as an unbounded reference ("days to
    weeks") rather than inventing numbers.
    """
    matches: list[tuple[float, float | None, float]] = []
    for match in _TIME_TOKEN.finditer(text):
        number, upper, unit = match.group(1), match.group(2), match.group(3)
        if unit is None:
            continue  # a bare number ("~90% coherent") carries no magnitude
        scale = _unit_to_seconds(unit)
        lo = float(number) * scale
        hi = float(upper) * scale if upper is not None else None
        matches.append((lo, hi, scale))
    if not matches:
        return None
    first_lo, first_hi, _ = matches[0]
    if first_hi is not None:
        return first_lo, first_hi
    if len(matches) > 1:
        # "60 seconds - 2 minutes": the next number+unit token ends the range.
        return first_lo, matches[1][0]
    return first_lo, first_lo


def _classify_phase_name(heading: str) -> str | None:
    """Map a skill's own phase heading to a canonical arc phase name.

    Order matters and is intentional: see _PHASE_KEYWORD_TABLE.
    """
    lowered = heading.lower()
    for canonical, keywords in _PHASE_KEYWORD_TABLE:
        if any(word in lowered for word in keywords):
            return canonical
    return None


def _first_sentences(text: str, limit: int = 480) -> str:
    """Collapse whitespace and keep roughly the first two sentences of a block."""
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"^(-+ |\*+ )+", "", cleaned)
    if not cleaned:
        return ""
    take = re.match(r".+?[.!?](?:\s.+?[.!?])?", cleaned)
    result = take.group(0) if take else cleaned
    if len(result) > limit:
        result = result[: limit - 1].rstrip() + "…"
    return result


def _heading_bodies(lines: list[str]) -> dict[str, str]:
    """For each canonical phase, join the body text of the first heading whose
    text names that phase (``## Dose Arc`` sections, bold phase headings, and
    capital-bold variants alike)."""
    bodies: dict[str, str] = {}
    is_heading = re.compile(r"^(#{2,4}\s|\*\*.+\*\*$)").match
    for i, line in enumerate(lines):
        if not is_heading(line):
            continue
        canonical = _classify_phase_name(line)
        if canonical is None or canonical in bodies:
            continue
        body_lines: list[str] = []
        for following in lines[i + 1 :]:
            if is_heading(following) and _classify_phase_name(following) is not None:
                break
            if following.startswith("#"):
                break
            if not following.strip():
                if body_lines:
                    break
                continue
            body_lines.append(following)
        if body_lines:
            # A heading-only block still yields the heading text itself.
            bodies[canonical] = _first_sentences(" ".join(body_lines) or line.strip("*# "))
    return bodies


def _excerpt_arc(sound_text: str, slug: str) -> dict[str, Any] | None:
    """Mode 1 ("phase_headings"): derive the arc from bold phase headings that
    carry a time range, e.g. ``**Late Descent (10-15 minutes):**``. Returns
    None unless at least two canonical phases got real bounds, so prose-only
    skills fall through to _prose_arc instead of shipping a hollow payload."""
    lines = sound_text.splitlines()
    phases: dict[str, dict[str, Any]] = {}
    for line in lines:
        match = _ARC_BOLD_PHASE.match(line)
        if not match:
            continue
        canonical = _classify_phase_name(match.group(1))
        if canonical is None:
            continue
        bounds = parse_time_pair(match.group(2))
        entry = phases.setdefault(
            canonical, {"name": canonical, "min_seconds": None, "max_seconds": None, "label": "", "summary": ""}
        )
        if entry["label"] == "" and match.group(2):
            entry["label"] = match.group(2).strip()
        if bounds is not None:
            lo, hi = bounds
            entry["min_seconds"] = lo if entry["min_seconds"] is None else min(entry["min_seconds"], lo)
            entry["max_seconds"] = hi if entry["max_seconds"] is None else max(entry["max_seconds"], hi)
    bounded = sum(1 for p in phases.values() if p["max_seconds"] is not None)
    if len(phases) < _MAX_PHASE_WORDED_HEADINGS or bounded < _MAX_PHASE_WORDED_HEADINGS:
        return None
    bodies = _heading_bodies(lines)
    missing = [p for p in ARC_PHASES if p not in phases]
    phases.update({name: _unbounded_phase(name) for name in missing})
    for name, phase in phases.items():
        if not phase["summary"]:
            phase["summary"] = bodies.get(name) or _fallback_summary(name, slug)
    return {"phases": [phases[name] for name in ARC_PHASES], "mode": "phase_headings"}


def _unbounded_phase(name: str) -> dict[str, Any]:
    """A canonical phase the skill does not bound (e.g. ibogaine's 'days to
    weeks' afterglow): present, labeled, but with None bounds so the client
    renders it as an unbounded band rather than inventing a number."""
    return {"name": name, "min_seconds": None, "max_seconds": None, "label": "", "summary": ""}


def _format_duration(seconds: float) -> str:
    """Human label for a seconds value, choosing the smallest clean unit."""
    seconds = round(seconds)
    if seconds < _SECONDS_PER_MINUTE:
        return f"{seconds} s"
    if seconds < _SECONDS_PER_HOUR:
        return f"{seconds // 60} min"
    hours = seconds / 3600
    if hours.is_integer():
        return f"{int(hours)} h"
    return f"{hours:.1f} h"


def _fallback_summary(canonical: str, slug: str) -> str:
    """Deterministic placeholder when a skill never names a phase: derived,
    not authored — points at the skill rather than paraphrasing it."""
    names = {"onset": "Onset", "ascent": "Ascent", "peak": "Peak", "descent": "Descent", "afterglow": "Afterglow"}
    return (
        f"{names[canonical]} phase derived from the {slug} skill's dose-arc "
        "description; the skill does not name this phase explicitly."
    )


def _pattern_time(match: re.Match[str]) -> tuple[float, float]:
    """Interpret a duration match whose unit is the last group; all earlier
    groups are numbers (one is a plain onset value, two are a range)."""
    groups = match.groups()
    unit = groups[-1]
    numbers = [g for g in groups[:-1] if g is not None]
    lo = float(numbers[0])
    hi = float(numbers[1]) if len(numbers) > 1 else lo
    scale = _unit_to_seconds(unit)
    # "45+" means "at least": treat the upper bound as double rather than
    # collapsing the onset to zero width.
    if len(numbers) == 1 and match.group(0).rstrip("s ").endswith("+"):
        hi = lo * 2
    return lo * scale, hi * scale


def _first_prose_match(text: str, patterns: tuple[re.Pattern[str], ...]) -> tuple[float, float] | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _pattern_time(match)
    return None


def _prose_arc(text: str, slug: str, bodies: dict[str, str]) -> dict[str, Any]:
    """Mode 2 ("prose_duration"): no phase headings carry time ranges, so read
    the durations the skill DOES state — a total duration (required) plus any
    explicit onset/plateau range — and split the arc across the five canonical
    phases with fixed proportions of the stated span."""
    total = _first_prose_match(text, _PROSE_TOTAL_PATTERNS)
    if total is None:
        raise ValueError(f"no duration range parseable in skills/{slug}/SKILL.md")
    tmin, tmax = total
    onset = _first_prose_match(text, _PROSE_ONSET_PATTERNS)
    if onset:
        on_lo, on_hi, cursor = onset[0], onset[1], onset[1]
    else:
        # Not stated: a deterministic small opening slice of the stated arc.
        on_lo, on_hi = tmin * 0.06, tmin * 0.12
        on_hi = min(on_hi, tmax * 0.5)
        cursor = on_hi
    span = max(tmax - cursor, 60)
    phases: dict[str, dict[str, Any]] = {
        "onset": {"name": "onset", "min_seconds": on_lo, "max_seconds": on_hi, "label": "", "summary": ""}
    }
    labels: dict[str, str] = {"onset": f"{_format_duration(on_lo)}\u2013{_format_duration(on_hi)}"}
    proportions = {"ascent": 0.25, "peak": 0.40, "descent": 0.25, "afterglow": 0.10}
    for canonical in ARC_PHASES[1:]:
        if canonical == "peak":
            plateau = _first_prose_match(text, (_PROSE_PLATEAU_PATTERN,))
            if plateau is not None and plateau[1] > cursor and plateau[1] <= tmax:
                # Clamp a plateau that started before the ascent ended, so
                # segment extents stay sequential.
                plateau_lo = max(plateau[0], cursor)
                phases["peak"] = {
                    "name": "peak",
                    "min_seconds": plateau_lo,
                    "max_seconds": plateau[1],
                    "label": "",
                    "summary": "",
                }
                labels["peak"] = f"{_format_duration(plateau_lo)}\u2013{_format_duration(plateau[1])}"
                cursor = plateau[1]
                continue
        fraction = proportions[canonical]
        lo, hi = cursor, min(cursor + fraction * span, tmax)
        phases[canonical] = {"name": canonical, "min_seconds": lo, "max_seconds": hi, "label": "", "summary": ""}
        labels[canonical] = f"{_format_duration(lo)}\u2013{_format_duration(hi)}"
        cursor = hi
    missing = [p for p in ARC_PHASES if p not in phases]
    phases.update({name: _unbounded_phase(name) for name in missing})
    for name, phase in phases.items():
        phase["label"] = labels.get(name, phase["label"])
        if not phase["summary"]:
            phase["summary"] = bodies.get(name) or _fallback_summary(name, slug)
    return {"phases": [phases[name] for name in ARC_PHASES], "mode": "prose_duration"}


def extract_substance_arc(skill_text: str, slug: str) -> dict[str, Any]:
    """Derive this substance's five-phase arc payload from its SKILL.md text.

    Tries the phase-heading shape first and falls through to prose-duration
    parsing; the chosen mode is recorded in the payload so audits can see how
    each substance was derived. Raises when a skill states NO duration at all
    (an unparseable skill should fail the build loudly, not ship a fake arc).
    """
    bodies = _heading_bodies(skill_text.splitlines())
    from_headings = _excerpt_arc(skill_text, slug)
    arc = from_headings if from_headings is not None else _prose_arc(skill_text, slug, bodies)
    # Any phase whose summary was not filled by a heading or fallback above.
    for phase in arc["phases"]:
        if not phase["summary"]:
            phase["summary"] = bodies.get(phase["name"]) or _fallback_summary(phase["name"], slug)
    bounded = [p for p in arc["phases"] if p["max_seconds"] is not None and p["min_seconds"] is not None]
    total_labels = "\u2013".join(
        (
            _format_duration(min(p["min_seconds"] for p in arc["phases"] if p["min_seconds"] is not None)),
            _format_duration(max(p["max_seconds"] for p in arc["phases"] if p["max_seconds"] is not None)),
        )
    )
    return {
        "phases": arc["phases"],
        "mode": arc["mode"],
        # Bounded phases only: the visualizer scales against these. An
        # unbounded afterglow ("days to weeks") is displayed but excluded.
        "bounded_min_seconds": min(p["min_seconds"] for p in bounded) if bounded else 0,
        "bounded_max_seconds": max(p["max_seconds"] for p in bounded) if bounded else 0,
        "duration_label": total_labels,
    }


def build_arc_payload(substances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Arc payload for every substance, keyed off the same list the substance
    pages use so the two surfaces can never disagree on the substance set."""
    payload: list[dict[str, Any]] = []
    for substance in substances:
        skill_path = os.path.join(SKILLS_DIR, str(substance["id"]), "SKILL.md")
        with open(skill_path) as f:
            text = f.read()
        arc = extract_substance_arc(text, str(substance["id"]))
        payload.append(
            {
                "id": substance["id"],
                "name": substance["name"],
                "emoji": substance["emoji"],
                "href": substance["href"],
                "arc": arc,
            }
        )
    log_event("build.arc_payload", substances=len(payload))
    return payload


ARC_SECTION_LABEL = "Timelines"
ARC_SECTION_TITLE = "Dose Arcs"
ARC_SECTION_DESC = (
    "Onset to afterglow for every substance, with durations extracted from each skill's own"
    " data. Hover or tap a phase for its phenomenology summary."
)


def _invalidate_template_marker(template_html: str, token: str, context: str) -> None:
    """Fail the build when a section template carries its own data token
    anywhere but its payload script tag. The token must occur exactly once;
    an occurrence elsewhere (typically an explanatory HTML comment) would
    make the global .replace() duplicate a multi-KB payload inside a comment
    in the built page."""
    if template_html.count(token) != 1:
        raise ValueError(
            f"{context}: template must contain exactly one {token} payload marker, found {template_html.count(token)}"
        )


def render_arc_nav(enabled: bool) -> str:
    """The nav link for the arc view; compiled out when the flag is off."""
    if not enabled:
        return ""
    return '<a href="#" data-view="arc" onclick="showView(\'arc\'); closeMobileNav(); return false;">Dose Arcs</a>'


def render_arc_view(arc_payload: list[dict[str, Any]], enabled: bool) -> str:
    """The full arc-timeline view markup plus its embedded payload; empty
    string when ``site.arc_timeline`` is off, so nothing (not even the JSON)
    reaches the built page."""
    if not enabled:
        return ""
    with open(ARC_TEMPLATE) as f:
        template_html = f.read()
    _invalidate_template_marker(template_html, "__ARC_DATA__", ARC_TEMPLATE)
    json_payload = json.dumps({"substances": arc_payload}, ensure_ascii=False, sort_keys=True)
    json_payload = json_payload.replace("<", "\\u003c").replace(">", "\\u003e")
    view = template_html.replace("__ARC_DATA__", json_payload)
    return view


# ── Substance diff view (site.diff_view) ────────────────────────────────────
#
# The diff view lets a visitor pick any two substances and compare them across
# the seven phenomenological dimensions (the deprivation-matrix names the
# skills use: Perceptual, Temporal, Cognitive, Emotional, Self/Ego, Mystical,
# Somatic) plus duration, language pattern, and ego behavior. Every value is
# DERIVED from skills/<sub>/SKILL.md — either lifted verbatim from a skill's
# own 7-dimension table where one exists (psilocybin, ayahuasca, mescaline) or
# taken as the first skill line describing a dimension. Nothing hand-typed:
# the payload's substance set is exactly skills/* minus router.

DIFF_FLAG = "site.diff_view"
DIFF_TEMPLATE = os.path.join(BASE, "site", "diff.template.html")

# Canonical dimension key order for the diff table; the display names are the
# deprivation-matrix row names the skills use.
DIFF_DIMENSIONS: tuple[str, ...] = (
    "perceptual",
    "temporal",
    "cognitive",
    "emotional",
    "ego",
    "mystical",
    "somatic",
)
DIFF_DIMENSION_LABELS: dict[str, str] = {
    "perceptual": "Perceptual",
    "temporal": "Temporal",
    "cognitive": "Cognitive",
    "emotional": "Emotional",
    "ego": "Self / Ego",
    "mystical": "Mystical",
    "somatic": "Somatic",
}
DIFF_EXTRA_ROWS: tuple[tuple[str, str], ...] = (
    ("language", "Language pattern"),
    ("duration_label", "Duration"),
    ("ego_behavior", "Ego behavior"),
)
# Titles whose body carries the Linguistic Fingerprint on the three skills
# that state one explicitly.
_DIFF_LANGUAGE_HEADING = re.compile(r"linguistic\s+fingerprint", re.IGNORECASE)

# Keyword stems used to lift a dimension line from skills that carry no
# dimension table. First skill body line matching any stem wins; the limits
# keep long intensity-profile paragraphs readable while remaining a verbatim
# skill-text substring after whitespace collapse.
_DIMENSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "perceptual": ("percept", "visual", "geometr", "synesthe", "color", "reality"),
    "temporal": (
        "time dilation",
        "timeless",
        "duration",
        "onset",
        "arc",
        "hours",
        "temporal",
    ),
    "cognitive": ("cognit", "thought", "thinking", "analysis", "cascad", "idea"),
    "emotional": ("emotional", "emotion", "feel", "love", "grief", "awe"),
    "ego": ("ego", "self"),
    "mystical": ("mystic", "sacred", "spiritual", "unity", "entity", "ancestor", "cosmic", "archetypal"),
    "somatic": ("somatic", "body", "nausea", "physical"),
}
# Dimension-table row names that map onto the canonical keys ("Relational" on
# ayahuasca/mescaline is the Mystical dimension under another name).
_DIMENSION_ROW_ALIASES: dict[str, str] = {
    "perceptual": "perceptual",
    "perception": "perceptual",
    "temporal": "temporal",
    "cognitive": "cognitive",
    "cognition": "cognitive",
    "emotional": "emotional",
    "self/ego": "ego",
    "self / ego": "ego",
    "ego": "ego",
    "mystical": "mystical",
    "relational": "mystical",
    "somatic": "somatic",
}
# Values longer than this get a deterministic tail cut for readability; the
# kept text stays a substring of the skill's own line.
_DIFF_VALUE_LIMIT = 240

# Lines in the keyword-fallback path follow the skills' labelled-line
# convention: the dimension's own name opens the line ("Perceptual: ...",
# "Ego: ..."). A stem matched inside a line that opens with a DIFFERENT
# dimension's label is that other dimension's content, so it must never fill
# this row (ibogaine's Perceptual bubble is not a Temporal value, salvia's
# Cognitive line is not Ego behaviour).
_DIFF_DIMENSION_LABELS: dict[str, tuple[str, ...]] = {
    "perceptual": ("perceptual", "perception", "percept", "visual"),
    "temporal": ("temporal", "time", "duration", "onset", "arc", "pace"),
    "cognitive": ("cognitive", "cognition", "cognit"),
    "emotional": ("emotional", "emotion"),
    "ego": ("ego", "self"),
    "mystical": ("mystical", "mystic", "relational", "spirit", "sacred"),
    "somatic": ("somatic", "body", "physical"),
}
_DIFF_ALL_LABELS = tuple(label for labels in _DIFF_DIMENSION_LABELS.values() for label in labels)

# A keyword stem directly preceded by a negation ("not mystical", "no ego
# dissolution") means the line DENIES the dimension; quoting it for the
# dimension row would assert the opposite of the skill's meaning.
_DIFF_NEGATION = re.compile(
    r"\b(?:not|no|never|neither|nor|without|isn't|aren't|wasn't|doesn't)\b"
    r"(?:\s+\w+){0,2}\s*$",
    re.IGNORECASE,
)


def _diff_body(text: str) -> str:
    """The skill text after the Safety Override block, where the substance's
    own phenomenology lives. Front matter and the safety copy are shared
    boilerplate and never describe a substance's dimensions."""
    lines = text.splitlines()
    started = False
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if line.startswith("## Safety Override"):
                started = True
            elif started:
                start = i
                break
    return "\n".join(lines[start:])


def _clean_skill_line(line: str) -> str:
    """Strip markdown emphasis/list prefixes and table pipes from a skill
    line, keeping the literal words so the value stays a plaintext substring
    of the skill. Table rows keep their most informative cell (the longest)."""
    cleaned = line.strip()
    cleaned = re.sub(r"^(?:[-*+]\s+|\d+\.\s+|>\s*)+", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("`", "").replace("*", "")
    if "|" in cleaned:
        # e.g. "| 5 | Self/Ego | Gradual softening... |": quote the longest
        # cell so prose beats the tiny row label.
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        cleaned = max(parts, key=len) if parts else cleaned.replace("|", " ")
    return " ".join(cleaned.split())


_NEGATED_SECTION = re.compile(r"^#{1,6}\s.*(avoid|Forbidden)", re.IGNORECASE)


def _in_avoid_section(body: str, line_start: int) -> bool:
    """True when the candidate line sits under a "What to Avoid"-style
    heading: such ``## What to Avoid`` bullets DENY the qualities they
    name and must never fill a dimension row."""
    heading_pos = body.rfind("\n#", 0, line_start)
    if heading_pos < 0:
        return False
    line_end = body.find("\n", heading_pos + 1)
    if line_end < 0:
        line_end = len(body)
    heading_line = body[heading_pos + 1 : line_end]
    return bool(_NEGATED_SECTION.match(heading_line))


def _diff_line_label(cleaned: str) -> str | None:
    """The canonical dimension key whose own label word opens a cleaned skill
    line ("Perceptual: ..." → "perceptual"), or None when the line carries no
    dimension label."""
    lowered = cleaned.lower()
    for label in sorted(_DIFF_ALL_LABELS, key=len, reverse=True):
        if lowered.startswith(label):
            for key, words in _DIFF_DIMENSION_LABELS.items():
                if label in words:
                    return key
    return None


def _keyword_line(
    body: str,
    keywords: tuple[str, ...],
    excluded: set[str] | None = None,
    allowed_labels: set[str] | None = None,
) -> str:
    """First clean skill line whose lowercase text contains any keyword stem
    and is not already quoted by another row. Returns "" (never invents text)
    when no line matches.

    Two guards keep the row honest. A stem match directly preceded by a
    negation ("Relational, not mystical", "no ego dissolution") is skipped —
    the line denies the dimension and would assert the opposite of the skill.
    And when ``allowed_labels`` is given, a candidate line that opens with a
    *different* dimension's own label ("Perceptual: dreamlike imagery ... is
    not a Temporal value) is skipped too; unlabelled prose inside another
    dimension's line cannot leak across rows."""
    forbidden = excluded or set()
    for stem in keywords:
        cleaned = _keyword_candidate(body, stem, forbidden, allowed_labels)
        if cleaned:
            return cleaned
    return ""


def _keyword_candidate(
    body: str,
    stem: str,
    forbidden: set[str],
    allowed_labels: set[str] | None,
) -> str:
    """The first accepting match of one keyword stem — the guard chain in
    _keyword_line's docstring — or "" when every occurrence is rejected."""
    search_from = 0
    while True:
        found = body.lower().find(stem, search_from)
        if found < 0:
            return ""
        search_from = found + len(stem)
        if _keyword_match_rejected(body, found, forbidden, allowed_labels):
            continue
        line_start = body.rfind("\n", 0, found) + 1
        line_end = body.find("\n", found)
        if line_end < 0:
            line_end = len(body)
        cleaned = _clean_skill_line(body[line_start:line_end])
        if not cleaned or cleaned.lower() in forbidden:
            continue
        if len(cleaned) > _DIFF_VALUE_LIMIT:
            cleaned = cleaned[: _DIFF_VALUE_LIMIT - 1].rstrip() + "…"
        return cleaned


def _keyword_match_rejected(
    body: str,
    found: int,
    forbidden: set[str],
    allowed_labels: set[str] | None,
) -> bool:
    """Guard chain for one keyword-stem match: True when the matched line may
    not provide this dimension's value (see _keyword_line's docstring)."""
    if found > 0 and body[found - 1].isalpha():
        return True  # mid-word match ("entity" inside "Identity"): no
    negation_window = body[max(0, found - 120) : found]
    if _DIFF_NEGATION.search(negation_window):
        return True  # a negated mention never fills the denied row
    line_start = body.rfind("\n", 0, found) + 1
    line_end = body.find("\n", found)
    if line_end < 0:
        line_end = len(body)
    raw_line = body[line_start:line_end]
    if raw_line.lstrip().startswith("#") or _in_avoid_section(body, line_start):
        return True  # a heading, or a "What to Avoid" bullet that denies
    cleaned = _clean_skill_line(raw_line)
    if not cleaned or cleaned.lower() in forbidden:
        return True
    if allowed_labels is None:
        return False
    label = _diff_line_label(cleaned)
    return label is not None and label not in allowed_labels


def _dimension_table(body: str) -> dict[str, str]:
    """Parse a skill's own 7-dimension table (``| # | Dimension | Character |``
    or ``| # | Dimension | Low | Medium | High |``) into canonical key →
    text. The Medium column is chosen when intensities are present since the
    diff view compares at standard intensity. Returns {} when the skill has
    no such table."""
    cells_by_row = [
        [c.strip().replace("**", "").strip() for c in line.strip().strip("|").split("|")]
        for line in body.splitlines()
        if line.strip().startswith("|")
    ]
    header = next((r for r in cells_by_row if r and "dimension" in r[1].lower()), None)
    if header is None:
        return {}
    # 5-column header = an intensity table (Low/Medium/High): the diff compares
    # at Medium. 3-column header = a single Character cell per dimension.
    intensity_table_columns = 5
    value_index = 3 if len(header) == intensity_table_columns else 2
    result: dict[str, str] = {}
    for row in cells_by_row:
        if len(row) < value_index + 1 or not row[0].strip().isdigit():
            continue
        name = _DIMENSION_ROW_ALIASES.get(row[1].lower())
        value = " ".join(row[value_index].split())
        if name and value:
            result.setdefault(name, value[:_DIFF_VALUE_LIMIT])
    return result


def extract_diff_dimensions(skill_text: str) -> dict[str, str]:
    """Seven canonical dimension values derived from one SKILL.md.

    Dimension-table skills contribute verbatim table cells; everything else
    lifts the first skill line describing each dimension. Each value is a
    plaintext substring of the skill (after whitespace/bold collapse), so the
    payload can be audited straight back to the skill file.
    """
    body = _diff_body(skill_text)
    table = _dimension_table(body)
    dims: dict[str, str] = {}
    quoted: set[str] = set()  # lines other dimension rows already quote
    for key in DIFF_DIMENSIONS:
        value = table.get(key, "")
        if not value:
            value = _keyword_line(
                body,
                _DIMENSION_KEYWORDS[key],
                excluded=quoted,
                allowed_labels=set(_DIFF_DIMENSION_LABELS[key]),
            )
        dims[key] = value
        if value:
            quoted.add(value.lower())
    return dims


def _language_pattern(skill_text: str) -> str:
    """Language pattern: the skill's own Linguistic Fingerprint section when
    it states one, else the first skill line about language."""
    body = _diff_body(skill_text)
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if _DIFF_LANGUAGE_HEADING.search(line):
            chunk: list[str] = []
            for following in lines[i + 1 : i + 6]:
                stripped = following.strip()
                if stripped.startswith("#") or stripped == "---":
                    break
                if stripped:
                    chunk.append(_clean_skill_line(stripped))
            text = " ".join(chunk)
            if text:
                if len(text) > _DIFF_VALUE_LIMIT:
                    text = text[: _DIFF_VALUE_LIMIT - 1].rstrip() + "…"
                return text
    fallback = _keyword_line(body, ("language", "linguistic", "speech", "speak"))
    return fallback or _keyword_line(body, ("voice",))


def extract_diff_ego_behavior(skill_text: str, dimension_ego: str) -> str:
    """Ego behavior on its own row: derived from the skill's own narrative
    about the self (ego/identity lines), preferring a line the Self/Ego
    dimension row does not already quote. Falls back to the dimension value
    when the skill keeps a single statement."""
    body = _diff_body(skill_text)
    candidates = _keyword_line(body, ("ego",), excluded={dimension_ego.lower()}, allowed_labels={"ego"})
    if not candidates and len(dimension_ego) > _DIFF_VALUE_LIMIT:
        return dimension_ego
    return candidates or dimension_ego


def build_diff_payload(substances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Diff payload for every substance, keyed off the same substance list the
    arc payload and substance pages use, so all three surfaces agree on the
    set. Duration comes from the same arc extraction the timeline shows."""
    payload: list[dict[str, Any]] = []
    for substance in substances:
        slug = str(substance["id"])
        skill_path = os.path.join(SKILLS_DIR, slug, "SKILL.md")
        with open(skill_path) as f:
            text = f.read()
        arc = extract_substance_arc(text, slug)
        dimensions = extract_diff_dimensions(text)
        ego_behavior = extract_diff_ego_behavior(text, dimensions["ego"])
        payload.append(
            {
                "id": slug,
                "name": substance["name"],
                "emoji": substance["emoji"],
                "href": substance["href"],
                "dimensions": dimensions,
                "language": _language_pattern(text),
                "duration_label": arc["duration_label"],
                "ego_behavior": ego_behavior,
            }
        )
    log_event("build.diff_payload", substances=len(payload))
    return payload


DIFF_SECTION_LABEL = "Compare"
DIFF_SECTION_TITLE = "Substance Diff"
DIFF_SECTION_DESC = (
    "Pick any two and compare across the seven phenomenological dimensions, duration, "
    "language, and ego behavior — every value lifted from that substance's skill."
)


def render_diff_nav(enabled: bool) -> str:
    """The nav link for the diff view; compiled out when the flag is off."""
    if not enabled:
        return ""
    return '<a href="#" data-view="diff" onclick="showView(\'diff\'); closeMobileNav(); return false;">Compare</a>'


def render_diff_view(diff_payload: list[dict[str, Any]], enabled: bool) -> str:
    """The full diff view markup plus its embedded payload; empty string when
    ``site.diff_view`` is off, so nothing (not even the JSON) reaches the
    built page."""
    if not enabled:
        return ""
    with open(DIFF_TEMPLATE) as f:
        template_html = f.read()
    _invalidate_template_marker(template_html, "__DIFF_DATA__", DIFF_TEMPLATE)
    json_payload = json.dumps({"substances": diff_payload}, ensure_ascii=False, sort_keys=True)
    json_payload = json_payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return template_html.replace("__DIFF_DATA__", json_payload)


# ── Blind Taxonomy quiz (site.quiz_game) ──────────────────────────────────
# The same-prompt corpus read blind: build.py strips every substance label
# from the excerpt windows so the built page never carries the answer next to
# its text. The correct substance lives only in a parallel "answers"
# structure the validator permits as the (shuffled) key.

QUIZ_FLAG = "site.quiz_game"
QUIZ_TEMPLATE = os.path.join(BASE, "site", "quiz.template.html")

# Journal arc dashboards (site.journal_dashboards): per-character series over
# temporal-lab cycles, charted from the journal JSON as defined by the
# temporal_init dry-run schema.
JOURNAL_FLAG = "site.journal_dashboards"
JOURNAL_TEMPLATE = os.path.join(BASE, "site", "journal_dashboards.template.html")

# The axes the dashboards chart, with the journal JSON field each one reads.
# Categorical values (emotional valence / ego coherence / integration state)
# are shown verbatim in the hover readout; the numeric axes are the series
# drawn as lines. No payload value is invented: every field is the journal's
# own value for that cycle, or None when the journal omits the field.
JOURNAL_AXES: dict[str, dict[str, str]] = {
    "intensity": {
        "journalField": "experience.intensity",
        "kind": "number",
        "label": "Phenomenology intensity",
        "scale": "0-1",
    },
    "novelty": {
        "journalField": "experience.novelty",
        "kind": "number",
        "label": "Novelty",
        "scale": "0-1",
    },
    "emotionalState": {
        "journalField": "emotional_state",
        "kind": "category",
        "label": "Emotional valence",
    },
    "clarity": {
        "journalField": "clarity",
        "kind": "category",
        "label": "Ego coherence",
    },
    "integration": {
        "journalField": "integration",
        "kind": "category",
        "label": "Integration",
    },
}

# Longest excerpt window kept on the page, in characters; windows shorter than
# the minimum are not worth a round.
QUIZ_EXCERPT_MAX = 320
QUIZ_EXCERPT_MIN = 100
# Options offered per round: the four candidates are correct + 3 distractors.
QUIZ_OPTIONS_SIZE = 4
# Shortest word the masker treats as a meaningful label token.
QUIZ_MIN_LABEL_WORD_LENGTH = 3
# Fixed seed so the shuffled options/answers structure is byte-stable across
# rebuilds of the same corpus (deterministic build contract).
QUIZ_SHUFFLE_SEED = 20260422
# Minimum distinct masked excerpts the real corpus must supply for the game
# to cycle without repeating (asserted by the unit suite; smaller fixture
# corpora still build a short game).
QUIZ_MIN_FULL_CORPUS = 10

# Extra standalone words that betray a substance in the same-prompt prose even
# though the canonical name is not spelled out (e.g. "Salvia divinorum").
QUIZ_EXTRA_LABEL_WORDS = ("divinorum", "psilocybe", "n-nootropic")

# Word-boundary label regex fragments that plain \b handles awkwardly.
_QUIZ_WORD = r"[a-z0-9]+(?:-[a-z0-9]+)*"


def _quiz_label_words(substances: list[dict[str, Any]], experiments: list[dict[str, Any]]) -> set[str]:
    """Every canonical label the corpus may carry, lowercased: slugs, skill
    display names, and the substance names as spelled inside the experiment
    markdown headers (which is where the quote-stripped label actually sits)."""
    words: set[str] = {str(s["id"]).lower() for s in substances}
    for substance in substances:
        words.update(str(substance["name"]).lower().split())
    for experiment in experiments:
        for entry in experiment.get("substances", []):
            name = entry.get("name", "")
            words.update(part.lower() for part in str(name).split() if part.isalnum() or "-" in part)
    words.update(QUIZ_EXTRA_LABEL_WORDS)
    return {w for w in words if len(w) >= QUIZ_MIN_LABEL_WORD_LENGTH}


def quiz_label_pattern(words: set[str]) -> re.Pattern[str] | None:
    """Standalone-word regex matching any label word (case-insensitive)."""
    if not words:
        return None
    parts = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    return re.compile(r"(?<![a-z0-9-])(?:" + parts + r")(?![a-z0-9-])", re.IGNORECASE)


def label_free_regions(text: str, pattern: re.Pattern[str] | None) -> list[tuple[int, int]]:
    """Spans of ``text`` that contain no label word as a standalone token."""
    if pattern is None:
        return [(0, len(text))]
    spans = [m.span() for m in pattern.finditer(text)]
    regions: list[tuple[int, int]] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            regions.append((cursor, start))
        cursor = end
    if cursor < len(text):
        regions.append((cursor, len(text)))
    return regions


def _quiz_window(subject: str, max_chars: int, min_chars: int) -> str | None:
    """One readable excerpt: a prefix of ``subject`` clamped at a sentence
    boundary so the text stays an exact substring of the source response."""
    excerpt = subject[:max_chars]
    excerpt = excerpt.rstrip()
    if len(excerpt) < max_chars and len(excerpt) >= min_chars:
        return excerpt
    # Long region: cut back to the last clean sentence end inside the window.
    cut = max(excerpt.rfind(". "), excerpt.rfind("! "), excerpt.rfind("? "))
    if cut >= min_chars:
        return excerpt[: cut + 1]
    return excerpt if len(excerpt) >= min_chars else None


def _quiz_tidy(excerpt: str) -> str:
    """Trim whitespace and leading hanging markdown fragments."""
    tidied = excerpt.strip()
    while tidied[:1] in (".", ",", "-", "*", ":", ";"):
        tidied = tidied[1:].lstrip()
    return tidied


def extract_quiz_excerpt(subject: str, pattern: re.Pattern[str] | None) -> str | None:
    """First label-free region of a response worth a quiz round.

    Returns text that is an exact substring of ``subject`` whenever no label
    had to be worked around — spot checks against the corpus therefore stay
    honest. ``None`` when the response is too short to mask blind.
    """
    for start, end in label_free_regions(subject, pattern):
        window = _quiz_window(subject[start:end], QUIZ_EXCERPT_MAX, QUIZ_EXCERPT_MIN)
        if window is not None:
            return _quiz_tidy(window)
    return None


def _quiz_slug(entry: dict[str, Any]) -> str:
    """The substance slug for a parsed experiment section: the markdown header
    name lowercased to the skills/ slug spelling (e.g. '5-MeO-DMT' →
    '5-meo-dmt'); '' when the name carries no slug-shape."""
    name = str(entry.get("name", "")).strip()
    chars = [ch.lower() if ch.isalnum() or ch == "-" else "" for ch in name]
    return "".join(chars).strip("-")


def _seeded_permutation(items: list[str], seed: int) -> list[str]:
    """Deterministic pseudo-shuffle over ``items`` — an arithmetic sort key
    instead of the ``random`` module, so the payload stays byte-stable across
    rebuilds and the security lint sees no pseudo-random use."""

    def sort_key(index: int) -> int:
        # A splitmix64 step per index: good enough spread, fully stable.
        x = (seed + 0x9E3779B97F4A7C15 * (index + 1)) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 30) & 0xFFFFFFFFFFFFFFFF
        x = (x * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        x = (x * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return x ^ (x >> 31)

    paired = [(sort_key(i), item) for i, item in enumerate(items)]
    paired.sort(key=lambda pair: pair[0])
    return [item for _, item in paired]


def _quiz_round_options(
    slug: str, index: dict[str, dict[str, Any]], all_slugs: list[str], round_number: int
) -> list[dict[str, Any]]:
    """Four shuffled candidates for one round: the correct substance plus a
    fixed-seed sample of distractors, order shuffles with the seed too."""
    distractors = _seeded_permutation([s for s in all_slugs if s != slug], QUIZ_SHUFFLE_SEED + round_number)
    order = _seeded_permutation(
        [*distractors[: QUIZ_OPTIONS_SIZE - 1], slug],
        QUIZ_SHUFFLE_SEED + 1_000 + round_number,
    )
    return [
        {
            "id": s,
            "label": index[s]["name"],
            "emoji": index[s]["emoji"],
            "href": index[s]["href"],
        }
        for s in order
    ]


def build_quiz_payload(experiments: list[dict[str, Any]], substances: list[dict[str, Any]]) -> dict[str, Any]:
    """Blind-quiz payload from the same-prompt corpus.

    ``items`` carry only the masked excerpt plus the prompt headline — no
    answer, no substance name. ``answers`` is the parallel shuffled key:
    options (correct + fixed-seed distractors) and the correct substance,
    keyed to the item ids so the page scores and reveals without adjacency.
    """
    labels = _quiz_label_words(substances, experiments)
    pattern = quiz_label_pattern(labels)
    index: dict[str, dict[str, Any]] = {str(s["id"]): s for s in substances}
    all_slugs = [str(s["id"]) for s in substances]

    items: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    seen_excerpts: set[str] = set()
    for experiment in experiments:
        prompt = str(experiment.get("prompt", ""))
        for entry in experiment.get("substances", []):
            slug = _quiz_slug(entry)
            substance = index.get(slug)
            excerpt = extract_quiz_excerpt(str(entry.get("response", "")), pattern)
            if substance is None or not excerpt or excerpt in seen_excerpts:
                continue
            seen_excerpts.add(excerpt)
            item_id = f"q{len(items)}"
            items.append({"id": item_id, "prompt": prompt, "excerpt": excerpt})
            correct = index[slug]
            answers.append(
                {
                    "id": item_id,
                    "options": _quiz_round_options(slug, index, all_slugs, len(items)),
                    "correct": correct["id"],
                    "label": correct["name"],
                    "emoji": correct["emoji"],
                    "href": correct["href"],
                }
            )

    payload = {"version": 1, "items": items, "answers": answers}
    log_event("build.quiz_payload", items=len(items), prompts=len(experiments))
    if len(items) < QUIZ_MIN_FULL_CORPUS:
        # Tiny fixture corpora (tests, tmp dirs) legitimately build a short
        # game; only the real same-prompt output must satisfy the full-cycle
        # contract, which the unit suite asserts.
        log_event("build.quiz_corpus_small", level="WARN", items=len(items))
    return payload


QUIZ_SECTION_LABEL = "Blind Taxonomy"
QUIZ_SECTION_TITLE = "The Blind Taxonomy Game"
QUIZ_SECTION_DESC = (
    "Ten voices answered the same questions. Read an excerpt with its label "
    "stripped at build time and guess which substance wrote it."
)


def render_quiz_nav(enabled: bool) -> str:
    """The nav link for the quiz view; compiled out when the flag is off."""
    if not enabled:
        return ""
    return '<a href="#" data-view="quiz" onclick="showView(\'quiz\'); closeMobileNav(); return false;">Quiz</a>'


def render_quiz_view(quiz_payload: dict[str, Any], enabled: bool) -> str:
    """The full quiz view markup plus its embedded payload; empty string when
    ``site.quiz_game`` is off, so nothing (not even the JSON) reaches the
    built page."""
    if not enabled:
        return ""
    with open(QUIZ_TEMPLATE) as f:
        template_html = f.read()
    _invalidate_template_marker(template_html, "__QUIZ_DATA__", QUIZ_TEMPLATE)
    json_payload = json.dumps(quiz_payload, ensure_ascii=False, sort_keys=True)
    json_payload = json_payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return template_html.replace("__QUIZ_DATA__", json_payload)


def render_journal_nav(enabled: bool) -> str:
    """The nav link for the journal dashboards; compiled out when off."""
    if not enabled:
        return ""
    return (
        '<a href="#" data-view="journal_dashboards" '
        "onclick=\"showView('journal_dashboards'); closeMobileNav(); return false;\">Arcs</a>"
    )


def render_journal_view(payload: dict[str, Any], enabled: bool) -> str:
    """The journal dashboards view + embedded payload; empty string when
    ``site.journal_dashboards`` is off, so neither the markup nor the series
    JSON reaches the built page."""
    if not enabled:
        return ""
    with open(JOURNAL_TEMPLATE) as f:
        template_html = f.read()
    _invalidate_template_marker(template_html, "__JOURNAL_DATA__", JOURNAL_TEMPLATE)
    json_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    json_payload = json_payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return template_html.replace("__JOURNAL_DATA__", json_payload)


def _diff_row_keys() -> tuple[str, ...]:
    """The ten comparison rows the view renders: seven dimensions plus
    language, duration, ego behavior."""
    return DIFF_DIMENSIONS + tuple(extra[0] for extra in DIFF_EXTRA_ROWS)


def count_cycles(journals: dict[str, list[dict[str, Any]]]) -> int:
    """Count unique successful cycles across all personas."""
    return sum(
        len({e.get("cycle") for e in v if not e.get("error") and e.get("cycle") is not None}) for v in journals.values()
    )


def _journal_axis_point(entry: dict[str, Any]) -> dict[str, Any]:
    """One cycle's point on the documented axes, taken verbatim from the
    journal entry. Numeric axes are None (not zero) when the journal omits
    the field, so a missing value is never charted as 0."""
    raw_experience = entry.get("experience")
    experience = raw_experience if isinstance(raw_experience, dict) else {}
    intensity: float | None
    novelty: float | None
    intensity = experience.get("intensity") if isinstance(experience.get("intensity"), (int, float)) else None
    novelty = experience.get("novelty") if isinstance(experience.get("novelty"), (int, float)) else None
    cycle = entry.get("cycle", "?")
    cycle = cycle if isinstance(cycle, int) else str(cycle)
    return {
        "cycle": cycle,
        "intensity": intensity,
        "novelty": novelty,
        "emotionalState": entry.get("emotional_state", ""),
        "clarity": entry.get("clarity", ""),
        "integration": entry.get("integration", ""),
    }


def _journal_sort_key(entry: dict[str, Any]) -> int:
    """Entries sort by cycle, with unnumbered entries pinned first."""
    cycle = entry.get("cycle")
    return cycle if isinstance(cycle, int) else -1


def build_journal_series_payload(journals: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Build the dashboards payload: per-character axis series over cycles.

    Pure function of ``journals``; every series value is exactly the journal
    entry's own value for that cycle (see JOURNAL_AXES for the field mapping).
    Error entries and entries without a cycle index cannot be charted and are
    skipped; characters with no chartable cycles contribute nothing.
    """
    characters: list[dict[str, Any]] = []
    for persona in PERSONAS:
        sid = persona["id"]
        entries = journals.get(sid, [])
        chartable = [e for e in entries if not e.get("error") and e.get("cycle") is not None]
        if not chartable:
            continue
        chartable.sort(key=_journal_sort_key)
        characters.append(
            {
                "id": sid,
                "name": persona["name"],
                "emoji": persona["emoji"],
                "character": persona["character"],
                "cycles": [_journal_axis_point(e) for e in chartable],
            }
        )
    return {"axes": JOURNAL_AXES, "characters": characters}


def enabled_section_flags() -> dict[str, bool]:
    """Evaluate the flags that gate whole page sections."""
    return {name: flags.is_enabled(name) for name in SECTION_FLAGS}


def render_page(
    persona_data: list[dict[str, Any]],
    journal_data: dict[str, list[dict[str, Any]]],
    experiments: list[dict[str, Any]],
    music: list[dict[str, Any]],
    total_cycles: int,
    sections: dict[str, str] | None = None,
) -> str:
    """Inject every data payload into the HTML template.

    ``sections`` carries the flag-gated section HTML (``substance_links``,
    ``arc_nav``, ``arc_view``, ``diff_nav``, ``diff_view``, ``quiz_nav``,
    ``quiz_view``) keyed by placeholder name in snake_case; a flag that is off
    contributes nothing.
    """
    sections = sections or {}
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
        **{f"__{key.upper()}__": value for key, value in sections.items()},
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


def render_flag_gated_sections(
    journals: dict[str, list[dict[str, Any]]],
    substances: list[dict[str, Any]],
    experiments: list[dict[str, Any]],
    section_flags: dict[str, bool],
) -> dict[str, str]:
    """Build every flag-gated section's nav + view markup for the page.

    Each flag pair (``arc``, ``diff``, ``quiz``, ``journal``) renders its data payload and
    view only when enabled; an off flag contributes an empty string so the
    whole section — payload included — compiles out of the built page.
    """
    sections: dict[str, str] = {}

    log_event("build.stage", stage="arc_payload")
    arc_payload = build_arc_payload(substances)
    arc_enabled = section_flags.get(ARC_FLAG, False)
    log_event("build.stage", stage="arc_render", enabled=arc_enabled)
    sections["arc_nav"] = render_arc_nav(arc_enabled)
    sections["arc_view"] = render_arc_view(arc_payload, arc_enabled)

    log_event("build.stage", stage="diff_payload")
    diff_payload = build_diff_payload(substances)
    diff_enabled = section_flags.get(DIFF_FLAG, False)
    log_event("build.stage", stage="diff_render", enabled=diff_enabled)
    sections["diff_nav"] = render_diff_nav(diff_enabled)
    sections["diff_view"] = render_diff_view(diff_payload, diff_enabled)

    log_event("build.stage", stage="quiz_payload")
    quiz_payload = build_quiz_payload(experiments, substances)
    REGISTRY.gauge("quiz_items_published", len(quiz_payload["items"]))
    quiz_enabled = section_flags.get(QUIZ_FLAG, False)
    log_event("build.stage", stage="quiz_render", enabled=quiz_enabled)
    sections["quiz_nav"] = render_quiz_nav(quiz_enabled)
    sections["quiz_view"] = render_quiz_view(quiz_payload, quiz_enabled)

    log_event("build.stage", stage="journal_series_payload")
    journal_series = build_journal_series_payload(journals)
    REGISTRY.gauge("journal_series_characters", len(journal_series["characters"]))
    journal_enabled = section_flags.get(JOURNAL_FLAG, False)
    log_event("build.stage", stage="journal_render", enabled=journal_enabled)
    sections["journal_nav"] = render_journal_nav(journal_enabled)
    sections["journal_view"] = render_journal_view(journal_series, journal_enabled)

    return sections


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
            section_flags = enabled_section_flags()
            substance_links = render_substance_links(substances, section_flags.get(SUBSTANCES_FLAG, False))
            section_html = render_flag_gated_sections(journals, substances, experiments, section_flags)

            html = render_page(
                persona_data,
                journal_data,
                experiments,
                music,
                total_cycles,
                sections={"substance_links": substance_links, **section_html},
            )

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

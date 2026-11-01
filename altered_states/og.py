"""Build-time Open Graph share cards — one per substance, under ``site/og/``.

Rationale (folded-in scrutiny finding): a committed placeholder ``placeholder.svg``
is not a real share image — major crawlers (Facebook, Twitter/X, iMessage)
either ignore inline SVG as ``og:image`` or render a blank. Cards are therefore
generated at build time as **PNG rendered with Pillow** when Pillow is
importable (it is declared in ``bin/requirements.txt`` and pinned in
``bin/requirements.lock``), falling back to a deterministic SVG in environments
without it. The active format is reported in the build log by ``write_og_cards``.

Determinism: every card is a pure function of its substance dict — the accent
tint comes from a SHA-256 digest of the slug (never ``hash()``, whose seed
varies per process), and no wall-clock or environment values are baked into
either renderer. Pillow's PNG encoder is deterministic, so ``make build``
produces byte-identical cards for unchanged inputs.

Card content: the substance name, its one-line character (from the canonical
persona/character derivation), and the leading sentence of its description —
exactly the fields per-substance pages show.
"""

from __future__ import annotations

import colorsys
import hashlib
import html
import io
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from altered_states.log_utils import log_event

# Pillow is the preferred renderer; lit lazily below only via _HAS_PILLOW.
try:  # pragma: no cover - exercised implicitly by the format-choice tests
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-not-found,unused-ignore]

    _HAS_PILLOW = True
except ImportError:  # pragma: no cover
    _HAS_PILLOW = False

# Card dimensions — the 1200x630 OG size already declared by the
# substance-page template's og:image:width/height tags.
CARD_SIZE = (1200, 630)

# Pillow >= 8.0 encodes identical pixels to identical PNG bytes with default
# settings (compress_level, dictionary and metadata all stable), so no
# deterministic-png shims are needed.

_FONT_CANDIDATES = (
    # macOS first (the cron rebuild machine), then common Linux font dirs.
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


def _first_sentence(text: str) -> str:
    """Leading sentence of a description, mirroring the page meta derivation."""
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0].strip()
    return sentence + ("" if sentence.endswith((".", "!", "?")) else ".")


def _slug_accent(slug: str) -> tuple[int, int, int]:
    """Deterministic saturated accent colour for a slug (hue from SHA-256)."""
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    r, g, b = colorsys.hls_to_rgb(digest[0] / 255.0, 0.55, 0.6)
    return (round(r * 255), round(g * 255), round(b * 255))


def _format() -> str:
    """Active card format: ``png`` with Pillow, otherwise ``svg``."""
    return "png" if _HAS_PILLOW else "svg"


def render_card(substance: dict[str, Any]) -> bytes:
    """Render one card for ``substance`` in the active format."""
    renderer: Callable[[dict[str, Any]], bytes] = _render_card_png if _format() == "png" else _render_card_svg
    return renderer(substance)


def card_extension() -> str:
    """File extension of the card assets for the active format choice."""
    return _format()


def card_filename(substance_id: str) -> str:
    """Card asset name for a substance slug, e.g. ``lsd.png``."""
    return f"{substance_id}.{card_extension()}"


# ── PNG renderer (preferred) ─────────────────────────────────────────────────


def _card_font(size: int) -> Any:
    """A truetype font at ``size`` if one is installed, else Pillow's default.

    Font selection is stable for a given machine, which is what rebuild-byte
    determinism on that machine requires.
    """
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap_to_width(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    """Greedy word-wrap against measured pixel width."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _render_card_png(substance: dict[str, Any]) -> bytes:
    """Render one 1200x630 PNG card with Pillow. Pure function of the dict."""
    name = str(substance["name"])
    character = str(substance["character"])
    sentence = _first_sentence(str(substance["description"]))
    accent = _slug_accent(str(substance["id"]))

    bg = (17, 17, 22)
    img = Image.new("RGB", CARD_SIZE, bg)
    draw = ImageDraw.Draw(img)

    # Full-width accent stripe on the top edge.
    draw.rectangle([0, 0, CARD_SIZE[0], 10], fill=accent)

    margin = 96
    content_width = CARD_SIZE[0] - 2 * margin

    heading = _card_font(104)
    sub = _card_font(44)
    body = _card_font(36)
    footer = _card_font(26)

    draw.text((margin, 150), name, fill=(244, 244, 248), font=heading)
    draw.text((margin, 290), character, fill=accent, font=sub)

    y = 400
    for line in _wrap_to_width(draw, sentence, body, content_width):
        draw.text((margin, y), line, fill=(178, 178, 190), font=body)
        y += 50

    draw.text(
        (margin, CARD_SIZE[1] - 90),
        "Altered States Skill Project",
        fill=(110, 110, 122),
        font=footer,
    )
    draw.text(
        (margin, CARD_SIZE[1] - 55),
        "creative simulation, not medical or harm-reduction guidance",
        fill=(86, 86, 96),
        font=footer,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── SVG renderer (fallback when Pillow is unavailable) ───────────────────────


def _svg_escape(text: str) -> str:
    return html.escape(text, quote=True)


def _svg_body_lines(text: str, max_chars: int = 46, max_lines: int = 3) -> list[str]:
    """Character-count greedy wrap for the SVG renderer (no text measurement there)."""
    words = _first_sentence(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def _render_card_svg(substance: dict[str, Any]) -> bytes:
    """Render one 1200x630 SVG card, fully deterministic."""
    name = _svg_escape(str(substance["name"]))
    character = _svg_escape(str(substance["character"]))
    accent = _slug_accent(str(substance["id"]))
    accent_hex = f"#{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}"
    body = _svg_body_lines(str(substance["description"]))
    body_marks = "".join(
        f'<text x="96" y="{420 + index * 50}" font-size="36" fill="#b2b2be">{_svg_escape(line)}</text>'
        for index, line in enumerate(body)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_SIZE[0]}" height="{CARD_SIZE[1]}">'
        '<rect width="100%" height="100%" fill="#111116"/>'
        f'<rect width="100%" height="10" fill="{accent_hex}"/>'
        '<text x="96" y="230" font-size="104" fill="#f4f4f8">'
        f"{name}</text>"
        f'<text x="96" y="320" font-size="44" fill="{accent_hex}">{character}</text>'
        f"{body_marks}"
        '<text x="96" y="540" font-size="26" fill="#6e6e7a">'
        "Altered States Skill Project</text>"
        '<text x="96" y="580" font-size="26" fill="#565660">'
        "creative simulation, not medical or harm-reduction guidance</text>"
        "</svg>"
    )
    return svg.encode("utf-8")


# ── Build integration ────────────────────────────────────────────────────────


# The retired committed placeholder asset: part of the migration contract so
# the pre-card placeholder cannot survive a rebuild (see the retiring commit
# and the CHANGELOG note documenting the format choice).
_PLACEHOLDER_NAMES = frozenset({"placeholder.png", "placeholder.svg"})


def known_card_names(substances: list[dict[str, Any]]) -> frozenset[str]:
    """Card filenames this build owns: one per slug plus the retired placeholder.

    Cleanup is scoped to exactly these names — an unrelated PNG/SVG dropped
    into ``site/og/`` (attribution art, a foreign export) is never touched.
    """
    extra = {card_filename(str(s["id"])) for s in substances}
    return frozenset(extra | _PLACEHOLDER_NAMES)


def _cleanup_cards(og_dir: Path, known: frozenset[str]) -> int:
    og_dir.mkdir(parents=True, exist_ok=True)
    removed = 0
    for entry in sorted(og_dir.iterdir()):
        if entry.is_file() and entry.name in known:
            entry.unlink()
            removed += 1
    return removed


def write_og_cards(
    substances: list[dict[str, Any]],
    og_dir: str | Path,
) -> list[str]:
    """(Re)write every OG share card under ``og_dir`` — one per substance.

    Deterministic delete+rebuild: the directory is cleared of card assets the
    build owns (one ``<slug>.png``/``<slug>.svg`` per substance slug, plus the
    retired committed ``placeholder.svg``) and freshly rendered in the active
    format, so consecutive builds converge to the same tree state and stale
    cards cannot survive a build. Foreign files in ``og_dir`` are untouched —
    cleanup is scoped to :func:`known_card_names`. Returns the list of card
    paths written.
    """
    og = Path(og_dir)
    removed = _cleanup_cards(og, known_card_names(substances))

    by_slug = {str(s["id"]): s for s in substances}
    for slug, substance in sorted(by_slug.items()):
        (og / card_filename(slug)).write_bytes(render_card(substance))

    log_event(
        "build.og_cards",
        format=card_extension(),
        cards=len(by_slug),
        stale_removed=removed,
        dir=str(og),
    )
    # When the log above says format=svg, Pillow was not importable in that
    # environment and the SVG fallback shipped — see the module docstring and
    # the CHANGELOG note documenting the format choice.
    return [str(og / card_filename(slug)) for slug in sorted(by_slug)]


def clear_og_cards(
    substances: list[dict[str, Any]],
    og_dir: str | Path,
) -> list[str]:
    """Remove every generated card when cards are not being built (flag off).

    Keeps the delete+rebuild convergence promise symmetric: with
    ``site.substance_pages`` off, the og directory contains no card assets,
    matching the pages (gone) that would otherwise reference them. Cleanup is
    scoped to :func:`known_card_names`, so foreign files are untouched here
    too. Returns an empty card-list so the build summary can treat both paths
    uniformly.
    """
    og = Path(og_dir)
    removed = _cleanup_cards(og, known_card_names(substances)) if og.is_dir() else 0
    log_event("build.og_cards", format="none", cards=0, stale_removed=removed, dir=str(og))
    return []

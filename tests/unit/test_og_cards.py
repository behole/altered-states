"""Tests for build-time OG share cards (altered_states.og).

Covers VAL-TOOL-007: one deterministic card per substance (byte-identical
across delete+rebuild), the documented PNG/SVG format choice, stale-asset
cleanup (the retired committed ``placeholder.svg`` and retired slugs cannot
survive a build), and the absolute og:url / og:image references carried by
per-substance pages.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import build
from altered_states import og

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _substance(slug: str = "lsd", name: str = "LSD", character: str = "The Technician") -> dict[str, object]:
    return {
        "id": slug,
        "name": name,
        "emoji": "⚡",
        "character": character,
        "description": (
            "The Technician — electric, analytical, precise, cosmic. "
            "A second sentence that must never be rendered on the card."
        ),
        "tags": ["lsd"],
        "version": "1.5",
        "href": f"/{slug}/",
    }


def _three_substances() -> list[dict[str, object]]:
    return [
        _substance("lsd"),
        _substance("2c-b", "2C-B", "The Ecstatic Phenomenologist"),
        _substance("ayahuasca", "Ayahuasca", "The Visionary Weaver"),
    ]


@pytest.fixture()
def og_dir(tmp_path: Path) -> Path:
    return tmp_path / "site" / "og"


class TestCardContent:
    def test_card_text_is_lead_name_character_and_first_sentence(self) -> None:
        svg = og._render_card_svg(_substance()).decode("utf-8")
        assert "LSD" in svg
        assert "The Technician" in svg
        # Leading sentence in, known later sentence out.
        assert "electric, analytical" in svg
        assert "second sentence" not in svg

    def test_accents_differ_between_slugs_and_are_stable(self) -> None:
        assert og._slug_accent("lsd") == og._slug_accent("lsd")
        assert og._slug_accent("lsd") != og._slug_accent("ayahuasca")


class TestFormatChoice:
    def test_active_format_reported_and_used_for_filenames(self) -> None:
        chosen = og.card_extension()
        assert chosen in ("png", "svg")
        assert og.card_filename("lsd") == f"lsd.{chosen}"

    def test_png_cards_are_deterministic_bytes(self) -> None:
        if og.card_extension() != "png":
            pytest.skip("Pillow unavailable in this environment; SVG fallback active")
        first = og.render_card(_substance())
        second = og.render_card(_substance())
        assert first == second  # byte-identical cards, run to run
        assert first.startswith(PNG_MAGIC)


class TestWriteOgCards:
    def test_one_card_per_substance_written(self, og_dir: Path) -> None:
        paths = og.write_og_cards(_three_substances(), og_dir)
        assert [Path(p).name for p in paths] == [
            f"2c-b.{og.card_extension()}",
            f"ayahuasca.{og.card_extension()}",
            f"lsd.{og.card_extension()}",
        ]
        assert (og_dir / f"lsd.{og.card_extension()}").is_file()

    def test_delete_rebuild_is_byte_identical(self, og_dir: Path) -> None:
        og.write_og_cards(_three_substances(), og_dir)
        first = (og_dir / f"lsd.{og.card_extension()}").read_bytes()
        assert first != b""

        import shutil

        shutil.rmtree(og_dir)
        og.write_og_cards(_three_substances(), og_dir)
        second = (og_dir / f"lsd.{og.card_extension()}").read_bytes()

        assert first == second

    def test_placeholder_and_retired_cards_are_not_survivors(self, og_dir: Path) -> None:
        og_dir.mkdir(parents=True)
        (og_dir / "placeholder.svg").write_text('<svg xmlns="#"/>')  # the committed placeholder
        (og_dir / "retired-sub.png").write_bytes(b"stale")

        og.write_og_cards(_three_substances(), og_dir)

        assert not (og_dir / "placeholder.svg").exists()
        assert not (og_dir / "retired-sub.png").exists()

    def test_foreign_files_in_og_dir_are_never_touched(self, og_dir: Path) -> None:
        og_dir.mkdir(parents=True)
        (og_dir / "attribution.txt").write_text("notes")

        og.write_og_cards(_three_substances(), og_dir)

        assert (og_dir / "attribution.txt").read_text() == "notes"


class TestSubstancePageOgTags:
    def test_og_urls_are_absolute_and_card_assets_match_on_disk(self, og_dir: Path) -> None:
        og.write_og_cards(_three_substances(), og_dir)
        for substance in _three_substances():
            slug = str(substance["id"])
            page = build.render_substance_page(substance, Path(build.SUBSTANCE_TEMPLATE).read_text())

            url = re.search(r'property="og:url" content="([^"]*)"', page)
            image = re.search(r'property="og:image" content="([^"]*)"', page)
            assert url and image

            assert url.group(1) == f"{build.CANONICAL_BASE_URL}/{slug}/"
            assert image.group(1) == f"{build.CANONICAL_BASE_URL}/og/{og.card_filename(slug)}"
            # The referenced card really exists on disk (path-equivalent of the URL).
            assert Path(image.group(1).rsplit("/og/", 1)[1]).name == og.card_filename(slug)
            assert (og_dir / og.card_filename(slug)).is_file()

    def test_no_placeholder_reference_remains(self) -> None:
        template = Path(build.SUBSTANCE_TEMPLATE).read_text()
        assert "placeholder" not in template


def test_build_generates_a_card_for_every_real_substance(og_dir: Path) -> None:
    """The full skills tree derives cards — 11 substances today (10 + 2C-B)."""
    substances: list[dict[str, object]] = build.load_substances()
    assert len(substances) >= 10
    paths = og.write_og_cards(substances, og_dir)
    assert len(paths) == len(substances)
    for path in paths:
        assert Path(path).stat().st_size > 0

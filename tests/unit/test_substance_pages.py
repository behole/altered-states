"""Tests for the per-substance static page feature (site.substance_pages).

Covers the SKILL.md front-matter parser, the pure substance derivation from
``skills/*`` (minus router), the standalone substance-page render (title, OG
meta, back link, determinism), the flag-gated home-page links, and the
deterministic delete+rebuild cleanup of generated page directories.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import build

SKILL_MD = """---
name: lsd-altered-state
description: >
  LSD phenomenological state simulation. The Technician — electric, analytical,
  precise, cosmic.
tags: [creative, phenomenology, lsd, altered-states]
version: "1.5"
author: behole
---
"""

PERSONA = {
    "id": "lsd",
    "name": "LSD",
    "emoji": "⚡",
    "character": "The Technician",
    "chatPrompt": "irrelevant",
}


def _substance() -> dict[str, object]:
    return {
        "id": "lsd",
        "name": "LSD",
        "emoji": "⚡",
        "character": "The Technician",
        "description": "The Technician — electric, analytical, precise.",
        "tags": ["lsd", "altered-states"],
        "version": "1.5",
        "href": "/lsd/",
    }


@pytest.fixture()
def tmp_skills(tmp_path: Path) -> Path:
    """A skills tree: two substance dirs, the router, plus an orphan slug."""
    for slug in ("lsd", "mdma", "router", "new-sub"):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "SKILL.md").write_text(SKILL_MD.replace("lsd-altered-state", f"{slug}-altered-state"))
    return tmp_path


class TestParseSkillFrontMatter:
    def test_parses_block_scalar_description(self) -> None:
        fm = build.parse_skill_front_matter(SKILL_MD)
        assert fm["description"] == (
            "LSD phenomenological state simulation. The Technician — electric, analytical, precise, cosmic."
        )

    def test_parses_tags_list_and_scalar_values(self) -> None:
        fm = build.parse_skill_front_matter(SKILL_MD)
        assert fm["tags"] == ["creative", "phenomenology", "lsd", "altered-states"]
        assert fm["version"] == "1.5"
        assert fm["author"] == "behole"

    def test_no_front_matter_raises(self) -> None:
        with pytest.raises(ValueError):
            build.parse_skill_front_matter("# no front matter\n")

    def test_unparseable_line_raises(self) -> None:
        with pytest.raises(ValueError):
            build.parse_skill_front_matter("---\njust some text: x\nno-separator-oops\n---\n")


class TestLoadSubstances:
    def test_covers_every_substance_dir_minus_router(self, tmp_skills: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build, "SKILLS_DIR", str(tmp_skills))
        substances = build.load_substances()
        assert [s["id"] for s in substances] == ["lsd", "mdma", "new-sub"]  # router excluded, sorted

    def test_orphan_slug_gets_fresh_identity_from_front_matter(
        self, tmp_skills: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(build, "SKILLS_DIR", str(tmp_skills))
        orphan = next(s for s in build.load_substances() if s["id"] == "new-sub")
        assert orphan["name"] == "NEW-SUB"  # derived from the -altered-state anchor
        assert orphan["character"] == ""
        assert orphan["description"].startswith("LSD phenomenological")

    def test_repo_has_one_substance_per_skill_dir(self) -> None:
        skills_dir = Path(build.SKILLS_DIR)
        expected = sorted(
            d.name
            for d in skills_dir.iterdir()
            # Router is a dispatch skill; combos/* are blend overlay skills,
            # not substances (they live one level deeper than skills/<slug>/SKILL.md).
            if d.is_dir() and d.name not in (build.ROUTER_SLUG, "combos")
        )
        assert [s["id"] for s in build.load_substances()] == expected
        assert "combos" not in {s["id"] for s in build.load_substances()}


class TestSubstanceLinks:
    def test_flag_off_compiles_links_out_completely(self) -> None:
        assert build.render_substance_links([_substance()], enabled=False) == ""

    def test_flag_on_links_every_substance_page(self) -> None:
        html = build.render_substance_links(
            [
                _substance(),
                {"id": "mdma", "name": "MDMA", "emoji": "💎", "character": "The Connector", "href": "/mdma/"},
            ],
            enabled=True,
        )
        assert 'href="/lsd/"' in html
        assert 'href="/mdma/"' in html
        assert build.render_substance_links(
            build.load_substances(),
            enabled=True,
        ).count('href="/') == len(build.load_substances())

    def test_values_are_html_escaped(self) -> None:
        substance = _substance()
        substance["character"] = 'The <Technician> "thinks"'
        html = build.render_substance_links([substance], enabled=True)
        assert "The &lt;Technician&gt;" in html
        assert "&quot;thinks&quot;" in html
        assert "<Technician>" not in html


class TestRenderSubstancePage:
    def test_title_og_and_back_link_present(self) -> None:
        page = build.render_substance_page(_substance(), Path(build.SUBSTANCE_TEMPLATE).read_text())
        assert "<title>LSD — Altered States</title>" in page
        assert 'property="og:title"' in page
        assert 'property="og:description"' in page
        assert 'content="/og/placeholder.svg"' in page
        assert 'href="/"' in page  # home back-link
        assert build.SUBSTANCE_PAGE_MARKER in page

    def test_no_placeholders_survive_render(self) -> None:
        page = build.render_substance_page(_substance(), Path(build.SUBSTANCE_TEMPLATE).read_text())
        assert "__" not in page

    def test_render_is_deterministic(self) -> None:
        template = Path(build.SUBSTANCE_TEMPLATE).read_text()
        assert build.render_substance_page(_substance(), template) == build.render_substance_page(
            {**_substance()}, template
        )

    def test_json_payload_is_injected_and_escaped(self) -> None:
        substance = _substance()
        substance["description"] = "script closer </script> inside"
        page = build.render_substance_page(substance, Path(build.SUBSTANCE_TEMPLATE).read_text())
        match = next(line for line in page.splitlines() if build.SUBSTANCE_PAGE_MARKER in line)
        assert "</sub" not in match.lower()

    def test_meta_description_is_first_sentence(self) -> None:
        page = build.render_substance_page(_substance(), Path(build.SUBSTANCE_TEMPLATE).read_text())
        assert ('name="description" content="The Technician — electric, analytical, precise."') in page


def _payload_js(page: str) -> str:
    match = re.search(r'substance-payload">(.*?)</script>', page, re.DOTALL)
    assert match is not None
    return match.group(1)


@pytest.fixture()
def tmp_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect SITE_DIR and SUBSTANCE_TEMPLATE into a tmp tree."""
    (tmp_path / "site").mkdir()
    (tmp_path / "substance.template.html").write_text(Path(build.SUBSTANCE_TEMPLATE).read_text())
    monkeypatch.setattr(build, "SITE_DIR", str(tmp_path / "site"))
    monkeypatch.setattr(build, "SUBSTANCE_TEMPLATE", str(tmp_path / "substance.template.html"))
    return tmp_path / "site"


class TestWriteSubstancePages:
    def test_writes_one_page_per_substance(self, tmp_site: Path) -> None:
        pages = build.write_substance_pages([_substance()], enabled=True)

        assert pages == [str(tmp_site / "lsd" / "index.html")]
        assert Path(pages[0]).stat().st_size > 0
        assert build.SUBSTANCE_PAGE_MARKER in Path(pages[0]).read_text()

    def test_flag_off_removes_generated_pages(self, tmp_site: Path) -> None:
        build.write_substance_pages([_substance()], enabled=True)
        assert (tmp_site / "lsd" / "index.html").exists()

        pages = build.write_substance_pages([_substance()], enabled=False)

        assert pages == []
        assert not (tmp_site / "lsd").exists()

    def test_rebuild_of_deleted_page_is_byte_identical(self, tmp_site: Path) -> None:
        build.write_substance_pages([_substance()], enabled=True)
        first: str = (tmp_site / "lsd" / "index.html").read_text()

        (tmp_site / "lsd" / "index.html").unlink()
        build.write_substance_pages([_substance()], enabled=True)
        second: str = (tmp_site / "lsd" / "index.html").read_text()

        assert first == second

    def test_stale_generated_dir_is_removed(self, tmp_site: Path) -> None:
        stale = tmp_site / "retired-sub"
        stale.mkdir()
        (stale / "index.html").write_text(f"x {build.SUBSTANCE_PAGE_MARKER} y")

        build.write_substance_pages([_substance()], enabled=True)

        assert not stale.exists()

    def test_foreign_dirs_are_never_touched(self, tmp_site: Path) -> None:
        foreign = tmp_site / "music"
        foreign.mkdir()
        (foreign / "index.html").write_text("<html>music stub</html>")

        build.write_substance_pages([_substance()], enabled=False)

        assert (foreign / "index.html").read_text() == "<html>music stub</html>"


def test_substance_payload_json_round_trips() -> None:
    page = build.render_substance_page(_substance(), Path(build.SUBSTANCE_TEMPLATE).read_text())
    payload = json.loads(_payload_js(page))
    assert payload["id"] == "lsd"
    assert payload["href"] == "/lsd/"

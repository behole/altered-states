"""Dose-arc diff view payload tests for site.diff_view.

VAL-SITE-007: the payload covers 10 substances (skills/* minus router) x 7
phenomenological dimensions (the deprivation-matrix keys), every value
derived from skills/<sub>/SKILL.md — spot checks trace values back to skill
plaintext. VAL-SITE-008 groundwork: the rendered view exposes the payload
and the flag-off build compiles the whole view out.
"""

from __future__ import annotations

import json
import re
from typing import Any

import build

SPOT_CHECK_SUBSTANCES = ("lsd", "psilocybin")


def _payload_by_id() -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in build.build_diff_payload(build.load_substances())}


def _collapsed(text: str) -> str:
    """Normalize like the extractor's cleaner: bullets and emphasis dropped,
    whitespace collapsed, lowercase. Skill plaintext empathy for markdown
    conventions."""
    stripped_lines = [re.sub(r"^[\s>]*[-+]\s+", "", line) for line in text.splitlines()]
    return " ".join(
        line.replace("**", "").replace("*", "").replace("`", "").strip() for line in stripped_lines if line.strip()
    ).lower()


def _skill_text(slug: str) -> str:
    with open(f"skills/{slug}/SKILL.md") as f:
        return f.read()


class TestDiffPayloadCoversTheMatrix:
    def test_payload_substance_set_equals_skills_minus_router(self) -> None:
        slugs = {s["id"] for s in build.load_substances()}
        assert len(slugs) == 11
        assert "router" not in slugs
        assert {s["id"] for s in _payload_by_id().values()} == slugs

    def test_every_substance_has_seven_nonempty_dimension_values(self) -> None:
        for slug, entry in _payload_by_id().items():
            assert set(entry["dimensions"]) == set(build.DIFF_DIMENSIONS)
            for key, value in entry["dimensions"].items():
                assert value.strip(), (slug, key)

    def test_language_duration_ego_rows_nonempty_for_every_substance(self) -> None:
        for slug, entry in _payload_by_id().items():
            assert entry["language"].strip(), slug
            assert entry["duration_label"].strip(), slug
            assert entry["ego_behavior"].strip(), slug

    def test_row_space_is_ten_columns(self) -> None:
        keys = list(build.DIFF_DIMENSIONS) + [extra[0] for extra in build.DIFF_EXTRA_ROWS]
        assert len(keys) == 10
        assert len(set(keys)) == 10

    def test_every_value_is_skill_text_plaintext(self) -> None:
        """No hand-typed values: each entry's strings appear in (whitespace-
        collapsed) skills/<sub>/SKILL.md. Truncation ellipses are stripped
        first — the contract only demands the value's own words."""
        for slug, entry in _payload_by_id().items():
            skill = _collapsed(_skill_text(slug))
            values = [*entry["dimensions"].values(), entry["language"], entry["ego_behavior"]]
            for raw_value in values:
                value = _collapsed(raw_value).removesuffix("…")
                assert value in skill, (slug, value[:70])


class TestSpotChecksAgainstSkillText:
    def test_psilocybin_table_cells_come_from_its_dimension_matrix(self) -> None:
        """psilocybin carries the canonical 7-row table with Medium column
        values; those exact cells must be the payload's dimension values."""
        medium_column = {
            "perceptual": "Geometric patterns, morphing, synesthesia",
            "somatic": "Energy waves, body buzz",
        }
        payload = _payload_by_id()["psilocybin"]
        for key, expected in medium_column.items():
            assert payload["dimensions"][key] == expected
            assert expected in _skill_text("psilocybin")

    def test_lsd_spot_checks_match_skill_plaintext(self) -> None:
        skill = _skill_text("lsd")
        dims = _payload_by_id()["lsd"]["dimensions"]
        # lsd SKILL.md medium profile: "Time dilation pronounced..." and the
        # ego passage "Partial ego dissolution: gradual, expansive...".
        assert "Time dilation pronounced" in dims["temporal"]
        assert "Time dilation pronounced" in skill
        assert dims["ego"].startswith("Partial ego dissolution")
        assert "Partial ego dissolution" in skill

    def test_unlike_pairs_differ_on_at_least_three_rows(self) -> None:
        """VAL-SITE-009 groundwork: any unlike pair differs on >= 3 of the 10
        rows; the same pair picked twice is identical."""
        payload = _payload_by_id()

        def value(entry: dict[str, Any], row: str) -> str:
            source = entry["dimensions"] if row in entry["dimensions"] else entry
            return str(source[row])

        rows = [*build.DIFF_DIMENSIONS, "language", "ego_behavior"]
        for left, right in (("lsd", "psilocybin"), ("salvia", "ketamine"), ("dmt", "mescaline")):
            differing = sum(value(payload[left], r) != value(payload[right], r) for r in rows)
            assert differing >= 3, (left, right, differing)

    def test_same_substance_yields_identical_columns(self) -> None:
        entry = _payload_by_id()["mdma"]
        duplicated = build.build_diff_payload([sub for sub in build.load_substances() if sub["id"] == "mdma"])[0]
        assert duplicated == entry  # pure function of the skills dir

    def test_durations_trace_to_the_arc_extraction(self) -> None:
        payload = build.build_arc_payload(build.load_substances())
        diff = _payload_by_id()
        for substance in payload:
            assert diff[substance["id"]]["duration_label"] == substance["arc"]["duration_label"]
        salvia_label = diff["salvia"]["duration_label"]
        assert "\u2013" in salvia_label and "min" in salvia_label


class TestFlagLifecycle:
    def test_diff_nav_and_view_compile_out_when_flag_off(self) -> None:
        payload = build.build_diff_payload(build.load_substances())
        assert build.render_diff_nav(False) == ""
        assert build.render_diff_view(payload, False) == ""

    def test_diff_view_embeds_payload_when_flag_on(self) -> None:
        payload = build.build_diff_payload(build.load_substances())
        view = build.render_diff_view(payload, True)
        assert 'id="diff-data"' in view
        assert 'id="view-diff"' in view
        embedded = json.loads(view.split('<script type="application/json" id="diff-data">')[1].split("</script>")[0])
        assert [s["id"] for s in embedded["substances"]] == [s["id"] for s in payload]
        assert embedded["substances"][0]["dimensions"]

    def test_diff_nav_links_to_the_diff_view_when_flag_on(self) -> None:
        nav = build.render_diff_nav(True)
        assert 'data-view="diff"' in nav
        assert "Compare" in nav

    def test_diff_payload_is_deterministic(self) -> None:
        first = json.dumps(build.build_diff_payload(build.load_substances()), sort_keys=True)
        assert json.dumps(build.build_diff_payload(build.load_substances()), sort_keys=True) == first

    def test_negated_mention_never_fills_the_dimension_it_denies(self) -> None:
        """Scrutiny fix: 'Relational, not mystical' / 'no ego dissolution' / 'not
        perceptual or cognitive' must not be quoted for the dimension they deny."""
        body = "\n".join(
            [
                "## The Character",
                "- Relational, not mystical. The connection is with specific people.",
                "- Mystical flashes surface briefly at the peak.",
                "- There are no hallucinations, no ego dissolution, no cosmic revelations.",
                "- Softened, authentic self emerges.",
                "- The transformation is emotional, not perceptual or cognitive.",
                "- World looks normal, feels different.",
            ]
        )
        got = build._keyword_line(body, ("mystic", "sacred"), allowed_labels={"mystical"})
        assert got.startswith("Mystical flashes"), got
        got_ego = build._keyword_line(body, ("ego",), allowed_labels={"ego"})
        assert "no ego dissolution" not in got_ego.lower()
        got_perceptual = build._keyword_line(body, ("percept", "visual", "reality"), allowed_labels={"perceptual"})
        assert "not perceptual" not in got_perceptual.lower()

    def test_what_to_avoid_section_is_never_quoted(self) -> None:
        body = "\n".join(
            [
                "## The Peak",
                "- Cosmic unity saturates the entire field.",
                "",
                "## What to Avoid",
                "- Mystical framing (NOT this substance)",
            ]
        )
        got = build._keyword_line(body, ("mystic", "cosmic"), allowed_labels={"mystical"})
        assert got == "Cosmic unity saturates the entire field."

    def test_no_cross_dimension_contamination(self) -> None:
        """Scrutiny fix: a stem inside another dimension's labelled line is that
        other dimension's content (ibogaine temporal <- Perceptual bubble;
        salvia ego_behavior <- Cognitive line; ketamine temporal <- director
        guidance)."""
        body = "\n".join(
            [
                "- Perceptual: dreamlike imagery surfaces — doorways. Moments of timeless drift. Hours pass.",
                "- Ibogaine onset is slow (1-3 hours). Duration is extreme (12-24 hours active).",
                "- Hold the grounding. Remind them of safety, location, temporality.",
                "- Ketamine onset is rapid (seconds to minutes). Duration is short (30-60 min).",
            ]
        )
        temporal_keywords = ("time dilation", "timeless", "duration", "onset", "temporal", "arc", "hours")
        got = build._keyword_line(body, temporal_keywords, allowed_labels={"temporal"})
        assert got.startswith("Ibogaine onset"), got
        assert "temporality" not in got.lower() and "hold the grounding" not in got.lower()
        # the same guard picks ketamine's arc prose, not the director row
        body_k = body.replace("Ibogaine onset is slow (1-3 hours). Duration is extreme (12-24 hours active).", "")
        got_k = build._keyword_line(body_k, temporal_keywords, allowed_labels={"temporal"})
        assert got_k.startswith("Ketamine onset"), got_k

    def test_named_scrutiny_findings_are_fixed_in_the_real_payload(self) -> None:
        payload = _payload_by_id()
        # mdma: negated lines never quoted for the dimension they deny
        assert "not mystical" not in payload["mdma"]["dimensions"]["mystical"].lower()
        assert "no ego dissolution" not in payload["mdma"]["dimensions"]["ego"].lower()
        assert "not perceptual" not in payload["mdma"]["dimensions"]["perceptual"].lower()
        # ibogaine temporal is real temporal prose, not the Perceptual bubble
        assert payload["ibogaine"]["dimensions"]["temporal"].lower().startswith("ibogaine onset")
        # ketamine temporal: no director safety guidance inside the row
        temporal = payload["ketamine"]["dimensions"]["temporal"].lower()
        assert "hold the grounding" not in temporal
        assert "onset is rapid" in temporal
        # salvia ego behaviour is an Ego line, not a Cognitive one
        ego_behavior = payload["salvia"]["ego_behavior"]
        assert not ego_behavior.startswith("Cognitive:")

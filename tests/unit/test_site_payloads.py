"""Build-time payload tests for the dose-arc timeline (site.arc_timeline).

VAL-SITE-004: the payload covers all 10 substances x 5 canonical phases, with
durations DERIVED from skills/<sub>/SKILL.md (spot check: salvia's minutes
arc, ibogaine's 12-24 h arc — read straight from the skill files).
VAL-SITE-005/006 groundwork: the rendered view carries phase data attributes
in DOM order and proportional extents the browser checks.
"""

from __future__ import annotations

import itertools
import json
import os
from pathlib import Path

import pytest

import build
from altered_states import feature_flags


def test_parse_time_pair_accepts_skill_prose_variants() -> None:
    variants = [
        ("1-3 hours", (3600.0, 10800.0)),
        ("0-60 seconds", (0.0, 60.0)),
        ("60 seconds \u2013 2 minutes", (60.0, 120.0)),
        ("2-5 minutes", (120.0, 300.0)),
        ("0-5 min IV / 10-20 min intranasal", (0.0, 300.0)),
        ("18+ hours", (64800.0, 64800.0)),
        ("5-15 min", (300.0, 900.0)),
    ]
    for text, expected in variants:
        assert build.parse_time_pair(text) == expected, text


def test_parse_time_pair_rejects_text_without_a_time_shape() -> None:
    assert build.parse_time_pair("days to weeks") is None
    assert build.parse_time_pair("~90% coherent") is None
    assert build.parse_time_pair("") is None


def test_phase_classification_maps_skill_heading_names() -> None:
    cases = [
        ("Onset (1-3 hours)", "onset"),
        ("Acceleration (60 seconds \u2013 2 minutes)", "ascent"),
        ("Peak / Breakthrough (2-5 minutes)", "peak"),
        ("Deep Visionary (6-12 hours)", "peak"),
        ("Early Visionary (3-6 hours)", "ascent"),
        ("Early Descent (5-10 minutes)", "descent"),
        ("Integration / Resolution (12-18 hours)", "descent"),
        ("Afterglow (15-30 minutes)", "afterglow"),
    ]
    for heading, canonical in cases:
        assert build._classify_phase_name(heading) == canonical, heading


def test_arc_payload_covers_all_ten_substances_five_phases() -> None:
    substances = build.load_substances()
    payload = build.build_arc_payload(substances)
    assert {s["id"] for s in payload} == {s["id"] for s in substances}
    for substance in payload:
        phases = [p["name"] for p in substance["arc"]["phases"]]
        assert phases == list(build.ARC_PHASES), substance["id"]


def test_arc_spot_check_salvia_is_minute_scale_and_ibogaine_12_to_24_hours() -> None:
    """The whole spot-check assertion: the numbers in the payload must be
    consistent with the durations stated in salvia's and ibogaine's SKILL.md."""
    payload = {s["id"]: s for s in build.build_arc_payload(build.load_substances())}
    salvia = payload["salvia"]["arc"]
    ibogaine = payload["ibogaine"]["arc"]
    # salvia SKILL.md: onset 0-60 s ... afterglow 15-30 min; totals read
    # "0-60 seconds" and "15-30 minutes" in its phase headings.
    salvia_by_name = {p["name"]: p for p in salvia["phases"]}
    assert salvia_by_name["onset"]["max_seconds"] == 60.0
    assert salvia_by_name["afterglow"]["max_seconds"] == 1800.0
    assert 0 < salvia["bounded_max_seconds"] <= 1800.0  # minutes magnitude
    # ibogaine SKILL.md: "Duration is extreme (12-24 hours active...)" and its
    # phase headings run 1-3 h onset through 12-24 h resolution.
    assert 12 * 3600 <= ibogaine["bounded_max_seconds"] <= 24 * 3600
    ib_by_name = {p["name"]: p for p in ibogaine["phases"]}
    assert ib_by_name["onset"]["min_seconds"] >= 3600.0  # 1-3 h onset
    # Ibogaine's afterglow is stated as "days to weeks": present and labeled,
    # but never given invented numeric bounds.
    assert ib_by_name["afterglow"]["max_seconds"] is None
    assert "days" in ib_by_name["afterglow"]["label"]
    # Relative extremes hold: ibogaine's arc is orders of magnitude longer.
    assert ibogaine["bounded_max_seconds"] / salvia["bounded_max_seconds"] >= 46


def test_arc_summaries_are_derived_not_empty() -> None:
    payload = build.build_arc_payload(build.load_substances())
    for substance in payload:
        for phase in substance["arc"]["phases"]:
            assert phase["summary"].strip(), (substance["id"], phase["name"])


def test_arc_payload_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pure function of the skills dir: same input, byte-identical payload."""
    skills_snapshot = json.dumps(build.build_arc_payload(build.load_substances()), sort_keys=True)
    monkeypatch.chdir(tmp_path)
    assert json.dumps(build.build_arc_payload(build.load_substances()), sort_keys=True) == skills_snapshot


def test_prose_mode_substances_derive_a_monotone_arc() -> None:
    """The middle-phases split keeps phases ordered with no overlaps. Heading
    mode keeps the skill's stated bounds verbatim even when they overlap in
    the source (ketamine: peak 5-30 min, descent 20-60 min)."""
    payload = build.build_arc_payload(build.load_substances())
    for substance in payload:
        if substance["arc"]["mode"] != "prose_duration":
            continue
        bounded = [
            (p["min_seconds"], p["max_seconds"])
            for p in substance["arc"]["phases"]
            if p["max_seconds"] is not None and p["min_seconds"] is not None
        ]
        for (lo_a, hi_a), (lo_b, hi_b) in itertools.pairwise(bounded):
            assert hi_a <= lo_b + 1e-6, (substance["id"], lo_a, hi_a, lo_b, hi_b)
            assert lo_b <= hi_b


def test_arc_flag_off_drives_the_real_render_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """The AGENTS.md rule-4 lifecycle: the FLAG_ env var decides
    enabled_section_flags(), and the derived gate — not a hardcoded bool —
    drives what compiles into the page."""
    monkeypatch.setenv("FLAG_SITE_ARC_TIMELINE", "off")
    store = feature_flags.load_flags(environ=dict(os.environ))
    monkeypatch.setattr(build, "flags", store)
    flags = build.enabled_section_flags()
    assert flags[build.ARC_FLAG] is False
    payload = build.build_arc_payload(build.load_substances())
    assert build.render_arc_view(payload, flags[build.ARC_FLAG]) == ""
    assert build.render_arc_nav(flags[build.ARC_FLAG]) == ""
    # Negative control: the same drive with the flag on still renders.
    monkeypatch.setenv("FLAG_SITE_ARC_TIMELINE", "on")
    store_on = feature_flags.load_flags(environ=dict(os.environ))
    monkeypatch.setattr(build, "flags", store_on)
    flags_on = build.enabled_section_flags()
    assert flags_on[build.ARC_FLAG] is True
    assert build.render_arc_nav(flags_on[build.ARC_FLAG])


def test_arc_script_compares_data_bounded_string_not_truthiness() -> None:
    """Scrutiny fix: getAttribute returns the STRING "false", which is truthy;
    the unbounded-phase fallback is only reachable via === 'true'."""
    view = build.render_arc_view(build.build_arc_payload(build.load_substances()), True)
    assert "data-bounded') === 'true'" in view
    # A full attribute-looking line still declares the bounded/unbounded pairs.
    assert 'data-bounded="true"' in view and 'data-bounded="false"' in view


def test_arc_view_embeds_payload_and_phase_data_attributes() -> None:
    payload = build.build_arc_payload(build.load_substances())
    view = build.render_arc_view(payload, True)
    assert '<div id="view-arc" class="view-container">' in view
    assert 'id="arc-data"' in view
    assert "data-total-min-seconds" in view and "data-total-max-seconds" in view
    assert "data-min-seconds" in view and "data-max-seconds" in view
    assert 'data-summary="' not in view  # summaries ship only in the JSON payload
    data_blob = view.split('id="arc-data">', 1)[1]
    assert '"summary"' in data_blob


def test_arc_nav_link_compiled_into_enabled_page() -> None:
    nav = build.render_arc_nav(True)
    assert 'data-view="arc"' in nav

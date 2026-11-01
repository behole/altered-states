"""Journal arc dashboards (site.journal_dashboards) payload tests.

VAL-SITE-012 groundwork: the series payload is a pure function of the
temporal-lab journals, and every per-cycle axis value is exactly the journal
entry's own value (phenomenology intensity, novelty, emotional valence, ego
coherence, integration state, cycle index) — nothing invented. Also covers
the ALTERED_STATES_TEMPORAL_PATH override (fixture scaffold, never the real
experiments/ tree) and the compile-out contract when the flag is off.

Fixtures are tmp-dir journal JSON files shaped exactly like the temporal_init
dry-run output (initial cycle-0 entry without an experience block, then
per-cycle entries with an experience object).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import build


def _stub_entry(cycle: int, intensity: float = 0.5, novelty: float = 0.5) -> dict[str, Any]:
    """One cycle shaped exactly like a temporal_init dry-run stub entry."""
    entry: dict[str, Any] = {
        "timestamp": "2026-10-31T00:00:00",
        "cycle": cycle,
        "emotional_state": "precise",
        "clarity": "moderate",
        "integration": "low",
        "experience": {"description": "[DRY-RUN STUB]", "intensity": intensity, "novelty": novelty},
        "reflections": ["dry-run reflection one"],
        "questions": ["dry-run question?"],
    }
    if cycle == 0:
        # The initial journal entry carries no experience block.
        entry.pop("experience")
        entry["emotional_state"] = "confused"
    return entry


def _scaffold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    journals = tmp_path / "journals"
    journals.mkdir()
    monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(tmp_path))
    return journals


class TestTemporalPathOverride:
    def test_env_root_with_journals_dir_is_used(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        scaffold = _scaffold(monkeypatch, tmp_path)
        (scaffold / "lsd_journal.json").write_text(json.dumps([_stub_entry(0), _stub_entry(1)]))

        journals = build.load_journals()

        assert len(journals["lsd"]) == 2
        # Nothing was ever written into the real runtime dir.
        assert list(Path(build.JOURNALS_DIR).glob("*_journal.json")) == []

    def test_env_pointing_directly_at_journals_dir_is_used(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        journals_dir = _scaffold(monkeypatch, tmp_path)
        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(journals_dir))
        (journals_dir / "ketamine_journal.json").write_text(json.dumps([_stub_entry(1)]))

        journals = build.load_journals()

        assert len(journals["ketamine"]) == 1

    def test_unset_env_falls_back_to_runtime_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALTERED_STATES_TEMPORAL_PATH", raising=False)

        assert build.temporal_journals_dir() == build.JOURNALS_DIR

    def test_unresolvable_env_falls_back_to_runtime_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(Path("/definitely/not/here")))

        assert build.temporal_journals_dir() == build.JOURNALS_DIR


class TestSeriesMatchesJournalsExactly:
    def test_every_axis_value_equals_the_journal_entry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        scaffold = _scaffold(monkeypatch, tmp_path)
        source = [_stub_entry(0), _stub_entry(1, 0.5, 0.6), _stub_entry(2)]
        cycle_delays = [2, 0, 1]
        shuffled = [dict(s, cycle=c) for s, c in zip(source, cycle_delays, strict=True)]
        (scaffold / "lsd_journal.json").write_text(json.dumps(shuffled))

        journals = build.load_journals()
        payload = build.build_journal_series_payload(journals)
        series = {c["id"]: c for c in payload["characters"]}
        points = series["lsd"]["cycles"]

        assert [p["cycle"] for p in points] == [0, 1, 2]
        for point, entry in zip(points, shuffled_source(shuffled), strict=True):
            expected_experience = entry.get("experience", {})
            assert point["intensity"] == expected_experience.get("intensity")
            assert point["novelty"] == expected_experience.get("novelty")
            assert point["emotionalState"] == entry["emotional_state"]
            assert point["clarity"] == entry["clarity"]
            assert point["integration"] == entry["integration"]


def shuffled_source(shuffled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(shuffled, key=lambda e: e["cycle"])


class TestPayloadShape:
    def test_character_metadata_comes_from_the_persona_registry(self) -> None:
        payload = build.build_journal_series_payload({"lsd": [_stub_entry(1)]})

        assert len(payload["characters"]) == 1
        character = payload["characters"][0]
        assert character["id"] == "lsd"
        persona = next(p for p in build.PERSONAS if p["id"] == "lsd")
        assert character["name"] == persona["name"]
        assert character["emoji"] == persona["emoji"]
        assert character["character"] == persona["character"]

    def test_error_and_uncycled_entries_are_skipped(self) -> None:
        error_entry = dict(_stub_entry(5), error="boom")
        no_cycle = {"emotional_state": "even", "clarity": "moderate", "integration": "low"}

        payload = build.build_journal_series_payload({"lsd": [_stub_entry(1), error_entry, no_cycle]})

        assert [p["cycle"] for p in payload["characters"][0]["cycles"]] == [1]

    def test_missing_numeric_axis_is_none_not_zero(self) -> None:
        payload = build.build_journal_series_payload({"lsd": [_stub_entry(0)]})
        point = payload["characters"][0]["cycles"][0]

        assert point["intensity"] is None
        assert point["novelty"] is None

    def test_characters_with_no_cycles_contribute_nothing(self) -> None:
        payload = build.build_journal_series_payload({"lsd": [], "salvia": []})

        assert payload["characters"] == []

    def test_documented_axes_metadata_is_carried_in_the_payload(self) -> None:
        payload = build.build_journal_series_payload({"lsd": [_stub_entry(1)]})

        for name in ("intensity", "novelty", "emotionalState", "clarity", "integration"):
            assert name in payload["axes"]
            assert payload["axes"][name]["journalField"]

    def test_pure_function_is_deterministic(self) -> None:
        journals = {"lsd": [_stub_entry(1), _stub_entry(2)]}
        payload = build.build_journal_series_payload(journals)

        # A pure function: rebuilding from identical journals is byte-equal.
        again = build.build_journal_series_payload(journals)
        assert payload == again


class TestFlagCompileOut:
    def test_view_and_nav_compile_out_when_flag_off(self) -> None:
        assert build.render_journal_view({"axes": {}, "characters": []}, False) == ""
        assert build.render_journal_nav(False) == ""

    def test_view_inlines_the_payload_when_flag_on(self) -> None:
        payload = build.build_journal_series_payload({"lsd": [_stub_entry(1)]})
        view = build.render_journal_view(payload, True)

        assert "<" not in json.dumps(payload, sort_keys=True)
        assert json.dumps(payload, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c") in view
        assert 'id="jdash-data"' in view

    def test_nav_link_targets_the_dashboards_view(self) -> None:
        nav = build.render_journal_nav(True)

        assert 'data-view="journal_dashboards"' in nav
        assert "showView('journal_dashboards')" in nav

    def test_render_page_gates_the_journal_sections(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from altered_states import feature_flags

        monkeypatch.setattr(build, "flags", feature_flags.load_flags())

        template = tmp_path / "tpl.html"
        template.write_text("nav:${__JOURNAL_NAV__}:view:${__JOURNAL_VIEW__}:flags:__FLAGS__")
        monkeypatch.setattr(build, "TEMPLATE", str(template))

        payload_worker = build.build_journal_series_payload({"lsd": [_stub_entry(1)]})
        html = build.render_page(
            [{"id": "lsd"}],
            {"lsd": [_stub_entry(1)]},
            [],
            [],
            1,
            sections={
                "journal_nav": build.render_journal_nav(True),
                "journal_view": build.render_journal_view(payload_worker, True),
            },
        )

        assert 'data-view="journal_dashboards"' in html
        assert 'id="view-journal_dashboards"' in html

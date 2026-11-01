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

    def test_unset_env_defaults_to_the_committed_fixture_journals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALTERED_STATES_TEMPORAL_PATH", raising=False)

        assert build.temporal_journals_dir() == build.FIXTURE_JOURNALS_DIR

    def test_committed_fixtures_serve_the_default_build_and_the_runtime_is_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ALTERED_STATES_TEMPORAL_PATH", raising=False)

        journals = build.load_journals()

        fixture_files = {p.name for p in Path(build.FIXTURE_JOURNALS_DIR).glob("*_journal.json")}
        assert fixture_files == {f"{p['id']}_journal.json" for p in build.PERSONAS}
        for entries in journals.values():
            assert entries, "every persona must chart from the committed fixtures"

    def test_missing_fixtures_fall_back_to_runtime_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("ALTERED_STATES_TEMPORAL_PATH", raising=False)
        monkeypatch.setattr(build, "FIXTURE_JOURNALS_DIR", str(tmp_path / "gone"))

        assert build.temporal_journals_dir() == build.JOURNALS_DIR

    def test_unresolvable_env_falls_through_to_fixtures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(Path("/definitely/not/here")))

        assert build.temporal_journals_dir() == build.FIXTURE_JOURNALS_DIR


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


class TestReadoutWiring:
    """Scrutiny blocker fix: the hover/click readout used to be keyed by the
    node enumeration index into the cycle array (`cycles[idx]`), but nodes are
    emitted per (axis, cycle) pair — so ~half the points showed the wrong
    cycle or the idle hint. Now every node carries its own cycle + axis from
    the emit loop scope (data-cycle/data-axis) and the wiring resolves the
    payload point by those attributes; the readout therefore shows exactly
    the payload values for the point the user pointed at. Tested offline: the
    template source is pinned to that wiring, and the payload-side emission
    contract is cross-checked point by point."""

    def _payload_and_view(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[dict[str, Any], str]:
        scaffold = _scaffold(monkeypatch, tmp_path)
        sources = {
            "lsd": [_stub_entry(0), _stub_entry(1, 0.5, 0.6), _stub_entry(2, 0.85, 0.2), _stub_entry(3, 0.4, 0.45)],
            "salvia": [_stub_entry(0), _stub_entry(1, 0.9, 0.8), _stub_entry(2, 0.5, 0.5)],
        }
        for sid, entries in sources.items():
            (scaffold / f"{sid}_journal.json").write_text(json.dumps(entries))
        payload = build.build_journal_series_payload(build.load_journals())
        return payload, build.render_journal_view(payload, True)

    @staticmethod
    def _expected_point_nodes(char: dict[str, Any]) -> list[tuple[Any, str]]:
        """The nodes the template emits: one per (numeric axis, cycle) pair
        with a value, in the documented emit-loop order."""
        emitted: list[tuple[Any, str]] = []
        for axis_key in ("intensity", "novelty"):
            for point in char["cycles"]:
                if point[axis_key] is not None:
                    emitted.append((point["cycle"], axis_key))
        return emitted

    def test_view_embeds_exactly_the_wired_payload(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        payload, view = self._payload_and_view(monkeypatch, tmp_path)
        embedded = json.loads(view.split('id="jdash-data">')[1].split("</script>")[0])

        assert embedded == payload

    def test_every_emitted_point_reads_its_own_payload_cycle(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        payload, _view = self._payload_and_view(monkeypatch, tmp_path)

        for char in payload["characters"]:
            self._assert_char_readouts_equal_payload(char)

    @staticmethod
    def _assert_char_readouts_equal_payload(char: dict[str, Any]) -> None:
        # Chart data must be non-uniform (else nothing distinguishes cycles).
        intensities = [p["intensity"] for p in char["cycles"] if p["intensity"] is not None]
        assert len(set(intensities)) >= 2
        emitted_nodes = TestReadoutWiring._expected_point_nodes(char)
        assert len(emitted_nodes) >= 4, "non-uniform fixture must emit enough points"
        for cycle, _axis_key in emitted_nodes:
            resolved = [p for p in char["cycles"] if str(p["cycle"]) == str(cycle)]
            # The wiring resolves by data-cycle, so the readout is whichever
            # payload point that attribute names — it must be unambiguous and
            # provide every field the readout renders.
            assert len(resolved) == 1
            point = resolved[0]
            for field in ("intensity", "novelty", "emotionalState", "clarity", "integration"):
                assert field in point

    def test_template_wiring_resolves_points_from_attributes_not_enumeration_index(self) -> None:
        with open(build.JOURNAL_TEMPLATE) as f:
            template_src = f.read()

        # The regression canary: the node enumeration index must not key the
        # readout to the cycle array.
        assert "cycles[idx]" not in template_src
        assert "function (node, idx)" not in template_src

        # Each emitted node carries its own cycle + axis from the emit loop.
        emission = (
            'parts += \'<g class="jdash-point" data-cycle="\' + escHtml(p.cycle) +\n'
            '          \'" data-axis="\' + a.key + \'" tabindex="0">\''
        )
        assert emission in template_src

        # The wiring resolves the payload point by those attributes.
        assert "pointForCycle(char.cycles, node.getAttribute('data-cycle'))" in template_src
        assert "axis: node.getAttribute('data-axis')" in template_src

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

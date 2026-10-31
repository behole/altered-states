"""Unit tests for the temporal-lab domain logic: cadence, characters, insights."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import cadence
import characters
import pytest

from tests.conftest import SCRIPTS_DIR, write_journal


def load_script(filename: str) -> ModuleType:
    """Load a temporal-lab script by file path.

    Scripts such as ``extract-insights.py`` are hyphenated, so they cannot be
    imported by module name; load them from disk instead.
    """
    import importlib.util
    import sys

    path = SCRIPTS_DIR / f"{filename}.py"
    module_name = filename.replace("-", "_")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def entry(
    cycle: int,
    emotional_state: str,
    description: str = "d",
    intensity: float = 0.5,
    novelty: float = 0.5,
) -> dict[str, Any]:
    """One journal entry, so a fixture reads as data rather than as nesting."""
    return {
        "cycle": cycle,
        "emotional_state": emotional_state,
        "experience": {"description": description, "intensity": intensity, "novelty": novelty},
    }


class TestCharacters:
    def test_every_substance_has_a_complete_profile(self) -> None:
        for name in characters.available_substances():
            profile = characters.substance_characteristics(name)
            assert profile["name"]
            assert profile["emotional_range"]
            assert profile["expression_style"]
            assert profile["learning_focus"]

    def test_available_substances_is_in_canonical_order(self) -> None:
        assert characters.available_substances()[0] == "psilocybin"
        assert characters.available_substances()[-1] == "ibogaine"

    def test_there_are_ten_substances(self) -> None:
        assert len(characters.available_substances()) == 10

    def test_unknown_substance_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            characters.substance_characteristics("unobtainium")

    def test_env_override_wins_over_the_default_base_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(tmp_path))
        assert characters.resolve_base_path() == tmp_path.resolve()

    def test_explicit_argument_wins_over_the_environment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(tmp_path / "env"))
        assert characters.resolve_base_path(str(tmp_path / "explicit")) == (tmp_path / "explicit").resolve()

    def test_default_base_path_lives_under_the_lab(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ALTERED_STATES_TEMPORAL_PATH", raising=False)
        assert characters.resolve_base_path().name == "runtime"


class TestCadence:
    def test_never_run_character_is_due(self) -> None:
        assert cadence.is_due({"substance": "lsd"}) is True

    def test_character_is_not_due_before_its_interval(self) -> None:
        now = datetime(2026, 5, 1, 12, 0, 0)
        last = (now - timedelta(minutes=10)).isoformat()
        assert cadence.is_due({"substance": "ibogaine", "last_cycle": last}, now) is False

    def test_character_is_due_after_its_interval(self) -> None:
        now = datetime(2026, 5, 1, 12, 0, 0)
        last = (now - timedelta(minutes=61)).isoformat()
        assert cadence.is_due({"substance": "salvia", "last_cycle": last}, now) is True

    def test_character_is_due_exactly_at_the_boundary(self) -> None:
        now = datetime(2026, 5, 1, 12, 0, 0)
        last = (now - timedelta(minutes=60)).isoformat()
        assert cadence.is_due({"substance": "dmt", "last_cycle": last}, now) is True

    def test_unknown_substance_uses_the_default_interval(self) -> None:
        assert cadence.cycle_minutes("unknown") == cadence.DEFAULT_CYCLE_MINUTES

    def test_fast_substances_fire_more_often_than_slow_ones(self) -> None:
        assert cadence.cycle_minutes("salvia") < cadence.cycle_minutes("ibogaine")

    def test_next_cycle_is_offset_from_the_supplied_time(self) -> None:
        base = datetime(2026, 5, 1, 12, 0, 0)
        expected = (base + timedelta(minutes=cadence.cycle_minutes("lsd"))).isoformat()
        assert cadence.next_cycle_at("lsd", base) == expected

    def test_due_characters_reads_character_files(self, tmp_path: Path) -> None:
        (tmp_path / "lsd.json").write_text(json.dumps({"substance": "lsd", "name": "The Technician"}))
        due = cadence.due_characters(tmp_path, datetime(2026, 5, 1, 12, 0, 0))
        assert [char["substance"] for char in due] == ["lsd"]

    def test_due_characters_skips_recently_run_ones(self, tmp_path: Path) -> None:
        now = datetime(2026, 5, 1, 12, 0, 0)
        (tmp_path / "ibogaine.json").write_text(
            json.dumps(
                {
                    "substance": "ibogaine",
                    "name": "The Ancestor",
                    "last_cycle": (now - timedelta(minutes=5)).isoformat(),
                }
            )
        )
        assert cadence.due_characters(tmp_path, now) == []


class TestExtractInsights:
    def test_collect_insights_reads_journal_files(self, tmp_path: Path, journal_entry: dict[str, Any]) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        write_journal(journals, "lsd", [{"cycle": 0, "emotional_state": "calm"}, journal_entry])

        insights = module.collect_insights(journals)

        assert len(insights) == 1
        assert insights[0]["substance"] == "lsd"
        assert insights[0]["cycles"] == 1

    def test_single_entry_journals_are_ignored(self, tmp_path: Path) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        write_journal(journals, "lsd", [{"cycle": 0, "emotional_state": "calm"}])
        assert module.collect_insights(journals) == []

    def test_most_intense_entry_is_selected(self, tmp_path: Path) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        write_journal(
            journals,
            "lsd",
            [
                {"cycle": 0, "emotional_state": "calm"},
                entry(1, "a", "low", intensity=0.1, novelty=0.1),
                entry(2, "b", "high", intensity=0.9, novelty=0.5),
            ],
        )
        insight = module.collect_insights(journals)[0]
        assert insight["most_intense"] == "high"
        assert insight["intensity_score"] == 0.9

    def test_stability_counts_distinct_emotions(self, tmp_path: Path) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        write_journal(
            journals,
            "lsd",
            [
                {"cycle": 0, "emotional_state": "calm"},
                entry(1, "awed"),
                entry(2, "awed", intensity=0.6, novelty=0.6),
            ],
        )
        assert module.collect_insights(journals)[0]["emotional_stability"] == 1

    @pytest.mark.parametrize(
        ("stability", "expected"),
        [
            (1, "Highly focused evolution"),
            (2, "Exploring different emotional states"),
            (4, "Broad emotional exploration"),
        ],
    )
    def test_trend_for_buckets_stability(self, stability: int, expected: str) -> None:
        module = load_script("extract-insights")
        assert module.trend_for(stability) == expected

    def test_cross_character_section_reports_common_emotions(self, tmp_path: Path) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        for substance in ("lsd", "mdma"):
            write_journal(
                journals,
                substance,
                [
                    {"cycle": 0, "emotional_state": "calm"},
                    entry(1, "calm"),
                    entry(2, "warm"),
                    entry(3, "awed"),
                ],
            )
        lines = module.cross_character_lines(module.collect_insights(journals))
        assert any("Most Common Emotional States:" in line for line in lines)

    def test_analyze_patterns_writes_a_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = load_script("extract-insights")
        journals = tmp_path / "journals"
        write_journal(
            journals,
            "lsd",
            [
                {"cycle": 0, "emotional_state": "calm"},
                entry(1, "awed"),
            ],
        )
        monkeypatch.setattr(module, "resolve_base_path", lambda: tmp_path)

        module.analyze_patterns()

        report = tmp_path / "insights_report.txt"
        assert report.exists()
        assert "Temporal Insights & Patterns" in report.read_text()

    def test_analyze_patterns_handles_an_empty_lab(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        module = load_script("extract-insights")
        (tmp_path / "journals").mkdir()
        monkeypatch.setattr(module, "resolve_base_path", lambda: tmp_path)
        module.analyze_patterns()
        assert (tmp_path / "insights_report.txt").exists()

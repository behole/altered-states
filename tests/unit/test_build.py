"""Unit tests for build.py's parsing, normalisation, and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import build


class TestParseExperimentMd:
    def test_extracts_the_prompt_from_the_header(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert parsed["prompt"] == "What is love?"

    def test_extracts_run_info(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert parsed["run_info"].startswith("2026-04-22")

    def test_finds_every_substance_section(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert [section["name"] for section in parsed["substances"]] == ["Psilocybin", "LSD"]

    def test_captures_character_name(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert parsed["substances"][0]["character"] == "The Teacher"

    def test_captures_intensity(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert parsed["substances"][0]["intensity"] == "MEDIUM"

    def test_captures_the_response_body(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert "root system" in parsed["substances"][0]["response"]

    def test_trailing_horizontal_rule_is_stripped(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert not parsed["substances"][0]["response"].endswith("---")

    def test_emoji_is_extracted(self, experiment_md: Path) -> None:
        parsed = build.parse_experiment_md(str(experiment_md))
        assert parsed["substances"][0]["emoji"] == "🍄"

    def test_long_prompt_is_truncated_to_the_title_limit(self, tmp_path: Path) -> None:
        long_prompt = "x" * 200
        path = tmp_path / "long.md"
        path.write_text(f'# T\n> "{long_prompt}"\n> Run: now\n')
        parsed = build.parse_experiment_md(str(path))
        assert len(parsed["title"]) == build.MAX_TITLE_LENGTH
        assert parsed["title"].endswith("...")

    def test_short_prompt_is_kept_whole(self, tmp_path: Path) -> None:
        path = tmp_path / "short.md"
        path.write_text('# T\n> "hi"\n> Run: now\n')
        assert build.parse_experiment_md(str(path))["title"] == "hi"

    def test_missing_prompt_header_falls_back_to_unknown(self, tmp_path: Path) -> None:
        path = tmp_path / "bare.md"
        path.write_text("# T\n\nNo header here.\n")
        assert build.parse_experiment_md(str(path))["prompt"] == "Unknown"

    def test_file_without_sections_yields_no_substances(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.md"
        path.write_text('# T\n> "q"\n')
        assert build.parse_experiment_md(str(path))["substances"] == []


class TestJournalEntryToDict:
    def test_flattens_an_object_experience(self, journal_entry: dict[str, Any]) -> None:
        result = build.journal_entry_to_dict(journal_entry)
        assert result["experience"].startswith("The floor")
        assert result["intensity"] == "0.42"
        assert result["novelty"] == "0.71"

    def test_accepts_a_plain_string_experience(self) -> None:
        result = build.journal_entry_to_dict({"experience": "raw text"})
        assert result["experience"] == "raw text"

    def test_missing_experience_becomes_an_empty_string(self) -> None:
        assert build.journal_entry_to_dict({})["experience"] == ""

    def test_non_string_non_mapping_experience_is_stringified(self) -> None:
        assert build.journal_entry_to_dict({"experience": 42})["experience"] == "42"

    def test_top_level_intensity_wins_over_the_nested_value(self) -> None:
        entry = {"intensity": 0.9, "experience": {"intensity": 0.1}}
        assert build.journal_entry_to_dict(entry)["intensity"] == "0.9"

    def test_nested_intensity_used_when_top_level_is_absent(self) -> None:
        entry = {"experience": {"intensity": 0.3, "novelty": 0.4}}
        result = build.journal_entry_to_dict(entry)
        assert result["intensity"] == "0.3"
        assert result["novelty"] == "0.4"

    def test_cycle_count_preferred_over_cycle(self) -> None:
        assert build.journal_entry_to_dict({"cycle_count": 9, "cycle": 2})["cycle"] == 9

    def test_cycle_falls_back_when_count_absent(self) -> None:
        assert build.journal_entry_to_dict({"cycle": 2})["cycle"] == 2

    def test_questions_fall_back_to_open_questions(self) -> None:
        result = build.journal_entry_to_dict({"open_questions": ["why?"]})
        assert result["questions"] == ["why?"]


class TestPersonaState:
    def test_dormant_persona_has_no_cycles(self) -> None:
        journals: dict[str, list[dict[str, Any]]] = {persona["id"]: [] for persona in build.PERSONAS}
        states = build.get_persona_state(journals)
        assert states["lsd"] == {"currentState": "dormant", "cycleCount": 0}

    def test_cycle_count_deduplicates_repeated_cycle_numbers(self) -> None:
        journals: dict[str, list[dict[str, Any]]] = {persona["id"]: [] for persona in build.PERSONAS}
        journals["lsd"] = [{"cycle": 1}, {"cycle": 1}, {"cycle": 2}]
        assert build.get_persona_state(journals)["lsd"]["cycleCount"] == 2

    def test_error_entries_do_not_inflate_the_cycle_count(self) -> None:
        journals: dict[str, list[dict[str, Any]]] = {persona["id"]: [] for persona in build.PERSONAS}
        journals["lsd"] = [{"cycle": 1}, {"cycle": 2, "error": "boom"}]
        assert build.get_persona_state(journals)["lsd"]["cycleCount"] == 1

    def test_current_state_comes_from_the_last_entry(self) -> None:
        journals: dict[str, list[dict[str, Any]]] = {persona["id"]: [] for persona in build.PERSONAS}
        journals["mdma"] = [{"cycle": 1, "emotional_state": "warm"}, {"cycle": 2, "emotional_state": "intimate"}]
        assert build.get_persona_state(journals)["mdma"]["currentState"] == "intimate"

    def test_count_cycles_aggregates_across_personas(self) -> None:
        journals = {"a": [{"cycle": 1}, {"cycle": 2}], "b": [{"cycle": 1}]}
        assert build.count_cycles(journals) == 3


class TestFlagsAndRendering:
    def test_section_flags_returns_a_boolean_for_every_declared_section(self) -> None:
        assert set(build.enabled_section_flags()) == set(build.SECTION_FLAGS)

    def test_render_page_substitutes_every_placeholder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        template = tmp_path / "tpl.html"
        template.write_text(
            "P=__PERSONAS__ J=__JOURNALS__ E=__EXPERIMENTS__ M=__MUSIC__ "
            "F=__FLAGS__ C=__CYCLE_COUNT__ X=__EXP_COUNT__ S=__MUSIC_COUNT__"
        )
        monkeypatch.setattr(build, "TEMPLATE", str(template))

        html = build.render_page([{"id": "lsd"}], {"lsd": []}, [{"a": 1}], [{"tracks": [1, 2]}], 7)

        assert "__" not in html
        assert "P=" + json.dumps([{"id": "lsd"}]) in html
        assert "C=7" in html
        assert "X=1" in html
        assert "S=2" in html
        assert "F=" in html


class TestLoadDirectories:
    def test_load_experiments_returns_empty_when_directory_is_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(tmp_path / "missing"))
        assert build.load_experiments() == []

    def test_load_experiments_sorts_newest_first(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("2026-01-01-a.md", "2026-02-01-b.md"):
            (tmp_path / name).write_text(
                '# T\n> "q"\n> Run: now\n\n## 🍄 Psilocybin — *The Teacher*\n**Intensity:** MEDIUM\n\nbody\n'
            )
        monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(tmp_path))
        experiments = build.load_experiments()
        assert len(experiments) == 2
        assert experiments[0]["substances"][0]["name"] == "Psilocybin"

    def test_unparseable_experiment_is_skipped_without_raising(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "ok.md").write_text(
            '# T\n> "q"\n\n## 🍄 Psilocybin — *The Teacher*\n**Intensity:** MEDIUM\n\nbody\n'
        )
        monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(tmp_path))
        monkeypatch.setattr(build, "parse_experiment_md", _raiser_for("ok.md"))
        assert build.load_experiments() == []

    def test_load_music_skips_directories_without_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "lonely").mkdir()
        monkeypatch.setattr(build, "MUSIC_DIR", str(tmp_path))
        assert build.load_music() == []

    def test_load_music_builds_audio_urls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp = tmp_path / "describe-a-song"
        exp.mkdir()
        (exp / "metadata.json").write_text(json.dumps({"title": "Describe", "prompt": "p", "date": "2026-01-01"}))
        (exp / "tracks.json").write_text(json.dumps({"tracks": [{"persona_id": "lsd", "audio_file": "lsd.mp3"}]}))
        monkeypatch.setattr(build, "MUSIC_DIR", str(tmp_path))

        music = build.load_music()

        assert music[0]["title"] == "Describe"
        assert music[0]["tracks"][0]["audio_url"] == "music/describe-a-song/lsd.mp3"

    def test_track_without_audio_has_no_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        exp = tmp_path / "x"
        exp.mkdir()
        (exp / "metadata.json").write_text(json.dumps({"title": "T"}))
        (exp / "tracks.json").write_text(json.dumps({"tracks": [{"persona_id": "lsd"}]}))
        monkeypatch.setattr(build, "MUSIC_DIR", str(tmp_path))
        assert build.load_music()[0]["tracks"][0]["audio_url"] is None

    def test_load_journals_gives_every_persona_a_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build, "JOURNALS_DIR", str(tmp_path))
        monkeypatch.setattr(build, "FIXTURE_JOURNALS_DIR", str(tmp_path))
        journals = build.load_journals()
        assert len(journals) == len(build.PERSONAS)
        assert all(value == [] for value in journals.values())

    def test_malformed_journal_object_is_normalised_to_a_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "lsd_journal.json").write_text(json.dumps({"not": "a list"}))
        monkeypatch.setattr(build, "JOURNALS_DIR", str(tmp_path))
        monkeypatch.setattr(build, "FIXTURE_JOURNALS_DIR", str(tmp_path))
        assert build.load_journals()["lsd"] == []


def _raiser_for(filename: str) -> Any:
    def parse(path: str) -> dict[str, Any]:
        if path.endswith(filename):
            raise ValueError("bad file")
        return {"substances": [{"name": "ok"}]}

    return parse

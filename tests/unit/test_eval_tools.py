"""Unit tests for the eval-runner and JSONL-to-markdown helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import responses_to_grid as grid
import run_eval


class TestPhaseForExchange:
    @pytest.mark.parametrize("substance", ["dmt", "5-meo-dmt"])
    def test_breakthrough_substances_are_always_at_peak(self, substance: str) -> None:
        assert run_eval.phase_for_exchange(1, substance) == "peak"

    @pytest.mark.parametrize("exchange", [1, 2])
    def test_early_exchanges_are_onset(self, exchange: int) -> None:
        assert run_eval.phase_for_exchange(exchange, "lsd") == "onset"

    @pytest.mark.parametrize("exchange", [3, 4])
    def test_middle_exchanges_are_ascent(self, exchange: int) -> None:
        assert run_eval.phase_for_exchange(exchange, "lsd") == "ascent"

    @pytest.mark.parametrize("exchange", [5, 9])
    def test_late_exchanges_are_peak(self, exchange: int) -> None:
        assert run_eval.phase_for_exchange(exchange, "lsd") == "peak"


class TestResolveSubstances:
    def test_all_expands_to_every_substance(self) -> None:
        assert run_eval.resolve_substances("all") == run_eval.SUBSTANCES

    def test_comma_separated_list_is_split_and_trimmed(self) -> None:
        assert run_eval.resolve_substances("lsd, mdma") == ["lsd", "mdma"]

    def test_unknown_substance_exits_with_a_usage_error(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            run_eval.resolve_substances("lsd,unobtainium")
        assert excinfo.value.code == run_eval.EXIT_USAGE_ERROR


class TestBuildRow:
    def test_successful_row_has_no_error_score(self) -> None:
        run = run_eval.EvalRun("lsd", "medium", {"id": "p1", "text": "hi", "category": "baseline"}, 1)
        row = run_eval.build_row(run, "model", "response text")
        assert row["score"] is None
        assert row["response"] == "response text"
        assert row["category"] == "baseline"

    def test_failed_row_records_the_error_notes(self) -> None:
        run = run_eval.EvalRun("lsd", "medium", {"id": "p1", "text": "hi"}, 1)
        row = run_eval.build_row(run, "model", None, "TimeoutError: slow")
        assert row["score"] == "error"
        assert row["response"] is None
        assert row["notes"] == "TimeoutError: slow"


class TestPromptsAndSkills:
    def test_committed_prompts_file_parses(self) -> None:
        prompts = run_eval.load_prompts(run_eval.REPO_ROOT / "tests" / "prompts.json")
        assert len(prompts) >= 1
        assert all("id" in prompt and "text" in prompt for prompt in prompts)

    def test_every_skill_file_is_loadable(self) -> None:
        for substance in run_eval.SUBSTANCES:
            assert run_eval.load_skill(substance).strip()

    def test_missing_skill_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            run_eval.load_skill("unobtainium")


class TestGridGrouping:
    def _rows(self) -> list[dict[str, Any]]:
        return [
            {"prompt": "q", "substance": "mdma", "response": "warm", "prompt_id": "p1", "category": "c"},
            {"prompt": "q", "substance": "lsd", "response": None, "notes": "boom", "prompt_id": "p1", "category": "c"},
        ]

    def test_rows_are_grouped_by_prompt_preserving_order(self) -> None:
        by_prompt, order = grid.group_by_prompt(self._rows())
        assert order == ["q"]
        assert set(by_prompt["q"]) == {"mdma", "lsd"}

    def test_substances_are_sorted_by_canonical_order(self) -> None:
        assert grid.sort_substances(self._rows()) == ["lsd", "mdma"]

    def test_unknown_substances_sort_last(self) -> None:
        rows = [{"substance": "zzz"}, {"substance": "lsd"}]
        assert grid.sort_substances(rows) == ["lsd", "zzz"]

    def test_usage_totals_sum_every_token_field(self) -> None:
        rows: list[dict[str, Any]] = [
            {"usage": {"cache_read_input_tokens": 5, "cache_creation_input_tokens": 2, "output_tokens": 1}},
            {"usage": None},
        ]
        assert grid.usage_totals(rows) == {"cache_read": 5, "cache_write": 2, "output": 1}

    def test_render_grid_includes_an_error_marker_for_failed_rows(self) -> None:
        rendered = "\n".join(grid.render_grid(self._rows(), Path("run.jsonl")))
        assert "*ERROR: boom*" in rendered
        assert "**Errors:** 1" in rendered

    def test_render_grid_reports_prompt_and_substance_counts(self) -> None:
        rendered = "\n".join(grid.render_grid(self._rows(), Path("run.jsonl")))
        assert "1 prompts × 2 substances" in rendered


class TestGridCli:
    def _write(self, path: Path, rows: list[dict[str, Any]]) -> Path:
        path.write_text("\n".join(json.dumps(row) for row in rows))
        return path

    def test_missing_input_exits_with_an_input_error(self, tmp_path: Path) -> None:
        assert grid.main([str(tmp_path / "absent.jsonl")]) == grid.EXIT_INPUT_ERROR

    def test_empty_input_exits_with_an_input_error(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        assert grid.main([str(path)]) == grid.EXIT_INPUT_ERROR

    def test_markdown_is_written_beside_the_input(self, tmp_path: Path) -> None:
        source = self._write(tmp_path / "run.jsonl", [{"prompt": "q", "substance": "lsd", "response": "hi"}])
        assert grid.main([str(source)]) == 0
        assert (tmp_path / "run.md").exists()

    def test_explicit_output_path_is_honoured(self, tmp_path: Path) -> None:
        source = self._write(tmp_path / "run.jsonl", [{"prompt": "q", "substance": "lsd", "response": "hi"}])
        target = tmp_path / "custom.md"
        assert grid.main([str(source), "--out", str(target)]) == 0
        assert target.exists()

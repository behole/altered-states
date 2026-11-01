"""Eval grid payload (VAL-SITE-014) — offline derivation tests.

The payload is a pure function of the two data dirs: the historical
same-prompt captures (``experiments/same-prompt/output/*.md``, run tagged by
its ``> Run:`` header) and real-run JSONL response sets
(``tests/responses/*.jsonl``, model field per row). These tests pin the
invariants the contract asserts:

- every grid entry carries prompt, substance, response text, and a run/model
  tag sourced from the underlying artifact,
- a prompt's grid carries ALL runs that produced data for it,
- ≥ 2 distinct run/model tags exist overall (historical corpus + DeepSeek),
- dry-run rows never publish, empty text/model never publish,
- the derivation is deterministic (identical JSON across calls) and reacts to
  its inputs.

Template wiring canaries pin the emitted markup attributes the client JS
reads; the toggle behaviour itself is browser-verified per
``library/user-testing.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import build
from altered_states import feature_flags

MD_CORPUS = """# Same Prompt, Ten Ways
> "What is love?"
> Run: 2026-04-22 22:02 | Model: anthropic/claude-sonnet-4.6
> Per-substance sweet-spot intensity

## 🍄 Psilocybin — *The Teacher*
**Intensity:** MEDIUM (annotation, not part of the answer)

The question has weight I wasn't ready for.

---

## ⚡ LSD — *The Technician*
**Intensity:** MEDIUM

Love is an *optimization function.* Let me trace its edges.

---
"""

MD_UNLABELED = """# Same Prompt, Ten Ways
> "Unlabeled run?"
> (no Run header — a capture that produced no model tag)

## 🍄 Psilocybin — *The Teacher*

An answer that cannot be tagged.

---
"""


@dataclass
class FixtureDirs:
    same_prompt_dir: Path
    responses_dir: Path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _real_row(
    substance: str,
    model: str,
    text: str,
    prompt: str = "What is love?",
    dry_run: bool = False,
) -> dict[str, object]:
    return {
        "prompt": prompt,
        "prompt_id": "test-01",
        "substance": substance,
        "model": model,
        "response": text,
        "dry_run": dry_run,
    }


@pytest.fixture
def fixture_dirs(tmp_path: Path) -> FixtureDirs:
    same_prompt_dir = tmp_path / "corpus"
    same_prompt_dir.mkdir()
    (same_prompt_dir / "what-is-love.md").write_text(MD_CORPUS)
    responses_dir = tmp_path / "responses"
    responses_dir.mkdir()
    _write_jsonl(
        responses_dir / "responses-2026-10-31-deepseek-chat.jsonl",
        [
            _real_row("psilocybin", "deepseek-chat", "That question lands right in the chest."),
            _real_row("lsd", "deepseek-chat", "Something structural is here. Let me find its edges."),
        ],
    )
    return FixtureDirs(same_prompt_dir=same_prompt_dir, responses_dir=responses_dir)


def _payload(fix: FixtureDirs) -> dict[str, Any]:
    return build.build_eval_grid_payload(str(fix.same_prompt_dir), str(fix.responses_dir))


class TestRunTaggingAndCoverage:
    def test_every_entry_carries_prompt_substance_text_and_run_tag(self, fixture_dirs: FixtureDirs) -> None:
        for grid in _payload(fixture_dirs)["grids"]:
            assert grid["prompt"].strip()
            assert grid["promptId"].strip()
            for run in grid["runs"]:
                assert run["runId"].strip()
                assert run["label"].strip()
                assert run["model"].strip()
                for cell in run["substances"]:
                    assert cell["substance"].strip()
                    assert cell["text"].strip()

    def test_prompt_grid_carries_all_runs_producing_data(self, fixture_dirs: FixtureDirs) -> None:
        grids = _payload(fixture_dirs)["grids"]
        love = next(g for g in grids if g["prompt"] == "What is love?")
        run_tags = {(run["runId"], run["model"]) for run in love["runs"]}
        assert run_tags == {
            ("what-is-love", "anthropic/claude-sonnet-4.6"),
            ("responses-2026-10-31-deepseek-chat", "deepseek-chat"),
        }

    def test_at_least_two_distinct_run_model_tags_overall(self, fixture_dirs: FixtureDirs) -> None:
        runs = _payload(fixture_dirs)["runs"]
        assert {run["model"] for run in runs} >= {"anthropic/claude-sonnet-4.6", "deepseek-chat"}

    def test_run_labels_are_derived_from_the_artifacts(self, fixture_dirs: FixtureDirs) -> None:
        grids = _payload(fixture_dirs)["grids"]
        love = next(g for g in grids if g["prompt"] == "What is love?")
        by_id = {run["runId"]: run for run in love["runs"]}
        # md corpus: timestamp + model from the `> Run:` header.
        assert by_id["what-is-love"]["label"] == "2026-04-22 22:02 (anthropic/claude-sonnet-4.6)"
        # JSONL: date · tag from the filename stem, model from the row field.
        assert by_id["responses-2026-10-31-deepseek-chat"]["label"] == "2026-10-31 · deepseek-chat (deepseek-chat)"


class TestDegenerateInputs:
    def test_dry_run_rows_never_publish_a_run(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(
            responses_dir / "responses-2026-01-01-dry.jsonl",
            [_real_row("psilocybin", "deepseek-chat", "dry-run stub", dry_run=True)],
        )
        payload = build.build_eval_grid_payload(str(tmp_path), str(responses_dir))
        assert payload["grids"] == []
        assert payload["runs"] == []

    def test_empty_model_or_empty_text_rows_are_dropped(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(
            responses_dir / "responses-2026-01-02-bad.jsonl",
            [
                _real_row("psilocybin", "", "has text but no model"),
                _real_row("lsd", "deepseek-chat", "   "),
                _real_row("mdma", "deepseek-chat", "Only this survives."),
            ],
        )
        payload = build.build_eval_grid_payload(str(tmp_path), str(responses_dir))
        assert [g["prompt"] for g in payload["grids"]] == ["What is love?"]
        cells = payload["grids"][0]["runs"][0]["substances"]
        assert [c["substance"] for c in cells] == ["mdma"]
        assert cells[0]["text"] == "Only this survives."

    def test_back_to_back_builds_identical_json(self, fixture_dirs: FixtureDirs) -> None:
        p1 = json.dumps(_payload(fixture_dirs), sort_keys=True)
        p2 = json.dumps(_payload(fixture_dirs), sort_keys=True)
        assert p1 == p2

    def test_payload_reacts_its_inputs(self, fixture_dirs: FixtureDirs) -> None:
        before = _payload(fixture_dirs)
        extra = fixture_dirs.responses_dir / "responses-2026-11-01-deepseek-chat.jsonl"
        _write_jsonl(
            extra,
            [_real_row("mdma", "deepseek-chat", "A second run changes the run set.")],
        )
        after = _payload(fixture_dirs)
        grids = after["grids"]
        # Same prompt: the run set grows, not the grid count.
        love = next(g for g in grids if g["prompt"] == "What is love?")
        assert len(love["runs"]) == 3
        # A differently-prompted source file yields a new grid.
        _write_jsonl(
            extra,
            [_real_row("mdma", "deepseek-chat", "New prompt new grid.", prompt="Is this a test?")],
        )
        assert len(_payload(fixture_dirs)["grids"]) == len(before["grids"]) + 1


class TestRealRepoSources:
    def test_committed_sources_yield_two_run_tags_on_the_love_prompt(self) -> None:
        payload = build.build_eval_grid_payload()
        love = next(g for g in payload["grids"] if g["prompt"] == "What is love?")
        models = {run["model"] for run in love["runs"]}
        assert "anthropic/claude-sonnet-4.6" in models
        assert "deepseek-chat" in models
        deepseek = next(run for run in love["runs"] if run["model"] == "deepseek-chat")
        assert {c["substance"] for c in deepseek["substances"]} == {"psilocybin", "lsd", "mdma"}

    def test_payload_holds_at_least_two_distinct_model_tags(self) -> None:
        payload = build.build_eval_grid_payload()
        assert len({run["model"] for run in payload["runs"]}) >= 2

    def test_deepseek_and_corpus_text_traces_to_source_jsonl(self) -> None:
        payload = build.build_eval_grid_payload()
        love = next(g for g in payload["grids"] if g["prompt"] == "What is love?")
        deepseek = next(run for run in love["runs"] if run["model"] == "deepseek-chat")
        source_path = Path(build.BASE) / "tests" / "responses" / "responses-2026-10-31-deepseek-chat-love.jsonl"
        row_texts = [
            str(row["response"])
            for row in (json.loads(line) for line in source_path.read_text().splitlines() if line.strip())
        ]
        for cell in deepseek["substances"]:
            # The published text is a prefix cap of the source row's response.
            assert any(row.startswith(cell["text"][:80]) for row in row_texts), cell["substance"]


class TestRenderAndFlagLifecycle:
    def test_view_compiles_out_when_flag_off(self) -> None:
        assert build.render_eval_grid_view({"runs": [], "grids": [{"runs": [], "grid": 1}]}, False) == ""
        assert build.render_eval_grid_nav(False) == ""

    def test_view_embeds_payload_and_run_toggle_markup(self, fixture_dirs: FixtureDirs) -> None:
        payload = _payload(fixture_dirs)
        view = build.render_eval_grid_view(payload, True)
        assert "__EVAL_GRID_DATA__" not in view
        assert 'id="view-eval_grid"' in view
        assert "data-run-index" in view
        assert 'data-substance="' in view
        assert "data-grid-index" in view

    def test_nav_links_to_eval_grid_view(self) -> None:
        nav = build.render_eval_grid_nav(True)
        assert 'data-view="eval_grid"' in nav
        assert "showView('eval_grid')" in nav
        assert ">Grids</a>" in nav

    def test_eval_grid_flag_is_declared_owned_by_site(self) -> None:
        store = feature_flags.load_flags()
        flag = store.get(build.EVAL_GRID_FLAG)
        assert flag is not None
        assert flag.owner == "site"
        assert flag.enabled is True
        assert build.EVAL_GRID_FLAG in build.SECTION_FLAGS

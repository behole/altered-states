"""Cross-model diff payload (VAL-EVAL-011) — offline derivation tests.

The payload is a pure function of the two data dirs: the historical
same-prompt captures (``experiments/same-prompt/output/*.md``, model named in
the run header) and real-run JSONL response sets (``tests/responses/*.jsonl``,
model field per row). These tests pin the invariants the contract asserts:

- side-by-side entries keyed by a **non-empty, per-side-distinct** model tag,
- no entry ever publishes an empty model tag or empty text,
- dry-run rows are never published,
- the derivation is deterministic (identical JSON across calls) and reacts to
  its inputs (pure function of the data dirs, not hardcoded).

Source-substring spot checks run against the REAL in-repo artifacts so the
test fails loudly if the committed DeepSeek artifact and the historical
corpus stop lining up.
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

Love is an *optimization function.*

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
        responses_dir / "responses-real.jsonl",
        [
            _real_row("psilocybin", "deepseek-chat", "That question lands right in the chest."),
            _real_row("lsd", "deepseek-chat", "Something structural is here. Let me find its edges."),
        ],
    )
    return FixtureDirs(same_prompt_dir=same_prompt_dir, responses_dir=responses_dir)


def _payload(fix: FixtureDirs) -> dict[str, Any]:
    return build.build_cross_model_payload(str(fix.same_prompt_dir), str(fix.responses_dir))


class TestPairingAndTags:
    def test_one_prompt_groups_two_distinct_model_sides(self, fixture_dirs: FixtureDirs) -> None:
        pairs = _payload(fixture_dirs)["pairs"]
        assert len(pairs) == 1
        pair = pairs[0]
        assert pair["prompt"] == "What is love?"
        models = [resp["model"] for resp in pair["responses"]]
        assert models == sorted(models)
        assert models == ["anthropic/claude-sonnet-4.6", "deepseek-chat"]
        assert len(set(models)) == 2

    def test_models_column_order_is_sorted(self, fixture_dirs: FixtureDirs) -> None:
        pair = _payload(fixture_dirs)["pairs"][0]
        assert pair["models"] == ["anthropic/claude-sonnet-4.6", "deepseek-chat"]

    def test_every_entry_has_nonempty_model_and_text(self, fixture_dirs: FixtureDirs) -> None:
        for pair in _payload(fixture_dirs)["pairs"]:
            for resp in pair["responses"]:
                assert resp["model"].strip()
                for cell in resp["substances"]:
                    assert cell["substance"].strip()
                    assert cell["text"].strip()

    def test_intensity_annotation_is_not_published_as_response(self, fixture_dirs: FixtureDirs) -> None:
        pair = _payload(fixture_dirs)["pairs"][0]
        deepseek = [r for r in pair["responses"] if r["model"] == "antic/should-not-exist"]
        claude_side = next(r for r in pair["responses"] if r["model"] == "anthropic/claude-sonnet-4.6")
        cell = next(c for c in claude_side["substances"] if c["substance"] == "psilocybin")
        assert "Intensity" not in cell["text"]
        assert cell["text"].startswith("The question has weight")
        assert isinstance(deepseek, list)


class TestDegenerateInputs:
    def test_dry_run_rows_are_never_published(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(
            responses_dir / "dry.jsonl",
            [_real_row("psilocybin", "deepseek-chat", "dry-run stub", dry_run=True)],
        )
        payload = build.build_cross_model_payload(str(tmp_path), str(responses_dir))
        assert payload["pairs"] == []

    def test_empty_model_or_empty_text_rows_are_dropped(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(
            responses_dir / "bad.jsonl",
            [
                _real_row("psilocybin", "", "has text but no model"),
                _real_row("lsd", "deepseek-chat", "   "),
                _real_row("mdma", "deepseek-chat", "should not stop the next source"),
            ],
        )
        payload = build.build_cross_model_payload(str(tmp_path), str(responses_dir))
        assert payload["pairs"] == []

    def test_single_model_prompt_is_not_published_as_a_pair(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(responses_dir / "one.jsonl", [_real_row("mdma", "deepseek-chat", "Only one side.")])
        payload = build.build_cross_model_payload(str(tmp_path), str(responses_dir))
        assert payload["pairs"] == []


class TestPurityAndDeterminism:
    def test_two_calls_identical_json(self, fixture_dirs: FixtureDirs) -> None:
        first, second = _payload(fixture_dirs), _payload(fixture_dirs)
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)

    def test_payload_reacts_to_its_inputs(self, fixture_dirs: FixtureDirs) -> None:
        baseline = json.dumps(_payload(fixture_dirs), sort_keys=True)
        _write_jsonl(
            fixture_dirs.responses_dir / "responses-later.jsonl",
            [_real_row("mdma", "deepseek-reasoner", "A third side arrives.")],
        )
        changed = _payload(fixture_dirs)
        assert json.dumps(changed, sort_keys=True) != baseline
        ids = {r["model"] for r in changed["pairs"][0]["responses"]}
        assert "deepseek-reasoner" in ids

    def test_entry_text_is_capped_at_the_documented_limit(self, tmp_path: Path) -> None:
        responses_dir = tmp_path / "responses"
        responses_dir.mkdir()
        _write_jsonl(responses_dir / "long.jsonl", [_real_row("mdma", "deepseek-chat", "x" * 5000)])
        weird = tmp_path / "corpus"
        weird.mkdir()
        (weird / "p.md").write_text(
            MD_CORPUS.replace("anthropic/claude-sonnet-4.6", "model-b").replace("Psilocybin", "Mdma")
        )
        pair = build.build_cross_model_payload(str(weird), str(responses_dir))["pairs"][0]
        long_cell = next(
            r for resp in pair["responses"] if resp["model"] == "deepseek-chat" for r in resp["substances"]
        )
        assert long_cell["text"] == "x" * build.MAX_CROSS_MODEL_TEXT_CHARS


class TestRealRepoSources:
    """Spot checks against the committed artifacts (offline)."""

    def test_real_sources_pair_deepseek_with_historical_corpus(self) -> None:
        payload = build.build_cross_model_payload()
        pairs = payload["pairs"]
        love = next(p for p in pairs if p["promptId"] == "what-is-love")
        models = {r["model"] for r in love["responses"]}
        assert "deepseek-chat" in models
        assert models - {"deepseek-chat"}  # at least one historical side
        for r in love["responses"]:
            assert r["model"].strip()

    def test_deepseek_text_substring_exists_in_source_jsonl(self) -> None:
        payload = build.build_cross_model_payload()
        love = next(p for p in payload["pairs"] if p["promptId"] == "what-is-love")
        deepseek = next(r for r in love["responses"] if r["model"] == "deepseek-chat")
        responses: list[str] = []
        for artifact in sorted(Path(build.RESPONSES_DIR).glob("*.jsonl")):
            for line in artifact.read_text().splitlines():
                if line.strip():
                    responses.append(str(json.loads(line).get("response") or ""))
        combined_prefixes = "\n".join(r[:200] for r in responses)
        assert deepseek["substances"], "DeepSeek side must carry substances"
        for cell in deepseek["substances"]:
            head = cell["text"][:120]
            assert head.strip() and head in combined_prefixes


class TestRenderAndFlagLifecycle:
    def test_view_compiles_out_when_flag_off(self) -> None:
        assert build.render_cross_model_view({"pairs": []}, enabled=False) == ""
        assert build.render_cross_model_nav(enabled=False) == ""

    def test_view_embeds_payload_and_model_tag_markup(self, fixture_dirs: FixtureDirs) -> None:
        html = build.render_cross_model_view(_payload(fixture_dirs), enabled=True)
        assert "view-cross_model" in html
        assert "cm-model-tag" in html
        assert "deepseek-chat" in html
        assert "anthropic/claude-sonnet-4.6" in html
        assert not html.strip().endswith("__CROSS_MODEL_DATA__")

    def test_nav_links_to_cross_model_view(self) -> None:
        nav = build.render_cross_model_nav(enabled=True)
        assert 'data-view="cross_model"' in nav

    def test_cross_model_flag_is_declared_owned_by_eval(self) -> None:
        store = feature_flags.load_flags()
        assert build.CROSS_MODEL_FLAG in store.names
        flag = store.get(build.CROSS_MODEL_FLAG)
        assert flag is not None
        assert flag.owner == "eval"
        assert flag.enabled is True
        assert flag.rollout_percentage == 100
        assert not flag.expired()
        assert build.CROSS_MODEL_FLAG in build.SECTION_FLAGS

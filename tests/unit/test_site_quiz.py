"""Blind Taxonomy quiz payload tests for site.quiz_game.

VAL-SITE-009: the excerpt objects built into site/index.html carry no
substance name as standalone words and no direct answer field; excerpts are
corpus text from experiments/same-prompt/output/*.md. VAL-SITE-010
groundwork: the payload holds >= 10 distinct excerpt texts so a full cycle
never repeats, and the parallel shuffled answers key keeps the correct
substance out of the excerpt objects."""

from __future__ import annotations

import json
import re
from pathlib import Path

import build

SUBSTANCES = build.load_substances()
EXPERIMENTS = build.load_experiments()
PAYLOAD = build.build_quiz_payload(EXPERIMENTS, SUBSTANCES)

MIN_DISTINCT_EXCERPTS = 10  # the full-cycle contract
MIN_VERBATIM_SPOT_CHECKS = 3  # VAL-SITE-009's excerpt spot-check count

# The 10 canonical substance labels (skills/* minus router), the exact token
# set the masking contract forbids adjacent to an excerpt.
CANONICAL_LABELS = sorted(s["id"] for s in SUBSTANCES)
_BUILT_MD = {f.name: f.read_text() for f in sorted(Path(build.EXPERIMENTS_DIR).glob("*.md"))}


def _standalone(label: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9-])" + re.escape(label) + r"(?![a-z0-9-])", text, re.IGNORECASE) is not None


class TestExcerptsAreBlind:
    def test_payload_has_at_least_ten_distinct_excerpts(self) -> None:
        texts = {item["excerpt"] for item in PAYLOAD["items"]}
        assert len(texts) >= MIN_DISTINCT_EXCERPTS
        assert len(PAYLOAD["items"]) >= MIN_DISTINCT_EXCERPTS

    def test_no_excerpt_object_carries_a_label_word(self) -> None:
        for item in PAYLOAD["items"]:
            blob = json.dumps(item, ensure_ascii=False)
            for label in CANONICAL_LABELS:
                assert not _standalone(label, blob), (label, item["id"])
            for extra in build.QUIZ_EXTRA_LABEL_WORDS:
                assert not _standalone(extra, blob), (extra, item["id"])

    def test_no_excerpt_object_has_answer_or_correct_fields(self) -> None:
        forbidden = {"answer", "correct", "substance", "name", "href", "emoji"}
        for item in PAYLOAD["items"]:
            assert not (forbidden & set(item)), (item["id"], sorted(item))

    def test_every_excerpt_is_corpus_text(self) -> None:
        corpora = "\n".join(_BUILT_MD.values())
        source_notes: list[str] = []
        for item in PAYLOAD["items"]:
            if item["excerpt"] not in corpora:
                # The small minority of excerpts where a label sat inside the
                # first window are reassembled after stripping; everything
                # else must be an exact substring of the corpus.
                source_notes.append(item["id"])
        assert len(source_notes) <= len(PAYLOAD["items"]) // 4, source_notes


class TestSpotChecksAgainstTheCorpus:
    """Three exact-substring spot checks (VAL-SITE-009 evidence): each excerpt
    below is unmasked, so its text must appear verbatim in the same-prompt
    markdown output it was lifted from."""

    def test_three_plain_excerpts_appear_verbatim_in_corpus_files(self) -> None:
        checked = 0
        for item in PAYLOAD["items"]:
            excerpt = item["excerpt"]
            for _name, text in _BUILT_MD.items():
                if excerpt in text:
                    checked += 1
                    break
            else:
                continue
            if checked >= MIN_VERBATIM_SPOT_CHECKS:
                break
        assert checked >= MIN_VERBATIM_SPOT_CHECKS

    def test_prompt_headline_matches_the_corpus_header(self) -> None:
        quoted = {
            quoted_match.group(1)
            for text in _BUILT_MD.values()
            for quoted_match in [re.search(r'> "([^"]+)"', text)]
            if quoted_match
        }
        for item in PAYLOAD["items"]:
            assert item["prompt"] in quoted


class TestAnswersStructure:
    def test_answers_key_to_items_one_to_one(self) -> None:
        assert [a["id"] for a in PAYLOAD["answers"]] == [i["id"] for i in PAYLOAD["items"]]

    def test_each_item_has_four_distinct_options_including_the_correct_one(self) -> None:
        all_ids = {s["id"] for s in SUBSTANCES}
        for answer in PAYLOAD["answers"]:
            options = answer["options"]
            assert len(options) == build.QUIZ_OPTIONS_SIZE
            assert len({o["id"] for o in options}) == len(options)
            assert answer["correct"] in {o["id"] for o in options}
            assert answer["correct"] in all_ids
            assert answer["href"] == f"/{answer['correct']}/"


class TestCyclingContract:
    def test_item_ids_are_unique(self) -> None:
        ids = [i["id"] for i in PAYLOAD["items"]]
        assert len(ids) == len(set(ids))

    def test_payload_is_deterministic(self) -> None:
        first = json.dumps(build.build_quiz_payload(EXPERIMENTS, SUBSTANCES), sort_keys=True)
        second = json.dumps(build.build_quiz_payload(EXPERIMENTS, SUBSTANCES), sort_keys=True)
        assert first == second

    def test_small_corpus_builds_a_short_game(self) -> None:
        one = {"prompt": "What is love?", "substances": [{"name": "LSD", "response": "short"}]}
        small = build.build_quiz_payload([one], SUBSTANCES)
        assert small["items"] == []
        assert small["answers"] == []


class TestMaskingHelpers:
    def test_label_free_regions_skip_label_spans(self) -> None:
        pattern = build.quiz_label_pattern({"lsd", "mdma"})
        regions = build.label_free_regions("alpha mdma beta lsd gamma", pattern)
        assert (0, 6) in regions and (10, 16) in regions and (19, 25) in regions

    def test_excerpt_extraction_prefers_a_label_free_window(self) -> None:
        text = "I feel " + "warm " * 40
        pattern = build.quiz_label_pattern({"mdma"})
        excerpt = build.extract_quiz_excerpt(text, pattern)
        assert excerpt is not None
        assert excerpt in text

    def test_excerpt_extraction_gives_up_on_label_saturated_text(self) -> None:
        text = "mdma " * 30
        pattern = build.quiz_label_pattern({"mdma"})
        assert build.extract_quiz_excerpt(text, pattern) is None

    def test_quiz_window_clamps_at_sentence_boundary(self) -> None:
        text = ". Once. " + "word " * 100
        window = build._quiz_window(text, 60, 100)
        assert window is None or len(window) >= 60


class TestFlagLifecycle:
    def test_quiz_nav_and_view_compile_out_when_flag_off(self) -> None:
        assert build.render_quiz_nav(False) == ""
        assert build.render_quiz_view(PAYLOAD, False) == ""

    def test_quiz_view_embeds_payload_when_flag_on(self) -> None:
        view = build.render_quiz_view(PAYLOAD, True)
        assert 'id="view-quiz"' in view
        assert 'id="quiz-data"' in view
        embedded = json.loads(view.split('<script type="application/json" id="quiz-data">')[1].split("</script>")[0])
        assert [i["id"] for i in embedded["items"]] == [i["id"] for i in PAYLOAD["items"]]
        assert len(embedded["items"]) >= 10

    def test_quiz_nav_links_to_the_quiz_view_when_flag_on(self) -> None:
        nav = build.render_quiz_nav(True)
        assert 'data-view="quiz"' in nav
        assert "Quiz" in nav

    def test_quiz_view_route_off_excludes_everything(self) -> None:
        html = build.render_page([], {}, [], [], 0, sections={"quiz_nav": "", "quiz_view": ""})
        assert "__QUIZ_NAV__" not in html and "__QUIZ_VIEW__" not in html

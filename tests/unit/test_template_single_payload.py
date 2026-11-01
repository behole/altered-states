"""Single-payload guarantee for section templates (site.quiz_game,
site.arc_timeline, site.diff_view, site.journal_dashboards).

Scrutiny fix: each SPA section template embeds its own ``__X_DATA__`` token
exactly once, inside the payload script tag. A token in an explanatory HTML
comment would make build.py's global ``.replace()`` duplicate a multi-KB
payload as plain text inside the comment of the built page.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import build

SITE = Path(build.BASE) / "site"

TOKEN_RENDER_CASES: tuple[tuple[str, str, Any], ...] = (
    ("arc.template.html", "__ARC_DATA__", [{"id": "payload-a"}]),
    ("diff.template.html", "__DIFF_DATA__", [{"id": "payload-a"}]),
    ("quiz.template.html", "__QUIZ_DATA__", {"items": [1]}),
    ("journal_dashboards.template.html", "__JOURNAL_DATA__", {"axes": ["a"]}),
    ("eval_grid.template.html", "__EVAL_GRID_DATA__", {"grids": []}),
)


@pytest.mark.parametrize(("template_name", "token", "payload"), TOKEN_RENDER_CASES)
def test_token_occurs_exactly_once_in_the_template(template_name: str, token: str, payload: Any) -> None:
    template_html = (SITE / template_name).read_text()
    assert template_html.count(token) == 1, (template_name, token)


@pytest.mark.parametrize(("template_name", "token", "payload"), TOKEN_RENDER_CASES)
def test_rendered_view_contains_the_payload_exactly_once(template_name: str, token: str, payload: Any) -> None:
    rendered = _render(template_name, payload)
    assert token not in rendered
    assert rendered.count("unique-payload-marker") == 1, (
        template_name,
        "payload duplicated (probably inside an HTML comment)",
    )


def _render(template_name: str, payload: Any) -> str:
    list_payload: list[dict[str, str]] = [{"id": "payload-a", "json": "unique-payload-marker"}]
    if template_name == "arc.template.html":
        return build.render_arc_view(list_payload, True)
    if template_name == "diff.template.html":
        return build.render_diff_view(list_payload, True)
    if template_name == "quiz.template.html":
        return build.render_quiz_view({"items": ["unique-payload-marker"]}, True)
    if template_name == "eval_grid.template.html":
        return build.render_eval_grid_view({"grids": [{"runs": [], "json": "unique-payload-marker"}]}, True)
    return build.render_journal_view({"axes": ["unique-payload-marker"]}, True)


def test_invalidate_helper_rejects_a_duplicated_token() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build._invalidate_template_marker("x __DIFF_DATA__ y __DIFF_DATA__", "__DIFF_DATA__", "t")

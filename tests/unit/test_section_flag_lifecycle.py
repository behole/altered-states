"""Groundwork tests for the six milestone-2 SITE section flags.

The gated sections themselves land in later features; these tests pin the
lifecycle contract that feature depends on: the flags are declared with a
committing end state (enabled, rollout 100), they are injected into the built
page through ``__FLAGS__``, and the build-time on/off decision is observable
per flag (the "flip-off probe" groundwork).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

import build
from altered_states import feature_flags

NEW_SECTION_FLAGS = (
    "site.substance_pages",
    "site.arc_timeline",
    "site.diff_view",
    "site.quiz_game",
    "site.journal_dashboards",
    "site.eval_grids",
)


def _repo_flag_store() -> feature_flags.FlagStore:
    return feature_flags.load_flags()


class TestNewFlagsAreDeclaredWithCommittedEndState:
    @pytest.mark.parametrize("name", NEW_SECTION_FLAGS)
    def test_flag_declared_enabled_full_rollout_owned_by_site(self, name: str) -> None:
        store = _repo_flag_store()
        assert name in store.names
        flag = store.get(name)
        assert flag is not None
        assert flag.owner == "site"
        assert flag.enabled is True
        assert flag.rollout_percentage == 100

    @pytest.mark.parametrize("name", NEW_SECTION_FLAGS)
    def test_flag_has_a_realistic_review_date(self, name: str) -> None:
        flag = _repo_flag_store().get(name)
        assert flag is not None
        # Still live today, but expires soon enough to force a review.
        assert not flag.expired()
        assert flag.expires_on and int(flag.expires_on.split("-")[0]) in (2026, 2027)

    def test_every_new_flag_is_a_declared_section_flag(self) -> None:
        assert set(NEW_SECTION_FLAGS) <= set(build.SECTION_FLAGS)
        assert set(build.SECTION_FLAGS) <= set(_repo_flag_store().names)


class TestFlagPayloadInjectedThroughPlaceholder:
    def test_rendered_page_contains_a_boolean_for_every_section_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(build, "flags", feature_flags.load_flags())
        template = tmp_path / "tpl.html"
        template.write_text("const FLAGS = __FLAGS__;")
        monkeypatch.setattr(build, "TEMPLATE", str(template))

        html = build.render_page([{"id": "lsd"}], {"lsd": []}, [], [], 0)

        match = re.search(r"const FLAGS = (\{[^}]*\});", html)
        assert match is not None
        payload = json.loads(match.group(1))
        assert set(payload) == set(build.SECTION_FLAGS)
        for name in NEW_SECTION_FLAGS:
            assert payload[name] is True


class TestFlipOffProbeGroundwork:
    @pytest.mark.parametrize("name", NEW_SECTION_FLAGS)
    def test_flag_env_override_decides_the_section_gate(self, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
        env_key = "FLAG_" + name.replace(".", "_").upper()
        monkeypatch.setenv(env_key, "off")
        store = feature_flags.load_flags(environ=dict(os.environ))
        monkeypatch.setattr(build, "flags", store)

        gates = build.enabled_section_flags()

        assert gates[name] is False
        # The other section flags are untouched by the single flag flip.
        expected_without_name = {n: store.is_enabled(n) for n in build.SECTION_FLAGS}
        del expected_without_name[name]
        del gates[name]
        assert gates == expected_without_name

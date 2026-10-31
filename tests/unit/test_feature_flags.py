"""Unit tests for file-backed feature flags, rollout bucketing, and staleness."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from altered_states import feature_flags
from altered_states.feature_flags import (
    BUCKETS,
    Flag,
    FlagStore,
    bucket_for,
    load_flags,
    referenced_names,
    unused_flags,
)


def make_flag(name: str, **overrides: object) -> Flag:
    defaults: dict[str, object] = {"name": name, "enabled": True, "rollout_percentage": 100}
    defaults.update(overrides)
    return Flag(**defaults)  # type: ignore[arg-type]


class TestFlagParsing:
    def test_from_mapping_reads_every_documented_key(self) -> None:
        flag = Flag.from_mapping(
            {
                "name": "site.music_section",
                "enabled": True,
                "rollout_percentage": 25,
                "owner": "site",
                "description": "desc",
                "expires_on": "2027-01-01",
                "allowlist": ["a"],
                "denylist": ["b"],
            }
        )
        assert flag.rollout_percentage == 25
        assert flag.owner == "site"
        assert flag.expires_on == "2027-01-01"
        assert flag.allowlist == ("a",)
        assert flag.denylist == ("b",)

    def test_missing_optional_keys_get_defaults(self) -> None:
        flag = Flag.from_mapping({"name": "site.x"})
        assert flag.enabled is False
        assert flag.rollout_percentage == 0
        assert flag.owner == "unassigned"


class TestEvaluation:
    def test_unknown_flag_is_off(self) -> None:
        assert FlagStore([make_flag("site.a")]).is_enabled("site.does_not_exist") is False

    def test_disabled_flag_is_off_even_at_full_rollout(self) -> None:
        store = FlagStore([make_flag("site.a", enabled=False)])
        assert store.is_enabled("site.a") is False

    def test_full_rollout_is_on_without_a_subject(self) -> None:
        assert FlagStore([make_flag("site.a")]).is_enabled("site.a") is True

    def test_partial_rollout_is_off_without_a_subject(self) -> None:
        assert FlagStore([make_flag("site.a", rollout_percentage=50)]).is_enabled("site.a") is False

    def test_allowlist_overrides_a_partial_rollout(self) -> None:
        store = FlagStore([make_flag("site.a", rollout_percentage=0, allowlist=("vip",))])
        assert store.is_enabled("site.a", "vip") is True

    def test_denylist_overrides_full_rollout(self) -> None:
        store = FlagStore([make_flag("site.a", denylist=("blocked",))])
        assert store.is_enabled("site.a", "blocked") is False

    def test_bucketing_is_deterministic(self) -> None:
        assert bucket_for("site.a", "user-1") == bucket_for("site.a", "user-1")

    def test_bucketing_spreads_subjects_across_the_range(self) -> None:
        buckets = {bucket_for("site.a", f"user-{index}") for index in range(200)}
        assert all(0 <= bucket < BUCKETS for bucket in buckets)
        assert len(buckets) > 20

    def test_bucketing_is_flag_specific(self) -> None:
        assert bucket_for("site.a", "user-1") != bucket_for("site.b", "user-1")

    def test_partial_rollout_admits_roughly_the_configured_share(self) -> None:
        store = FlagStore([make_flag("site.a", rollout_percentage=50)])
        enabled = sum(store.is_enabled("site.a", f"user-{index}") for index in range(400))
        # Deterministic, so assert a wide but meaningful band around 50%.
        assert 140 <= enabled <= 260

    def test_rollout_is_monotonic(self) -> None:
        narrow = FlagStore([make_flag("site.a", rollout_percentage=20)])
        wide = FlagStore([make_flag("site.a", rollout_percentage=80)])
        for index in range(200):
            subject = f"user-{index}"
            if narrow.is_enabled("site.a", subject):
                assert wide.is_enabled("site.a", subject)


class TestEnvOverrides:
    def test_env_can_force_a_flag_on(self) -> None:
        store = FlagStore([make_flag("site.a", enabled=False)]).load_from_env({"FLAG_SITE_A": "on"})
        assert store.is_enabled("site.a") is True

    def test_env_can_force_a_flag_off(self) -> None:
        store = FlagStore([make_flag("site.a")]).load_from_env({"FLAG_SITE_A": "off"})
        assert store.is_enabled("site.a") is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_spellings_enable(self, value: str) -> None:
        store = FlagStore([make_flag("site.a", enabled=False)]).load_from_env({"FLAG_SITE_A": value})
        assert store.is_enabled("site.a") is True

    def test_override_does_not_mutate_the_original_store(self) -> None:
        original = FlagStore([make_flag("site.a", enabled=False)])
        original.load_from_env({"FLAG_SITE_A": "on"})
        assert original.is_enabled("site.a") is False

    def test_env_keys_are_derived_from_the_dotted_name(self) -> None:
        store = FlagStore([make_flag("site.experiment_wheel", enabled=False)]).load_from_env(
            {"FLAG_SITE_EXPERIMENT_WHEEL": "on"}
        )
        assert store.is_enabled("site.experiment_wheel") is True


class TestStaleness:
    def test_flag_without_expiry_never_expires(self) -> None:
        assert make_flag("site.a").expired(date(2099, 1, 1)) is False

    def test_flag_is_expired_on_its_expiry_date(self) -> None:
        flag = make_flag("site.a", expires_on="2026-06-30")
        assert flag.expired(date(2026, 6, 30)) is True

    def test_flag_is_live_before_its_expiry_date(self) -> None:
        flag = make_flag("site.a", expires_on="2026-06-30")
        assert flag.expired(date(2026, 6, 29)) is False

    def test_malformed_expiry_is_treated_as_expired(self) -> None:
        assert make_flag("site.a", expires_on="not-a-date").expired() is True

    def test_store_reports_expired_flags(self) -> None:
        store = FlagStore([make_flag("site.old", expires_on="2020-01-01"), make_flag("site.new")])
        assert [flag.name for flag in store.expired(date(2026, 1, 1))] == ["site.old"]

    def test_unused_flags_are_reported(self, tmp_path: Path) -> None:
        source = tmp_path / "app.py"
        source.write_text("if flags.is_enabled('site.used'):\n    pass\n")
        store = FlagStore([make_flag("site.used"), make_flag("site.dead")])
        assert [flag.name for flag in unused_flags(store, tmp_path)] == ["site.dead"]

    def test_referenced_names_ignores_binary_and_site_directories(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("flag 'site.visible'\n")
        site = tmp_path / "site"
        site.mkdir()
        (site / "index.html").write_text("site.hidden_in_site\n")
        assert referenced_names(tmp_path) == {"site.visible"}


class TestLoading:
    def test_missing_file_yields_an_empty_store(self, tmp_path: Path) -> None:
        store = load_flags(tmp_path / "absent.json", {})
        assert len(store) == 0
        assert store.is_enabled("anything") is False

    def test_file_is_parsed_into_flags(self, flag_file: Path) -> None:
        store = load_flags(flag_file, {})
        assert set(store.names) == {"site.music_section", "site.chat_personas", "site.experiment_wheel"}
        assert store.is_enabled("site.music_section") is True
        assert store.is_enabled("site.chat_personas") is False

    def test_committed_repository_flags_are_well_formed(self) -> None:
        """The checked-in flag file must load and be internally consistent."""
        from altered_states.feature_flags import DEFAULT_FLAG_FILE

        store = load_flags(DEFAULT_FLAG_FILE, {})
        assert len(store) >= 1
        for name in store.names:
            flag = store.get(name)
            assert flag is not None
            assert 0 <= flag.rollout_percentage <= BUCKETS
            assert flag.owner


class TestCli:
    """`python -m altered_states.feature_flags` is the operator entry point."""

    def _write(self, tmp_path: Path, flags: list[dict[str, object]]) -> Path:
        target = tmp_path / "flags.json"
        target.write_text(json.dumps({"flags": flags}))
        return target

    def _scan_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str = "") -> None:
        """Point the unused-flag scan at a scratch tree instead of the repo."""
        monkeypatch.setattr(feature_flags, "REPO_ROOT", tmp_path)
        if source:
            (tmp_path / "consumer.py").write_text(source)

    def test_show_lists_every_flag_with_owner_and_rollout(
        self, flag_file: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._scan_root(flag_file.parent, monkeypatch)
        assert feature_flags.main(["--file", str(flag_file), "show"]) == 0
        out = capsys.readouterr().out
        assert "site.chat_personas" in out
        assert "owner=" in out
        assert "rollout=" in out

    def test_no_subcommand_defaults_to_show(
        self, flag_file: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._scan_root(flag_file.parent, monkeypatch)
        assert feature_flags.main(["--file", str(flag_file)]) == 0
        assert "Declared flags" in capsys.readouterr().out

    def test_show_marks_partial_rollouts_off_when_no_subject_is_given(
        self, flag_file: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._scan_root(flag_file.parent, monkeypatch)
        feature_flags.main(["--file", str(flag_file), "show"])
        out = capsys.readouterr().out
        wheel_line = next(line for line in out.splitlines() if "site.experiment_wheel" in line)
        assert "rollout= 50%" in wheel_line
        assert "off" in wheel_line

    def test_eval_reports_on_for_a_full_rollout(self, flag_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert feature_flags.main(["--file", str(flag_file), "eval", "site.music_section"]) == 0
        assert "-> on" in capsys.readouterr().out

    def test_eval_reports_off_for_a_disabled_flag(self, flag_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert feature_flags.main(["--file", str(flag_file), "eval", "site.chat_personas"]) == 0
        assert "-> off" in capsys.readouterr().out

    def test_eval_honours_a_denylisted_subject(self, flag_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = feature_flags.main(["--file", str(flag_file), "eval", "site.experiment_wheel", "--subject", "blocked"])
        assert code == 0
        assert "-> off" in capsys.readouterr().out

    def test_eval_honours_an_allowlisted_subject(self, flag_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = feature_flags.main(["--file", str(flag_file), "eval", "site.experiment_wheel", "--subject", "vip"])
        assert code == 0
        assert "-> on" in capsys.readouterr().out

    def test_check_passes_when_a_flag_is_referenced_and_unexpired(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = self._write(
            tmp_path,
            [{"name": "test.live_flag", "enabled": True, "owner": "o", "description": "d"}],
        )
        self._scan_root(tmp_path, monkeypatch, source='flags.is_enabled("test.live_flag")')

        assert feature_flags.main(["--file", str(target), "check"]) == 0
        assert "EXPIRED" not in capsys.readouterr().out

    def test_check_fails_and_names_an_expired_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = self._write(
            tmp_path,
            [{"name": "test.old_flag", "enabled": True, "owner": "o", "expires_on": "2020-01-01"}],
        )
        self._scan_root(tmp_path, monkeypatch, source='flags.is_enabled("test.old_flag")')

        assert feature_flags.main(["--file", str(target), "check"]) == 1
        assert "EXPIRED: test.old_flag" in capsys.readouterr().out

    def test_check_fails_and_names_an_unreferenced_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = self._write(tmp_path, [{"name": "totally.unreferenced", "enabled": True, "owner": "o"}])
        self._scan_root(tmp_path, monkeypatch)

        assert feature_flags.main(["--file", str(target), "check"]) == 1
        assert "DEAD: totally.unreferenced" in capsys.readouterr().out

    def test_check_with_no_flags_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = self._write(tmp_path, [])
        self._scan_root(tmp_path, monkeypatch)
        assert feature_flags.main(["--file", str(target), "check"]) == 0
        assert "Declared flags (0)" in capsys.readouterr().out


class TestReferenceScanning:
    def test_literals_in_python_files_are_collected(self, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text('if flags.is_enabled("site.music_section"):\n    pass\n')
        assert "site.music_section" in feature_flags.referenced_names(tmp_path)

    def test_literals_in_html_files_are_collected(self, tmp_path: Path) -> None:
        (tmp_path / "page.html").write_text("flagOn('site.chat_personas')")
        assert "site.chat_personas" in feature_flags.referenced_names(tmp_path)

    def test_built_site_output_is_excluded(self, tmp_path: Path) -> None:
        site = tmp_path / "site"
        site.mkdir()
        (site / "index.html").write_text("flagOn('site.experiments_gallery')")
        assert feature_flags.referenced_names(tmp_path) == set()

    def test_non_source_files_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("site.music_section")
        assert feature_flags.referenced_names(tmp_path) == set()

    def test_unreadable_file_is_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "broken.py").write_bytes(b"\xff\xfe\x00bad")
        assert isinstance(feature_flags.referenced_names(tmp_path), set)


class TestCommittedFlags:
    def test_every_committed_flag_is_referenced_by_source(self) -> None:
        store = feature_flags.load_flags(feature_flags.DEFAULT_FLAG_FILE)
        assert feature_flags.unused_flags(store) == []

    def test_no_committed_flag_is_past_its_expiry(self) -> None:
        store = feature_flags.load_flags(feature_flags.DEFAULT_FLAG_FILE)
        assert [flag.name for flag in store.expired()] == []

    def test_every_committed_flag_names_an_owner(self) -> None:
        store = feature_flags.load_flags(feature_flags.DEFAULT_FLAG_FILE)
        for name in store.names:
            flag = store.get(name)
            assert flag is not None
            assert flag.owner, f"{name} needs an owner"
            assert flag.description, f"{name} needs a description"

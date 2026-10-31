"""Unit tests for the label taxonomy and its reconciler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import sync_labels
from sync_labels import DesiredLabel, build_plan, desired_labels, is_managed

pytest.importorskip("yaml")

CONFIG = {
    "keep": ["good first issue"],
    "managed_prefixes": ["area:", "priority:"],
    "managed_names": ["bug", "enhancement"],
    "labels": [
        {"name": "bug", "color": "d73a4a", "description": "Something is broken"},
        {"name": "area:site", "color": "bfd4f2", "description": "Generated site"},
        {"name": "priority:high", "color": "d93f0b", "description": "Blocks the release"},
    ],
}


class TestManifest:
    def test_parsing_rejects_a_blank_name(self) -> None:
        with pytest.raises(ValueError):
            DesiredLabel.from_mapping({"name": "  "})

    def test_leading_hash_is_stripped_from_the_colour(self) -> None:
        assert DesiredLabel.from_mapping({"name": "x", "color": "#AABBCC"}).color == "AABBCC"

    def test_missing_colour_falls_back_to_grey(self) -> None:
        assert DesiredLabel.from_mapping({"name": "x"}).color == "ededed"

    def test_duplicate_names_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            desired_labels({"labels": [{"name": "x"}, {"name": "x"}]})

    def test_committed_taxonomy_parses_without_duplicates(self) -> None:
        config = sync_labels._load_yaml(sync_labels.LABELS_FILE)
        assert len(desired_labels(config)) >= 20

    def test_every_committed_label_has_a_description(self) -> None:
        config = sync_labels._load_yaml(sync_labels.LABELS_FILE)
        missing = [label.name for label in desired_labels(config) if not label.description]
        assert missing == []

    def test_every_committed_label_has_a_valid_colour(self) -> None:
        config = sync_labels._load_yaml(sync_labels.LABELS_FILE)
        for label in desired_labels(config):
            assert len(label.color) == 6
            assert all(char in "0123456789abcdefABCDEF" for char in label.color), label.name

    def test_taxonomy_covers_the_surfaces_in_the_repo(self) -> None:
        names = {label.name for label in desired_labels(sync_labels._load_yaml(sync_labels.LABELS_FILE))}
        assert {"bug", "enhancement", "dependencies", "security"} <= names
        assert {"area:site", "area:build", "area:ci"} <= names
        assert {"priority:critical", "priority:high"} <= names


class TestOwnership:
    def test_kept_labels_are_never_managed(self) -> None:
        assert is_managed("good first issue", CONFIG) is False

    def test_declared_names_are_managed(self) -> None:
        assert is_managed("bug", CONFIG) is True

    def test_prefixes_are_managed(self) -> None:
        assert is_managed("area:whatever", CONFIG) is True
        assert is_managed("priority:low", CONFIG) is True

    def test_unrelated_labels_are_left_alone(self) -> None:
        assert is_managed("question-from-a-visitor", CONFIG) is False


class TestPlan:
    def test_absent_labels_are_created(self) -> None:
        plan = build_plan(CONFIG, [])
        assert {label.name for label in plan.create} == {"bug", "area:site", "priority:high"}
        assert plan.delete == ()
        assert plan.is_empty is False

    def test_identical_labels_are_unchanged(self) -> None:
        existing = [{"name": "bug", "color": "d73a4a", "description": "Something is broken"}]
        plan = build_plan(CONFIG, existing)
        assert [label.name for label in plan.update] == []
        assert "bug" in plan.unchanged

    def test_colour_drift_triggers_an_update(self) -> None:
        existing = [{"name": "bug", "color": "000000", "description": "Something is broken"}]
        assert [label.name for label in build_plan(CONFIG, existing).update] == ["bug"]

    def test_description_drift_triggers_an_update(self) -> None:
        existing = [{"name": "bug", "color": "d73a4a", "description": "old"}]
        assert [label.name for label in build_plan(CONFIG, existing).update] == ["bug"]

    def test_managed_label_absent_from_the_file_is_deleted(self) -> None:
        existing = [{"name": "area:gone", "color": "ffffff", "description": "stale"}]
        assert build_plan(CONFIG, existing).delete == ("area:gone",)

    def test_unmanaged_label_is_not_deleted(self) -> None:
        existing = [{"name": "question", "color": "ffffff", "description": ""}]
        assert build_plan(CONFIG, existing).delete == ()

    def test_kept_label_is_not_deleted(self) -> None:
        existing = [{"name": "good first issue", "color": "ffffff", "description": ""}]
        assert build_plan(CONFIG, existing).delete == ()

    def test_plan_is_empty_when_nothing_changes(self) -> None:
        existing = [
            {"name": "bug", "color": "d73a4a", "description": "Something is broken"},
            {"name": "area:site", "color": "bfd4f2", "description": "Generated site"},
            {"name": "priority:high", "color": "d93f0b", "description": "Blocks the release"},
        ]
        plan = build_plan(CONFIG, existing)
        assert plan.is_empty is True
        assert plan.summary().startswith("0 to create")

    def test_deletions_are_sorted(self) -> None:
        existing = [
            {"name": "area:zebra", "color": "ffffff", "description": ""},
            {"name": "area:apple", "color": "ffffff", "description": ""},
        ]
        assert build_plan(CONFIG, existing).delete == ("area:apple", "area:zebra")


class TestCli:
    def _config_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "labels.yml"
        path.write_text(
            "managed_prefixes: ['area:']\n"
            "managed_names: [bug]\n"
            "labels:\n"
            "  - name: bug\n"
            "    color: d73a4a\n"
            "    description: Something is broken\n"
        )
        return path

    def test_dry_run_with_offline_state_changes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        existing = tmp_path / "existing.json"
        existing.write_text(json.dumps([{"name": "area:stale", "color": "ffffff", "description": ""}]))
        code = sync_labels.main(["--file", str(self._config_file(tmp_path)), "--existing", str(existing), "--dry-run"])
        out = capsys.readouterr().out
        assert code == sync_labels.EXIT_OK
        assert "1 to create" in out
        assert "1 to delete" in out
        assert "- area:stale" in out

    def test_missing_manifest_is_a_usage_error(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = sync_labels.main(["--file", str(tmp_path / "absent.yml"), "--dry-run"])
        assert code == sync_labels.EXIT_USAGE
        assert "does not exist" in capsys.readouterr().err

    def test_no_changes_means_no_writes(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        existing = tmp_path / "existing.json"
        existing.write_text(json.dumps([{"name": "bug", "color": "d73a4a", "description": "Something is broken"}]))
        code = sync_labels.main(["--file", str(self._config_file(tmp_path)), "--existing", str(existing)])
        assert code == sync_labels.EXIT_OK
        assert "0 to create, 0 to update, 0 to delete" in capsys.readouterr().out


def test_apply_plan_reports_failures(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A rejected API call must be counted, not swallowed."""
    from subprocess import CompletedProcess

    def failing(*args: str) -> CompletedProcess[str]:
        return CompletedProcess(args, 1, "", "not allowed")

    monkeypatch.setattr(sync_labels, "_gh", failing)
    plan = build_plan(CONFIG, [])
    assert sync_labels.apply_plan(plan) == len(plan.create)
    assert "FAILED" in capsys.readouterr().out


def test_apply_plan_succeeds_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    from subprocess import CompletedProcess

    monkeypatch.setattr(sync_labels, "_gh", lambda *args: CompletedProcess(args, 0, "", ""))
    assert sync_labels.apply_plan(build_plan(CONFIG, [])) == 0

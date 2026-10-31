"""Unit tests for the alert policy and its evaluator."""

from __future__ import annotations

import json
from pathlib import Path

import check_alerts
import pytest
from check_alerts import Alert, evaluate, load_policy, lookup, parse_snapshot, validate_policy

pytest.importorskip("yaml")


def an_alert(**overrides: object) -> Alert:
    base: dict[str, object] = {
        "name": "test-alert",
        "description": "a test alert",
        "signal": "altered_states_build_runs",
        "comparison": ">",
        "threshold": 1.0,
        "severity": "warning",
        "runbook": "runbooks/site-build-failure.md",
        "for_runs": 1,
    }
    base.update(overrides)
    return Alert.from_mapping(base, {})


SNAPSHOT = """\
# HELP altered_states_build_runs Total successful builds
# TYPE altered_states_build_runs counter
altered_states_build_runs 3.0
altered_states_llm_calls{status="ok",substance="lsd"} 10.0
altered_states_llm_calls{status="error",substance="lsd"} 2.0
altered_states_secret_redactions{kind="key"} 1.0
altered_states_secret_redactions{kind="value"} 4.0
altered_states_build_duration_seconds_count 1.0
altered_states_build_duration_seconds_sum 0.25
"""


class TestSnapshotParsing:
    def test_unlabelled_series_is_read(self) -> None:
        assert parse_snapshot(SNAPSHOT)["altered_states_build_runs"] == 3.0

    def test_labels_are_preserved_in_the_key(self) -> None:
        series = parse_snapshot(SNAPSHOT)
        assert series['altered_states_llm_calls{status="error",substance="lsd"}'] == 2.0

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        assert "# HELP" not in "".join(parse_snapshot(SNAPSHOT))

    def test_non_numeric_value_is_skipped(self) -> None:
        assert parse_snapshot("a_metric NaN_but_not\n") == {}

    def test_empty_snapshot_yields_nothing(self) -> None:
        assert parse_snapshot("") == {}


class TestLookup:
    def test_exact_labelled_series_wins(self) -> None:
        assert lookup(parse_snapshot(SNAPSHOT), 'altered_states_llm_calls{status="error",substance="lsd"}') == 2.0

    def test_unlabelled_alert_sums_labelled_variants(self) -> None:
        assert lookup(parse_snapshot(SNAPSHOT), "altered_states_secret_redactions") == 5.0

    def test_absent_signal_returns_none(self) -> None:
        assert lookup(parse_snapshot(SNAPSHOT), "altered_states_missing") is None


class TestEvaluation:
    def test_threshold_respected_for_each_comparison(self) -> None:
        series = {"m": 5.0}
        for comparison, expected in ((">", False), (">=", True), ("<", False), ("<=", True), ("==", True)):
            result = evaluate([an_alert(comparison=comparison, threshold=5.0, signal="m")], series, {})[0]
            assert result.fires is expected, comparison

    def test_equal_value_is_not_greater(self) -> None:
        result = evaluate([an_alert(comparison=">", threshold=3.0)], {"altered_states_build_runs": 3.0}, {})[0]
        assert result.fires is False

    def test_absent_signal_fires_a_less_than_alert(self) -> None:
        result = evaluate([an_alert(comparison="<", threshold=1.0)], {}, {})[0]
        assert result.fires is True
        assert "absent" in result.description

    def test_absent_signal_does_not_fire_a_greater_than_alert(self) -> None:
        result = evaluate([an_alert(comparison=">", threshold=0.0)], {}, {})[0]
        assert result.fires is False

    def test_for_runs_requires_consecutive_evaluations(self) -> None:
        alert = an_alert(comparison=">", threshold=1.0, for_runs=2)
        series = {"altered_states_build_runs": 5.0}

        first = evaluate([alert], series, {})[0]
        second = evaluate([alert], series, {alert.name: first.consecutive})[0]

        assert first.fires is False
        assert second.fires is True

    def test_a_clean_sample_resets_the_counter(self) -> None:
        alert = an_alert(comparison=">", threshold=10.0, for_runs=2)
        result = evaluate([alert], {"altered_states_build_runs": 1.0}, {alert.name: 5})[0]
        assert result.consecutive == 0
        assert result.fires is False

    def test_state_carries_only_firing_alerts(self) -> None:
        alerts = [
            an_alert(name="hot", comparison=">", threshold=1.0),
            an_alert(name="cold", comparison=">", threshold=100.0),
        ]
        results = evaluate(alerts, {"altered_states_build_runs": 5.0}, {})
        assert set(check_alerts.next_state(results)) == {"hot"}


class TestPolicyValidation:
    def test_committed_policy_is_valid(self) -> None:
        assert validate_policy(load_policy(check_alerts.POLICY_FILE)) == []

    def test_missing_runbook_is_rejected(self) -> None:
        problems = validate_policy([an_alert(runbook="")])
        assert any("no runbook" in problem for problem in problems)

    def test_nonexistent_runbook_is_rejected(self) -> None:
        problems = validate_policy([an_alert(runbook="runbooks/nope.md")])
        assert any("does not exist" in problem for problem in problems)

    def test_unknown_severity_is_rejected(self) -> None:
        problems = validate_policy([an_alert(severity="page-someone")])
        assert any("severity" in problem for problem in problems)

    def test_unknown_comparison_is_rejected(self) -> None:
        problems = validate_policy([an_alert(comparison="=>")])
        assert any("comparison" in problem for problem in problems)

    def test_zero_for_runs_is_rejected(self) -> None:
        problems = validate_policy([an_alert(for_runs=0)])
        assert any("for_runs" in problem for problem in problems)

    def test_duplicate_names_are_rejected(self) -> None:
        problems = validate_policy([an_alert(), an_alert()])
        assert any("duplicate" in problem for problem in problems)

    def test_missing_description_is_rejected(self) -> None:
        assert any("no description" in problem for problem in validate_policy([an_alert(description="")]))

    def test_every_committed_alert_has_a_runbook_on_disk(self) -> None:
        for alert in load_policy(check_alerts.POLICY_FILE):
            assert (check_alerts.REPO_ROOT / alert.runbook).is_file()

    def test_committed_policy_covers_build_and_lab_failure(self) -> None:
        names = {alert.name for alert in load_policy(check_alerts.POLICY_FILE)}
        assert {"build-not-running", "llm-errors", "credential-leak-detected"} <= names


class TestCli:
    def _snapshot(self, tmp_path: Path, body: str = SNAPSHOT) -> Path:
        path = tmp_path / "metrics.prom"
        path.write_text(body)
        return path

    def test_validate_only_passes_on_the_committed_policy(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert check_alerts.main(["--validate-only"]) == check_alerts.EXIT_OK
        assert "every one with a runbook" in capsys.readouterr().out

    def test_healthy_snapshot_exits_zero(self, tmp_path: Path) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "alerts:\n"
            "  - name: build-ran\n"
            "    description: d\n"
            "    signal: altered_states_build_runs\n"
            "    comparison: '>'\n"
            "    threshold: 100\n"
            "    severity: critical\n"
            "    runbook: runbooks/site-build-failure.md\n"
        )
        assert check_alerts.main(["--policy", str(policy), "--snapshot", str(self._snapshot(tmp_path))]) == 0

    def test_firing_critical_alert_exits_one(self, tmp_path: Path) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "alerts:\n"
            "  - name: build-ran\n"
            "    description: d\n"
            "    signal: altered_states_build_runs\n"
            "    comparison: '>'\n"
            "    threshold: 1\n"
            "    severity: critical\n"
            "    runbook: runbooks/site-build-failure.md\n"
        )
        code = check_alerts.main(["--policy", str(policy), "--snapshot", str(self._snapshot(tmp_path))])
        assert code == check_alerts.EXIT_FIRING

    def test_firing_warning_alert_exits_zero(self, tmp_path: Path) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "alerts:\n"
            "  - name: build-ran\n"
            "    description: d\n"
            "    signal: altered_states_build_runs\n"
            "    comparison: '>'\n"
            "    threshold: 1\n"
            "    severity: warning\n"
            "    runbook: runbooks/site-build-failure.md\n"
        )
        assert check_alerts.main(["--policy", str(policy), "--snapshot", str(self._snapshot(tmp_path))]) == 0

    def test_json_format_is_machine_readable(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "alerts:\n"
            "  - name: build-ran\n"
            "    description: d\n"
            "    signal: altered_states_build_runs\n"
            "    comparison: '>'\n"
            "    threshold: 1\n"
            "    severity: warning\n"
            "    runbook: runbooks/site-build-failure.md\n"
        )
        check_alerts.main(["--policy", str(policy), "--snapshot", str(self._snapshot(tmp_path)), "--format", "json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["firing"][0]["name"] == "build-ran"

    def test_state_is_written_after_evaluation(self, tmp_path: Path) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text(
            "alerts:\n"
            "  - name: build-ran\n"
            "    description: d\n"
            "    signal: altered_states_build_runs\n"
            "    comparison: '>'\n"
            "    threshold: 0\n"
            "    severity: warning\n"
            "    runbook: runbooks/site-build-failure.md\n"
        )
        state = tmp_path / "state.json"
        check_alerts.main(["--policy", str(policy), "--snapshot", str(self._snapshot(tmp_path)), "--state", str(state)])
        assert json.loads(state.read_text()) == {"build-ran": 1}

    def test_corrupt_state_file_is_survivable(self, tmp_path: Path) -> None:
        state = tmp_path / "state.json"
        state.write_text("not json")
        assert check_alerts._load_state(state) == {}

    def test_missing_policy_is_a_policy_error(self, tmp_path: Path) -> None:
        assert check_alerts.main(["--policy", str(tmp_path / "absent.yaml")]) == check_alerts.EXIT_POLICY

    def test_malformed_policy_is_a_policy_error(self, tmp_path: Path) -> None:
        policy = tmp_path / "policy.yaml"
        policy.write_text("alerts:\n  - name: broken\n")
        assert check_alerts.main(["--policy", str(policy)]) == check_alerts.EXIT_POLICY

    def test_missing_snapshot_is_a_policy_error(self, tmp_path: Path) -> None:
        assert check_alerts.main(["--snapshot", str(tmp_path / "absent.prom")]) == check_alerts.EXIT_POLICY

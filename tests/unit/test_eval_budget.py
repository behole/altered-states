"""Unit tests for the eval spend guardrails (VAL-EVAL-012, VAL-EVAL-013).

Pure offline: manifests, ledger arithmetic, and the command-list proof that
no CI/verify/hook/test command invokes a runner in real-run mode.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from altered_states import eval_budget

REPO_ROOT = Path(__file__).resolve().parents[2]


def _manifest(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "manifest_id": "abc123",
        "run_kind": "real",
        "model": "deepseek-chat",
        "max_tokens": 8192,
        "max_concurrent_requests": 4,
        "max_requests": 10,
        "num_runs": 5,
        "estimated_cost_per_call_usd": 0.01,
        "estimated_cost_usd": 0.10,
        "total_cap_usd": eval_budget.TOTAL_CAP_USD,
        "command_line": "bin/run_eval.py --substances lsd --out tests/responses/x.jsonl",
    }
    base.update(overrides)
    return base


class TestManifestSchema:
    def test_valid_manifest_passes(self) -> None:
        eval_budget.validate_manifest(_manifest())

    def test_cap_over_five_dollars_is_refused(self) -> None:
        with pytest.raises(eval_budget.ManifestError, match="total_cap_usd exceeds"):
            eval_budget.validate_manifest(_manifest(total_cap_usd=5.01))

    def test_cap_at_exactly_five_dollars_passes(self) -> None:
        eval_budget.validate_manifest(_manifest(total_cap_usd=5.00))

    def test_missing_fields_are_refused(self) -> None:
        for field in eval_budget.SCHEMA_FIELDS:
            manifest = _manifest()
            del manifest[field]
            with pytest.raises(eval_budget.ManifestError, match="missing required fields"):
                eval_budget.validate_manifest(manifest)

    def test_cost_above_the_run_cap_is_refused(self) -> None:
        with pytest.raises(eval_budget.ManifestError, match="exceeds"):
            eval_budget.validate_manifest(_manifest(estimated_cost_usd=4.01, total_cap_usd=4.00))

    def test_negative_and_non_positive_counts_are_refused(self) -> None:
        with pytest.raises(eval_budget.ManifestError):
            eval_budget.validate_manifest(_manifest(max_requests=0))
        with pytest.raises(eval_budget.ManifestError):
            eval_budget.validate_manifest(_manifest(max_tokens=-1))

    def test_unknown_run_kind_is_refused(self) -> None:
        with pytest.raises(eval_budget.ManifestError, match="run_kind"):
            eval_budget.validate_manifest(_manifest(run_kind="live"))

    def test_load_manifest_rejects_missing_and_corrupt_files(self, tmp_path: Path) -> None:
        with pytest.raises(eval_budget.ManifestError, match="not found"):
            eval_budget.load_manifest(tmp_path / "absent.manifest.json")
        bad = tmp_path / "bad.manifest.json"
        bad.write_text("{not json")
        with pytest.raises(eval_budget.ManifestError, match="not valid JSON"):
            eval_budget.load_manifest(bad)


class TestEstimatedCost:
    def test_estimate_is_worst_case_output_bound(self) -> None:
        # every billed token (output side) × list pricing, cache discount ignored
        assert eval_budget.estimate_cost_per_call("deepseek-chat", 8192) == pytest.approx(
            8192 * eval_budget.DEEPSEEK_PRICING["deepseek-chat"]["output"]
        )

    def test_unknown_model_refuses_to_estimate(self) -> None:
        with pytest.raises(eval_budget.ManifestError, match="pricing table"):
            eval_budget.estimate_cost_per_call("gpt-5", 100)

    def test_actual_cost_sums_both_token_directions(self) -> None:
        prices = eval_budget.DEEPSEEK_PRICING["deepseek-chat"]
        cost = eval_budget.estimate_cost_from_tokens("deepseek-chat", 1000, 2000)
        assert cost == pytest.approx(1000 * prices["input"] + 2000 * prices["output"])


class TestLedger:
    def _seed(self, ledger: Path, *entries: dict[str, object]) -> None:
        for entry in entries:
            eval_budget.append_ledger(ledger, entry)

    @staticmethod
    def _real_entry(cost: float = 0.01, manifest_id: str = "m0" * 1) -> dict[str, object]:
        return {
            "manifest_id": manifest_id,
            "run_kind": "real",
            "model": "deepseek-chat",
            "actual_cost_usd": cost,
            "prompt_tokens": 100,
            "output_tokens": 200,
            "output": "tests/responses/x.jsonl",
        }

    def test_missing_ledger_sum_is_zero(self, tmp_path: Path) -> None:
        assert eval_budget.ledger_total(tmp_path / "none.jsonl") == 0.0

    def test_ledger_sums_manifest_annotated_real_entries(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        self._seed(ledger, self._real_entry(0.01, "a"), self._real_entry(0.02, "b"))
        assert eval_budget.ledger_total(ledger) == pytest.approx(0.03)

    def test_dry_run_rows_contribute_zero(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        self._seed(
            ledger,
            {"run_kind": "dry_run", "manifest_id": "d1", "actual_cost_usd": 99.0},
            self._real_entry(0.01, "a"),
        )
        assert eval_budget.ledger_total(ledger) == pytest.approx(0.01)

    def test_unannotated_real_rows_are_never_summed(self, tmp_path: Path) -> None:
        # a real row with no manifest annotation is a broken ledger: it is
        # never included in the cumulative total (dry-run rows simply use
        # run_kind="dry_run" and likewise contribute 0)
        ledger = tmp_path / "spend-ledger.jsonl"
        self._seed(ledger, {"run_kind": "real", "actual_cost_usd": 50.0})
        with pytest.raises(eval_budget.ManifestError, match="without manifest annotation"):
            eval_budget.ledger_total(ledger)

    def test_real_row_without_annotation_is_rejected_as_broken(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        self._seed(ledger, {"run_kind": "real", "actual_cost_usd": 50.0})
        with pytest.raises(eval_budget.ManifestError, match="without manifest annotation"):
            eval_budget.chargeable_ledger_entries(ledger)
        with pytest.raises(eval_budget.ManifestError, match="without manifest annotation"):
            eval_budget.enforce_pre_run_budget(_manifest(), ledger)

    def test_corrupt_ledger_line_is_refused(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        ledger.write_text('{"ok": 1}\nnot json\n')
        with pytest.raises(eval_budget.ManifestError, match="line 2"):
            eval_budget.read_ledger_entries(ledger)


class TestPreRunBudget:
    def test_gate_allows_a_fitting_estimate(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        remaining = eval_budget.enforce_pre_run_budget(_manifest(), ledger)
        assert remaining == pytest.approx(eval_budget.TOTAL_CAP_USD - 0.0)

    def test_gate_refuses_when_estimate_plus_actuals_breach_the_cap(self, tmp_path: Path) -> None:
        ledger = tmp_path / "spend-ledger.jsonl"
        eval_budget.append_ledger(ledger, TestLedger._real_entry(4.95, "a"))
        with pytest.raises(eval_budget.ManifestError, match="mission cap"):
            eval_budget.enforce_pre_run_budget(_manifest(estimated_cost_usd=0.50), ledger)

    def test_ledger_entry_carries_the_manifest_annotation(self, tmp_path: Path) -> None:
        manifest = _manifest()
        entry = eval_budget.build_ledger_entry(
            manifest=manifest, model="deepseek-chat", prompt_tokens=10, output_tokens=20, output_relpath="x.jsonl"
        )
        assert entry["manifest_id"] == manifest["manifest_id"]
        assert entry["run_kind"] == "real"
        assert entry["actual_cost_usd"] > 0


RUNNER_NAMES = ("run_eval", "run-ten-ways", "llm_invoke")


class TestCommittedManifestAndLedgerFiles:
    """VAL-EVAL-012 checker: every consumed manifest stays under the cap."""

    @staticmethod
    def get_manifests() -> list[Path]:
        return sorted(REPO_ROOT.glob("tests/responses/*.manifest.json"))

    def test_committed_manifests_pass_schema_and_cap(self) -> None:
        for manifest_path in self.get_manifests():
            eval_budget.validate_manifest(json.loads(manifest_path.read_text()))

    def test_repo_ledger_stays_under_the_mission_cap(self) -> None:
        ledger = REPO_ROOT / "docs" / "evals" / "spend-ledger.jsonl"
        if not ledger.exists():
            return  # no real run has ever been authorized yet
        total = eval_budget.ledger_total(ledger)
        assert total <= eval_budget.TOTAL_CAP_USD + 1e-9


class TestCommandListProof:
    """VAL-EVAL-013: zero un-annotated real-run invocations any CI surface runs.

    Every Make/CI/pre-commit/check line that names a runner must either be a
    comment, or carry ``--dry-run`` / set ``TEMPORAL_LAB_DRY_RUN=1``.
    """

    SURFACES = (
        "Makefile",
        ".pre-commit-config.yaml",
        "bin/check_agents_md.py",
        *sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / ".github/workflows").glob("*")),
    )

    def _command_lines(self, surface: str) -> list[str]:
        text = (REPO_ROOT / surface).read_text()
        return [line for line in text.splitlines() if any(runner in line for runner in RUNNER_NAMES)]

    def test_surfaces_exist(self) -> None:
        assert "Makefile" in self.SURFACES and ".pre-commit-config.yaml" in self.SURFACES

    def test_zero_unannotated_real_run_invocations(self) -> None:
        offenders: list[str] = []
        for surface in self.SURFACES:
            for line in self._command_lines(surface):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue  # comment: documentation, not an invocation
                annotated = "--dry-run" in line or "TEMPORAL_LAB_DRY_RUN=1" in line or "dry_run" in line
                if not annotated:
                    offenders.append(f"{surface}: {stripped}")
        assert not offenders, "un-annotated real-run invocations in command lists:\n" + "\n".join(offenders)

    def test_no_ci_wiring_for_legacy_providers(self) -> None:
        surfaces = ["Makefile", *[str(p) for p in sorted((REPO_ROOT / ".github/workflows").glob("*"))]]
        for surface in surfaces:
            text = Path(surface).read_text()
            assert not re.search(r"ANTHROPIC_API_KEY|OPENROUTER_API_KEY", text), surface


class TestTestSuiteNeverReadsALiveKey:
    """VAL-EVAL-013 (2): test code only ever mentions env-var NAME constants."""

    def test_no_test_fetches_a_real_provider_key(self) -> None:
        offenders: list[str] = []
        for test_file in (REPO_ROOT / "tests").rglob("*.py"):
            for i, line in enumerate(test_file.read_text().splitlines(), start=1):
                # setenv/delenv with literal names is the dry-run/gate pattern;
                # reading a real value via os.environ[...] is not.
                if re.search(r"os\.environ\[[\"'](ANTHROPIC_API_KEY|OPENROUTER_API_KEY)", line):
                    offenders.append(f"{test_file.relative_to(REPO_ROOT)}:{i}")
        assert not offenders, "tests fetching live provider keys:\n" + "\n".join(offenders)

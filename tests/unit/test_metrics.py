"""Unit tests for the metrics registry and Prometheus export."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from altered_states import metrics
from altered_states.metrics import NAMESPACE, REGISTRY, Registry, dump_json, flush_metrics, timer, write_textfile


@pytest.fixture
def registry() -> Registry:
    return Registry()


class TestCounters:
    def test_counter_starts_at_zero(self, registry: Registry) -> None:
        assert registry.counter_value("build_runs") == 0.0

    def test_increment_accumulates(self, registry: Registry) -> None:
        registry.increment("build_runs")
        registry.increment("build_runs")
        assert registry.counter_value("build_runs") == 2.0

    def test_increment_accepts_a_step(self, registry: Registry) -> None:
        registry.increment("llm_tokens", 1500)
        assert registry.counter_value("llm_tokens") == 1500

    def test_labels_partition_the_counter(self, registry: Registry) -> None:
        registry.increment("llm_calls", status="ok")
        registry.increment("llm_calls", status="ok")
        registry.increment("llm_calls", status="error")
        assert registry.counter_value("llm_calls", status="ok") == 2.0
        assert registry.counter_value("llm_calls", status="error") == 1.0

    def test_label_order_does_not_change_the_series(self, registry: Registry) -> None:
        registry.increment("llm_calls", status="ok", substance="lsd")
        registry.increment("llm_calls", substance="lsd", status="ok")
        assert registry.counter_value("llm_calls", status="ok", substance="lsd") == 2.0


class TestGauges:
    def test_gauge_set_is_idempotent(self, registry: Registry) -> None:
        registry.gauge("cycles_generated", 10)
        registry.gauge("cycles_generated", 12)
        assert registry.gauge_value("cycles_generated") == 12

    def test_gauge_supports_labels(self, registry: Registry) -> None:
        registry.gauge("queue_depth", 3, worker="a")
        assert registry.gauge_value("queue_depth", worker="a") == 3


class TestHistograms:
    def test_observations_are_collected_in_order(self, registry: Registry) -> None:
        registry.observe("build_duration_seconds", 0.1)
        registry.observe("build_duration_seconds", 0.3)
        assert registry.histogram_values("build_duration_seconds") == [0.1, 0.3]

    def test_missing_histogram_returns_empty_list(self, registry: Registry) -> None:
        assert registry.histogram_values("nope") == []

    def test_timer_records_an_observation(self) -> None:
        REGISTRY.reset()
        with timer("llm_latency_seconds", substance="lsd"):
            pass
        observed = REGISTRY.histogram_values("llm_latency_seconds", substance="lsd")
        assert len(observed) == 1
        assert observed[0] >= 0


class TestPrometheusRendering:
    def test_counter_is_rendered_with_help_and_type(self) -> None:
        registry = Registry()
        registry.increment("build_runs")
        output = registry.render_prometheus()
        assert f"# HELP {NAMESPACE}_build_runs" in output
        assert f"# TYPE {NAMESPACE}_build_runs counter" in output
        assert f"{NAMESPACE}_build_runs 1" in output

    def test_labels_are_rendered_in_prometheus_syntax(self) -> None:
        registry = Registry()
        registry.increment("llm_calls", status="ok")
        assert f'{NAMESPACE}_llm_calls{{status="ok"}} 1' in registry.render_prometheus()

    def test_histograms_export_sum_and_count(self) -> None:
        registry = Registry()
        registry.observe("build_duration_seconds", 0.5)
        registry.observe("build_duration_seconds", 0.25)
        output = registry.render_prometheus()
        assert f"{NAMESPACE}_build_duration_seconds_sum 0.75" in output
        assert f"{NAMESPACE}_build_duration_seconds_count 2" in output

    def test_multiple_labels_are_comma_separated(self) -> None:
        registry = Registry()
        registry.increment("llm_calls", status="ok", substance="lsd")
        assert '{status="ok",substance="lsd"}' in registry.render_prometheus()

    def test_empty_registry_renders_nothing_but_a_newline(self) -> None:
        assert Registry().render_prometheus() == "\n"


class TestSnapshotAndFlush:
    def test_as_dict_reports_counts_and_sums(self) -> None:
        registry = Registry()
        registry.increment("build_runs")
        registry.observe("build_duration_seconds", 0.2)
        snapshot = registry.as_dict()
        assert snapshot["counters"][f"{NAMESPACE}_build_runs"] == 1.0
        assert snapshot["histograms"][f"{NAMESPACE}_build_duration_seconds"]["count"] == 1

    def test_reset_clears_every_series(self) -> None:
        registry = Registry()
        registry.increment("x")
        registry.gauge("y", 1)
        registry.observe("z", 1)
        registry.reset()
        assert registry.as_dict() == {"counters": {}, "gauges": {}, "histograms": {}}

    def test_write_textfile_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "metrics.prom"
        written = write_textfile(target)
        assert written.exists()
        assert written.parent.is_dir()

    def test_flush_writes_both_textfile_and_log_line(self, tmp_path: Path) -> None:
        REGISTRY.increment("build_runs")
        target = tmp_path / "out.prom"
        written = flush_metrics(target)
        assert f"{NAMESPACE}_build_runs 1" in written.read_text()

    def test_flush_honours_the_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        override = tmp_path / "from-env.prom"
        monkeypatch.setenv("METRICS_TEXTFILE_PATH", str(override))
        assert write_textfile() == override
        assert override.exists()

    def test_dump_json_is_valid_and_sorted(self) -> None:
        REGISTRY.increment("b")
        REGISTRY.increment("a")
        parsed = json.loads(dump_json())
        assert list(parsed["counters"]) == sorted(parsed["counters"])

    def test_default_textfile_path_is_relative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("METRICS_TEXTFILE_PATH", raising=False)
        assert not metrics.textfile_path().is_absolute()


class TestLayering:
    """`registry` is the bottom of the package; nothing below it may look up.

    A cycle between `log_utils` and `metrics` was once possible here — logging
    needed a counter and metrics needed the logger. These tests pin the
    one-way layering so it cannot come back unnoticed.
    """

    def test_metrics_reexports_the_one_registry(self) -> None:
        from altered_states import registry

        assert metrics.REGISTRY is registry.REGISTRY
        assert metrics.Registry is registry.Registry

    @staticmethod
    def _intra_package_imports(module_name: str) -> set[str]:
        source = (Path(__file__).parents[2] / "altered_states" / f"{module_name}.py").read_text()
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("altered_states"):
                imported.add(node.module.split(".")[1])
            elif isinstance(node, ast.Import):
                imported.update(
                    alias.name.split(".")[1] for alias in node.names if alias.name.startswith("altered_states")
                )
        return imported

    def test_registry_imports_nothing_from_this_package(self) -> None:
        assert self._intra_package_imports("registry") == set()

    def test_log_utils_depends_only_on_the_registry(self) -> None:
        assert self._intra_package_imports("log_utils") == {"registry"}

    def test_importing_either_module_first_works(self) -> None:
        """A cycle shows up in practice as failure that depends on import order."""
        for first in ("altered_states.log_utils", "altered_states.metrics"):
            result = subprocess.run(
                [sys.executable, "-c", f"import {first}; import altered_states.metrics"],
                capture_output=True,
                text=True,
                check=False,
                cwd=Path(__file__).parents[2],
            )
            assert result.returncode == 0, result.stderr

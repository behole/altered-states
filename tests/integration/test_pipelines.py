"""End-to-end integration tests.

These exercise whole pipelines against temporary copies of the real data
directories. No network access is required: the LLM path runs in dry-run mode
(``TEMPORAL_LAB_DRY_RUN``) and the site builder reads fixture journals.
"""

from __future__ import annotations

import json
from pathlib import Path

import characters
import logger
import pytest
import temporal_init

import build
from altered_states import feature_flags
from tests.conftest import write_journal

pytestmark = pytest.mark.integration


class TestSiteBuildPipeline:
    """build.py: journals + experiments + music -> a complete HTML document."""

    @pytest.fixture
    def site_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
        journals_dir = tmp_path / "journals"
        experiments_dir = tmp_path / "experiments"
        music_dir = tmp_path / "music"
        for directory in (journals_dir, experiments_dir, music_dir):
            directory.mkdir()

        write_journal(
            journals_dir,
            "lsd",
            [
                {"cycle": 0, "emotional_state": "calm"},
                {
                    "cycle": 1,
                    "emotional_state": "awed",
                    "experience": {"description": "Fragmenting nicely.", "intensity": 0.8, "novelty": 0.4},
                    "reflections": ["a"],
                    "questions": ["b"],
                },
            ],
        )
        (experiments_dir / "what-is-love.md").write_text(
            '# Same Prompt\n> "What is love?"\n> Run: 2026-04-22 22:00\n\n'
            "## 🍄 Psilocybin — *The Teacher*\n**Intensity:** MEDIUM\n\nLove is a root system.\n\n---\n"
        )
        music = music_dir / "describe-a-song"
        music.mkdir()
        (music / "metadata.json").write_text(json.dumps({"title": "Describe", "date": "2026-01-01"}))
        (music / "tracks.json").write_text(
            json.dumps({"tracks": [{"persona_id": "lsd", "name": "LSD", "emoji": "⚡", "audio_file": "lsd.mp3"}]})
        )

        template = tmp_path / "template.html"
        template.write_text(
            "<html><script>const P=__PERSONAS__;const J=__JOURNALS__;"
            "const E=__EXPERIMENTS__;const M=__MUSIC__;const F=__FLAGS__;"
            "const C=__CYCLE_COUNT__;const X=__EXP_COUNT__;const S=__MUSIC_COUNT__;</script></html>"
        )
        output = tmp_path / "index.html"

        monkeypatch.setattr(build, "JOURNALS_DIR", str(journals_dir))
        # Fixture journals are read as the default source; point them at the
        # same tmp scaffold so this pipeline test stays hermetic.
        monkeypatch.setattr(build, "FIXTURE_JOURNALS_DIR", str(journals_dir))
        monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(experiments_dir))
        monkeypatch.setattr(build, "MUSIC_DIR", str(music_dir))
        monkeypatch.setattr(build, "TEMPLATE", str(template))
        monkeypatch.setattr(build, "OUTPUT", str(output))
        # build() writes the per-substance pages and OG cards through the
        # module-level SITE_DIR / OG_DIR constants. Without patching both, a
        # parallel xdist worker rebuilds/clears the COMMITTED site/og/*.png
        # blobs while other workers' committed-card tests are reading them
        # (the release-hotfix flake in TestWriteOgCards).
        test_site = tmp_path / "site"
        monkeypatch.setattr(build, "SITE_DIR", str(test_site))
        monkeypatch.setattr(build, "OG_DIR", str(test_site / "og"))
        return {"output": output, "template": template, "journals": journals_dir}

    def test_build_writes_a_complete_document(self, site_dirs: dict[str, Path]) -> None:
        build.build()
        html = site_dirs["output"].read_text()
        assert "__" not in html
        assert "Love is a root system." in html

    def test_build_records_metrics(self, site_dirs: dict[str, Path]) -> None:
        from altered_states.metrics import REGISTRY

        build.build()
        assert REGISTRY.counter_value("build_runs") == 1.0
        assert len(REGISTRY.histogram_values("build_duration_seconds")) == 1

    def test_build_cycle_count_sums_every_journal_entry(self, site_dirs: dict[str, Path]) -> None:
        build.build()
        # The fixture journal holds two entries, so the site reports two cycles.
        assert "const C=2;" in site_dirs["output"].read_text()

    def test_flags_are_embedded_in_the_page(self, site_dirs: dict[str, Path]) -> None:
        build.build()
        html = site_dirs["output"].read_text()
        assert "site.music_section" in html
        assert "site.chat_personas" in html

    def test_feature_flag_env_override_changes_the_page(
        self, site_dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "build.flags",
            feature_flags.load_flags(environ={"FLAG_SITE_CHAT_PERSONAS": "off"}),
        )
        build.build()
        assert build.enabled_section_flags()["site.chat_personas"] is False

    def test_build_emits_structured_log_lines(
        self, site_dirs: dict[str, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        build.build()
        events = [json.loads(line)["event"] for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
        assert "build.start" in events
        assert "build.complete" in events

    def test_build_records_a_sendable_error_when_parsing_raises(
        self, site_dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def explode() -> None:
            raise RuntimeError("journal directory is unreadable")

        monkeypatch.setattr(build, "load_journals", explode)
        with pytest.raises(RuntimeError):
            build.build()


class TestTemporalLabCyclePipeline:
    """temporal_init: init -> run (dry-run) -> journal written -> dashboard reads it."""

    def test_init_creates_character_state(self, lab_root: Path) -> None:
        lab = temporal_init.TemporalLab()
        assert lab.initialize_character("mdma") is True
        state = json.loads((lab_root / "characters" / "mdma.json").read_text())
        assert state["cycle_count"] == 0
        assert state["name"] == "The Connector"

    def test_run_cycle_persists_a_journal_entry(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        lab = temporal_init.TemporalLab()
        lab.initialize_character("mdma")

        assert lab.run_cycle("mdma") is True

        journal = json.loads((lab_root / "journals" / "mdma_journal.json").read_text())
        assert journal[-1]["cycle"] == 1
        assert journal[-1]["experience"]["description"].startswith("[DRY-RUN STUB]")

    def test_run_cycle_advances_the_character_counter(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        lab = temporal_init.TemporalLab()
        lab.initialize_character("mdma")
        lab.run_cycle("mdma")
        lab.run_cycle("mdma")
        state = json.loads((lab_root / "characters" / "mdma.json").read_text())
        assert state["cycle_count"] == 2
        assert state["last_cycle"]

    def test_plain_text_mirror_is_written(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        lab = temporal_init.TemporalLab()
        lab.initialize_character("lsd")
        lab.run_cycle("lsd")
        mirror = (lab_root / "journals" / "lsd_journal.txt").read_text()
        assert "LSD — Cycle 1" in mirror
        assert "Emotional State:" in mirror

    def test_failed_cycle_is_journaled_as_silence(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lab = temporal_init.TemporalLab()
        lab.initialize_character("mdma")

        def boom(*args: object, **kwargs: object) -> dict[str, object]:
            raise RuntimeError("provider down")

        monkeypatch.setattr(temporal_init, "generate_cycle", boom)
        assert lab.run_cycle("mdma") is False

        journal = json.loads((lab_root / "journals" / "mdma_journal.json").read_text())
        assert journal[-1]["error"] == "provider down"
        assert "silence" in journal[-1]["experience"]["description"]

    def test_unknown_substance_is_rejected(self, lab_root: Path) -> None:
        lab = temporal_init.TemporalLab()
        assert lab.initialize_character("unobtainium") is False

    def test_listing_characters_returns_initialised_ones(self, lab_root: Path) -> None:
        lab = temporal_init.TemporalLab()
        lab.initialize_character("lsd")
        assert [char["substance"] for char in lab.list_characters()] == ["lsd"]

    def test_every_substance_can_be_initialised(self, lab_root: Path) -> None:
        lab = temporal_init.TemporalLab()
        for substance in characters.available_substances():
            assert lab.initialize_character(substance) is True

    def test_cycle_costs_are_ledgered(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        lab = temporal_init.TemporalLab()
        lab.initialize_character("mdma")
        lab.run_cycle("mdma")

        ledger = lab_root / "logs" / "cost-ledger.csv"
        assert ledger.exists()
        assert "mdma" in ledger.read_text()

    def test_metrics_textfile_is_written(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        lab = temporal_init.TemporalLab()
        lab.initialize_character("mdma")
        lab.run_cycle("mdma")

        textfile = lab_root / "metrics" / "altered-states.prom"
        assert textfile.exists()
        assert "altered_states_llm_calls" in textfile.read_text()

    def test_dry_run_never_calls_a_provider(self, lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEMPORAL_LAB_DRY_RUN", "1")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        lab = temporal_init.TemporalLab()
        lab.initialize_character("lsd")
        assert lab.run_cycle("lsd") is True


class TestLoggerIntegration:
    """logger: one call -> JSON log + CSV ledger + metrics, all redacted."""

    def test_log_call_writes_all_three_artifacts(self, lab_root: Path) -> None:
        record = logger.CallRecord("lsd", "test-model", 10, 20, 0.001, "ok", "", 42)
        logger.log_call(record)

        log_files = list((lab_root / "logs").glob("*.log"))
        assert len(log_files) == 1
        assert json.loads(log_files[0].read_text().strip())["tokens_in"] == 10
        assert (lab_root / "logs" / "cost-ledger.csv").exists()
        assert (lab_root / "metrics" / "altered-states.prom").exists()

    def test_secrets_in_the_message_are_redacted(self, lab_root: Path) -> None:
        record = logger.CallRecord("lsd", "m", 0, 0, 0.0, "api-error", "failed with sk-live-abcdef123456")
        logger.log_call(record)
        log_file = next((lab_root / "logs").glob("*.log"))
        assert "sk-live-abcdef123456" not in log_file.read_text()

    def test_cost_summaries_read_the_ledger(self, lab_root: Path) -> None:
        for tokens_in, tokens_out in ((100, 200), (10, 20)):
            logger.log_call(logger.CallRecord("lsd", "m", tokens_in, tokens_out, 0.5, "ok"))

        today = logger.daily_cost_summary()
        lifetime = logger.lifetime_cost_summary()

        assert today["calls"] == 2
        assert today["tokens_in"] == 110
        assert lifetime["cost_usd"] == pytest.approx(1.0)
        assert lifetime["by_model"]["m"]["calls"] == 2

    def test_failed_calls_are_excluded_from_cost_totals(self, lab_root: Path) -> None:
        logger.log_call(logger.CallRecord("lsd", "m", 0, 0, 1.0, "ok"))
        logger.log_call(logger.CallRecord("lsd", "m", 0, 0, 5.0, "api-error"))
        assert logger.lifetime_cost_summary()["calls"] == 1

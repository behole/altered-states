"""Shared fixtures for the unit and integration suites.

Every test runs against a temporary copy of the repository's data directories,
so nothing here writes into the working tree and suites can run in parallel
(``-n auto``) without interfering with each other.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "experiments" / "temporal-lab" / "scripts"
BIN_DIR = REPO_ROOT / "bin"

# Tests import modules from all three roots the way the scripts themselves do:
# repo root (build.py, altered_states), bin/ (run_eval, responses_to_grid), and
# the temporal-lab scripts directory.
for path in (REPO_ROOT, BIN_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def _isolated_metrics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point metric output at the test's temp dir and reset the registry."""
    from altered_states.metrics import REGISTRY

    registry = REGISTRY
    registry.reset()
    monkeypatch.setenv("METRICS_TEXTFILE_PATH", str(tmp_path / "metrics.prom"))
    yield
    registry.reset()


@pytest.fixture(autouse=True)
def _quiet_error_tracking(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Never let a test attempt to reach Sentry, even if a DSN is exported."""
    from altered_states import error_tracking

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    error_tracking.reset_state()
    yield
    error_tracking.reset_state()


@pytest.fixture
def journal_entry() -> dict[str, object]:
    """A representative temporal-lab journal entry."""
    return {
        "timestamp": "2026-04-21T20:07:08",
        "cycle": 2,
        "emotional_state": "awed",
        "clarity": "moderate",
        "integration": "low",
        "experience": {
            "description": "The floor is still the floor but it is making an argument.",
            "intensity": 0.42,
            "novelty": 0.71,
        },
        "reflections": ["The body knew first."],
        "questions": ["Who is feeling the separateness?"],
    }


@pytest.fixture
def lab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated temporal-lab runtime directory, wired via the env override."""
    root = tmp_path / "runtime"
    root.mkdir()
    monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(root))
    return root


@pytest.fixture
def experiment_md(tmp_path: Path) -> Path:
    """A same-prompt experiment file in the exact format build.py parses."""
    content = """# Same Prompt, Ten Ways
> "What is love?"
> Run: 2026-04-22 22:00 | Model: test-model
> Per-substance sweet-spot intensity

---

## 🍄 Psilocybin — *The Teacher*
**Intensity:** MEDIUM

Love is a root system. It finds the cracks.

---

## ⚡ LSD — *The Technician*
**Intensity:** MEDIUM

Love is a protocol both sides agree to speak.
"""
    path = tmp_path / "what-is-love-20260422-2200.md"
    path.write_text(content)
    return path


@pytest.fixture
def flag_file(tmp_path: Path) -> Path:
    """A small flag file covering on, off, and partial-rollout states."""
    payload = {
        "flags": [
            {
                "name": "site.music_section",
                "enabled": True,
                "rollout_percentage": 100,
                "owner": "site",
            },
            {
                "name": "site.chat_personas",
                "enabled": False,
                "rollout_percentage": 100,
                "owner": "site",
            },
            {
                "name": "site.experiment_wheel",
                "enabled": True,
                "rollout_percentage": 50,
                "owner": "site",
                "allowlist": ["vip"],
                "denylist": ["blocked"],
            },
        ]
    }
    path = tmp_path / "feature_flags.json"
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def clean_env() -> Iterator[dict[str, str]]:
    """An empty environment mapping for flag-override tests."""
    yield {}


def write_journal(directory: Path, substance: str, entries: list[dict[str, object]]) -> Path:
    """Write a journal file the way temporal_init does."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{substance}_journal.json"
    path.write_text(json.dumps(entries))
    return path


def env_without(*keys: str) -> dict[str, str]:
    """Copy of os.environ with the given keys removed."""
    return {key: value for key, value in os.environ.items() if key not in keys}

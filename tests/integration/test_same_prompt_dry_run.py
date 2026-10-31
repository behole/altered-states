"""Same-prompt runner: offline dry-run integration test.

Invokes ``experiments/same-prompt/run-ten-ways.py --dry-run`` as a subprocess
with no network access and asserts the contract: exit 0, every substance
succeeds, and the dry-run stub marker appears in the output. The compiled
markdown is written to a temporary directory so the read-only
``experiments/same-prompt/output/`` data directory is never touched: without
an explicit ``--output``, a plain ``--dry-run`` resolves to a fresh temp dir.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Anchored to this file so pytest works from any working directory.
REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "experiments" / "same-prompt" / "run-ten-ways.py"
DATA_DIR = REPO_ROOT / "experiments" / "same-prompt" / "output"


def _snapshot_data_dir() -> set[str]:
    """Filenames currently tracked under the read-only data directory."""
    return {p.name for p in DATA_DIR.iterdir()}


def run_runner(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run the dry-run subprocess with no network access."""
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_dry_run_runner_exits_zero_with_stub_marker(tmp_path: Path) -> None:
    """--dry-run runs offline: exit 0, 10/10 substances, [DRY-RUN STUB] marker."""
    result = run_runner(
        [
            "What is grief?",
            "--dry-run",
            "--output",
            str(tmp_path),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "Dry-run: True" in result.stdout
    assert "Done: 10/10 succeeded" in result.stdout

    # The compiled markdown was written to the temp dir, not the data directory.
    compiled = list(tmp_path.glob("*.md"))
    assert len(compiled) == 1
    assert "[DRY-RUN STUB]" in compiled[0].read_text()


def test_dry_run_without_output_writes_to_temp_dir_not_data_dir() -> None:
    """--dry-run with no --output prints a temp path and touches no data files."""
    before = _snapshot_data_dir()
    result = run_runner(["What is grief?", "--dry-run"])

    assert result.returncode == 0, result.stderr
    assert "Done: 10/10 succeeded" in result.stdout

    # The reported output path is a temp dir, not the tracked data directory.
    output_line = next(line for line in result.stdout.splitlines() if line.strip().startswith("Output:"))
    written = Path(output_line.strip().removeprefix("Output:").strip())
    assert written.parent != DATA_DIR

    # The compiled markdown exists in the temp dir and contains the stub marker.
    assert written.is_file()
    assert "[DRY-RUN STUB]" in written.read_text()

    # The tracked data directory is untouched: nothing new appeared.
    assert _snapshot_data_dir() == before

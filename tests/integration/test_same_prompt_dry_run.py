"""Same-prompt runner: offline dry-run integration test.

Invokes ``experiments/same-prompt/run-ten-ways.py --dry-run`` as a subprocess
with no network access and asserts the contract: exit 0, every substance
succeeds, and the dry-run stub marker appears in the output. The compiled
markdown is written to a temporary directory so the read-only
``experiments/same-prompt/output/`` data directory is never touched.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

RUNNER = Path("experiments/same-prompt/run-ten-ways.py")


def test_dry_run_runner_exits_zero_with_stub_marker(tmp_path: Path) -> None:
    """--dry-run runs offline: exit 0, 10/10 substances, [DRY-RUN STUB] marker."""
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "What is grief?",
            "--dry-run",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Dry-run: True" in result.stdout
    assert "Done: 10/10 succeeded" in result.stdout

    # The compiled markdown was written to the temp dir, not the data directory.
    compiled = list(tmp_path.glob("*.md"))
    assert len(compiled) == 1
    assert "[DRY-RUN STUB]" in compiled[0].read_text()

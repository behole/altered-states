"""Golden snapshot tests for build.py's JSON payloads (VAL-TOOL-005).

Each snapshot lives under ``tests/fixtures/golden/snapshots/`` and is keyed on
a content hash (SHA-256) of the fixture data directories it derives from. Two
things fail loudly:

* fixture inputs change without a re-snapshot (the stored ``inputs`` hash no
  longer matches the files on disk) — a snapshot whose content survived a
  fixture drift is not a golden test;
* the payload contract itself changes (e.g. a camelCase key is renamed) — the
  deep diff names the exact key path that moved.

Re-snapshotting after an *intended* change (never accidental drift):

    UPDATE_GOLDEN_SNAPSHOTS=1 pytest tests/unit/test_golden_snapshots.py

then review the diff of ``tests/fixtures/golden/snapshots/`` like any other
contract change.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

import build

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
JOURNALS_DIR = GOLDEN_DIR / "journals"
SKILLS_DIR = GOLDEN_DIR / "skills"
EXPERIMENTS_DIR = GOLDEN_DIR / "same-prompt-output"
SNAPSHOTS_DIR = GOLDEN_DIR / "snapshots"
UPDATE_ENV = "UPDATE_GOLDEN_SNAPSHOTS"

# The camelCase key contract of the persona cards (site/index.template.html
# reads these verbatim). Any rename breaks the page AND the snapshot test.
PERSONA_KEYS = {"id", "name", "emoji", "character", "chatPrompt", "currentState", "cycleCount"}


def _dir_digest(directory: Path) -> tuple[str, dict[str, str]]:
    """SHA-256 of a fixture directory plus a per-file digest map.

    The aggregate hash covers every file's relative path and bytes, so any
    addition, deletion, or content change moves it. The per-file map is only
    for human-facing failure messages (which file drifted).
    """
    digest = hashlib.sha256()
    per_file: dict[str, str] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(directory))
        blob = path.read_bytes()
        per_file[rel] = hashlib.sha256(blob).hexdigest()
        digest.update(rel.encode())
        digest.update(blob)
    return digest.hexdigest(), per_file


def _diff_dict(actual: dict[str, Any], expected: dict[str, Any], path: str) -> str | None:
    """Key-set and per-value comparison for dict payloads."""
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"expected key missing from actual payload: {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected key in actual payload: {', '.join(extra)}")
        return f"{path}: " + "; ".join(parts)
    for key in sorted(expected):
        found = _diff_value(actual[key], expected[key], f"{path}.{key}")
        if found is not None:
            return found
    return None


def _diff_list(actual: list[Any], expected: list[Any], path: str) -> str | None:
    """Index-wise comparison for list payloads."""
    if len(actual) != len(expected):
        return f"{path}: length {len(actual)} != {len(expected)}"
    for i in range(len(actual)):
        found = _diff_value(actual[i], expected[i], f"{path}[{i}]")
        if found is not None:
            return found
    return None


def _diff_value(actual: Any, expected: Any, path: str) -> str | None:
    if type(actual) is not type(expected):
        return f"{path}: type {type(actual).__name__} != {type(expected).__name__}"
    if isinstance(actual, dict):
        return _diff_dict(actual, expected, path)
    if isinstance(actual, list):
        return _diff_list(actual, expected, path)
    return None if actual == expected else f"{path}: {actual!r} != {expected!r}"


def _first_difference(actual: Any, expected: Any, path: str = "payload") -> str | None:
    """Path of the first difference between two JSON-shaped values, or None.

    The path is what failure messages quote (``payload[0].chatPrompt``), so a
    key rename is named explicitly rather than reported as a blob mismatch.
    """
    return _diff_value(actual, expected, path)


def _assert_golden(name: str, payload: Any, inputs: dict[str, Path]) -> None:
    """Compare ``payload`` against its golden snapshot; compare the fixture
    inputs' content hashes first, so stale snapshots fail loudly."""
    snapshot_path = SNAPSHOTS_DIR / f"{name}.json"
    inputs_now = {label: _dir_digest(directory)[0] for label, directory in inputs.items()}

    if UPDATE_ENV in os.environ and not snapshot_path.exists():
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps({"inputs": inputs_now, "payload": payload}, indent=2, ensure_ascii=False))
        return

    assert snapshot_path.exists(), (
        f"No golden snapshot for {name} yet; run "
        f"{UPDATE_ENV}=1 pytest tests/unit/test_golden_snapshots.py to create it, then review the diff."
    )
    snapshot = json.loads(snapshot_path.read_text())
    inputs_then: dict[str, str] = snapshot.get("inputs", {})

    drifted = {
        label: snapshot_inputs
        for label, snapshot_inputs in inputs_then.items()
        if inputs_now.get(label) != snapshot_inputs
    }
    missing_labels = sorted(set(inputs_now) - set(inputs_then))
    assert not drifted and not missing_labels, (
        f"Golden fixture inputs for {name} changed without re-snapshotting "
        f"(hash-keyed). Changed: {sorted(drifted) or 'none'}; new inputs: {missing_labels or 'none'}. "
        "If the change is intended, regenerate with "
        f"{UPDATE_ENV}=1 pytest tests/unit/test_golden_snapshots.py — the snapshot must move WITH its fixtures."
    )

    diff = _first_difference(payload, snapshot["payload"])
    assert diff is None, (
        f"Golden snapshot {name} mismatch at {diff}.\n"
        "Expected (snapshot):\n"
        f"{json.dumps(snapshot['payload'], indent=2, ensure_ascii=False)}\n"
        "Actual (derived from fixtures):\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )


@pytest.fixture
def golden_inputs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point build.py's module-level data dirs at the golden fixture copies."""
    monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(JOURNALS_DIR))
    monkeypatch.setattr(build, "SKILLS_DIR", str(SKILLS_DIR))
    monkeypatch.setattr(build, "EXPERIMENTS_DIR", str(EXPERIMENTS_DIR))
    return {"journals": JOURNALS_DIR, "skills": SKILLS_DIR, "experiments": EXPERIMENTS_DIR}


def _personas_payload() -> list[dict[str, Any]]:
    """The exact payload build() injects as __PERSONAS__."""
    return build.build_persona_payload(build.load_journals())


def _journal_series_payload() -> dict[str, Any]:
    return build.build_journal_series_payload(build.load_journals())


def _quiz_payload() -> dict[str, Any]:
    return build.build_quiz_payload(build.load_experiments(), build.load_substances())


class TestPersonasPayload:
    """Snapshot (a): the camelCase persona/pyproject payload contract."""

    def test_matches_golden_snapshot(self, golden_inputs: dict[str, Path]) -> None:
        inputs = {key: golden_inputs[key] for key in ("journals",)}
        _assert_golden("personas_payload", _personas_payload(), inputs)

    def test_exact_camelcase_key_set(self, golden_inputs: dict[str, Path]) -> None:
        payload = _personas_payload()
        assert payload, "fixture journals should light up every persona card"
        for persona in payload:
            assert set(persona) == PERSONA_KEYS

    def test_snapshot_records_the_payload_value_types(self, golden_inputs: dict[str, Path]) -> None:
        payload = _personas_payload()
        snapshot = json.loads((SNAPSHOTS_DIR / "personas_payload.json").read_text())
        expected = snapshot["payload"]
        assert isinstance(expected, list) and len(expected) == len(payload)
        for actual, recorded in zip(payload, expected, strict=True):
            assert isinstance(recorded["chatPrompt"], str) and isinstance(actual["chatPrompt"], str)
            assert isinstance(recorded["currentState"], str) and isinstance(actual["currentState"], str)
            assert isinstance(recorded["cycleCount"], int) and isinstance(actual["cycleCount"], int)
            assert recorded["chatPrompt"] == actual["chatPrompt"]

    def test_seeded_chatprompt_rename_fails_with_named_diff(self, golden_inputs: dict[str, Path]) -> None:
        payload = copy.deepcopy(_personas_payload())
        for persona in payload:
            persona["chat_prompt"] = persona.pop("chatPrompt")
        with pytest.raises(AssertionError) as excinfo:
            _assert_golden("personas_payload", payload, {"journals": golden_inputs["journals"]})
        message = str(excinfo.value)
        assert "payload[0]: expected key missing from actual payload: chatPrompt" in message
        assert "unexpected key in actual payload: chat_prompt" in message

    def test_changed_fixture_inputs_fail_loudly(
        self, golden_inputs: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Input drift without re-snapshotting = loud failure naming the input."""
        mutated = tmp_path / "journals"
        mutated.mkdir()
        journal = json.loads((JOURNALS_DIR / "psilocybin_journal.json").read_text())
        journal.append({"timestamp": "2026-04-24T10:00:00", "cycle": 4, "emotional_state": "restless"})
        (mutated / "psilocybin_journal.json").write_text(json.dumps(journal))

        monkeypatch.setenv("ALTERED_STATES_TEMPORAL_PATH", str(mutated))
        with pytest.raises(AssertionError) as excinfo:
            _assert_golden("personas_payload", _personas_payload(), {"journals": mutated})
        message = str(excinfo.value)
        assert "without re-snapshotting" in message
        assert "'journals'" in message


class TestJournalSeriesPayload:
    """Snapshot (b): the temporal-lab dashboards series payload."""

    def test_matches_golden_snapshot(self, golden_inputs: dict[str, Path]) -> None:
        inputs = {key: golden_inputs[key] for key in ("journals",)}
        _assert_golden("journal_series_payload", _journal_series_payload(), inputs)

    def test_series_values_are_journal_values_verbatim(self, golden_inputs: dict[str, Path]) -> None:
        raw_entries = json.loads((JOURNALS_DIR / "psilocybin_journal.json").read_text())
        chartable = [e for e in raw_entries if not e.get("error") and isinstance(e.get("cycle"), int)]
        payload = _journal_series_payload()
        psilocybin = next(c for c in payload["characters"] if c["id"] == "psilocybin")
        assert len(psilocybin["cycles"]) == len(chartable)
        numeric = [
            (recorded, raw)
            for recorded, raw in zip(psilocybin["cycles"], chartable, strict=True)
            if isinstance(raw.get("experience"), dict)
        ]
        assert numeric, "fixture journal should include object-experience entries"
        for recorded, raw in numeric:
            assert recorded["cycle"] == raw["cycle"]
            assert recorded["intensity"] == raw["experience"]["intensity"]


class TestQuizPayload:
    """Snapshot (c): the masked blind-taxonomy game payload."""

    def test_matches_golden_snapshot(self, golden_inputs: dict[str, Path]) -> None:
        inputs = {key: golden_inputs[key] for key in ("skills", "experiments")}
        payload = _quiz_payload()
        assert payload["items"], "fixture corpus should yield at least one quiz item"
        _assert_golden("quiz_payload", payload, inputs)

    def test_masked_items_carry_no_answer_or_label(self, golden_inputs: dict[str, Path]) -> None:
        payload = _quiz_payload()
        for item in payload["items"]:
            assert set(item) == {"id", "prompt", "excerpt"}
        for answer in payload["answers"]:
            assert set(answer) == {"id", "options", "correct", "label", "emoji", "href"}

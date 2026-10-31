"""Unit tests for the AGENTS.md validator."""

from __future__ import annotations

from pathlib import Path

import check_agents_md
import pytest
from check_agents_md import Problems, check_inline_paths, check_make_targets, check_sections, validate


def a_doc(*sections: str, body: str = "") -> str:
    return "\n\n".join(sections) + "\n\n" + body


class TestSections:
    def test_all_required_sections_pass(self) -> None:
        problems = Problems()
        check_sections(a_doc(*check_agents_md.REQUIRED_SECTIONS), problems)
        assert not problems

    def test_a_missing_section_is_reported(self) -> None:
        problems = Problems()
        check_sections(a_doc(*check_agents_md.REQUIRED_SECTIONS[1:]), problems)
        assert any("missing section" in item for item in problems.items)


class TestMakeTargets:
    def test_a_real_target_passes(self) -> None:
        problems = Problems()
        check_make_targets("Run `make check` and `make test`.", problems)
        assert not problems

    def test_a_renamed_target_is_reported(self) -> None:
        problems = Problems()
        check_make_targets("Run `make check-typo`.", problems)
        assert any("check-typo" in item for item in problems.items)

    def test_the_makefile_still_defines_the_documented_targets(self) -> None:
        targets = check_agents_md.make_targets()
        assert {"check", "test", "build", "verify", "security", "deps", "flags"} <= targets


class TestDocumentedScripts:
    def test_a_missing_script_is_reported(self) -> None:
        problems = Problems()
        text = "```bash\npython3 bin/not_a_real_script.py --dry-run\n```\n"
        check_agents_md.check_documented_scripts(text, problems)
        assert any("not_a_real_script.py" in item for item in problems.items)

    def test_an_existing_script_passes(self) -> None:
        problems = Problems()
        text = "```bash\npython3 bin/run_eval.py --dry-run\n```\n"
        check_agents_md.check_documented_scripts(text, problems)
        assert not problems

    def test_module_invocations_are_not_checked_as_files(self) -> None:
        problems = Problems()
        block = "```bash\npython -m altered_states.feature_flags check\n```\n"
        check_agents_md.check_documented_scripts(block, problems)
        assert not problems

    def test_comments_and_blanks_are_ignored(self) -> None:
        problems = Problems()
        check_agents_md.check_documented_scripts("```bash\n# a comment\n\n```\n", problems)
        assert not problems


class TestInlinePaths:
    def test_a_missing_relative_path_is_reported(self) -> None:
        problems = Problems()
        check_inline_paths("See `docs/not-real.md` for detail.", problems)
        assert any("docs/not-real.md" in item for item in problems.items)

    def test_an_existing_relative_path_passes(self) -> None:
        problems = Problems()
        check_inline_paths("See `docs/research-pipeline.md`.", problems)
        assert not problems

    def test_bare_filenames_are_not_assertions(self) -> None:
        problems = Problems()
        check_inline_paths("Each `SKILL.md` is content, and `index.html` is output.", problems)
        assert not problems

    def test_allowed_missing_paths_are_skipped(self) -> None:
        problems = Problems()
        for path in check_agents_md.ALLOWED_MISSING:
            check_inline_paths(f"See `{path}`.", problems)
        assert not problems

    def test_commands_are_not_paths(self) -> None:
        problems = Problems()
        check_inline_paths("Run `make check` or `--dry-run`.", problems)
        assert not problems


class TestExecutableClaims:
    def test_commands_are_not_run_in_a_child(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(check_agents_md.CHILD_MARKER, "1")
        problems = Problems()
        text = "```bash\npython bin/check_agents_md.py\n```\n"
        assert check_agents_md.check_executable_claims(text, problems) == 0
        assert not problems

    def test_a_claim_is_recognised(self) -> None:
        assert check_agents_md._is_executable_claim("python bin/check_agents_md.py") is True
        assert check_agents_md._is_executable_claim("python -m altered_states.feature_flags check") is True

    def test_a_heavy_gate_is_not_recognised(self) -> None:
        assert check_agents_md._is_executable_claim("make check") is False

    def test_a_costing_command_is_not_recognised(self) -> None:
        assert check_agents_md._is_executable_claim("python3 bin/run_eval.py --real") is False

    def test_python_is_resolved_to_the_running_interpreter(self) -> None:
        import sys

        assert check_agents_md._resolved_argv("python bin/x.py")[0] == sys.executable


class TestFullDocument:
    def test_committed_agents_md_is_accurate(self) -> None:
        problems, _ = validate(check_agents_md.AGENTS_MD.read_text(), run_commands=False)
        assert not problems, problems.items

    def test_drift_is_detected_in_a_broken_document(self, tmp_path: Path) -> None:
        broken = tmp_path / "AGENTS.md"
        broken.write_text("# Nothing useful here\n\n```bash\nmake no-such-target\n```\n")
        problems, _ = validate(broken.read_text(), run_commands=False)
        assert problems

    def test_running_the_claims_succeeds_for_the_real_document(self) -> None:
        problems, executed = validate(check_agents_md.AGENTS_MD.read_text(), run_commands=True)
        assert not problems, problems.items
        assert executed >= 1


class TestCli:
    def test_committed_file_passes(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert check_agents_md.main(["--no-run"]) == check_agents_md.EXIT_OK
        assert "AGENTS.md is accurate" in capsys.readouterr().out

    def test_missing_file_is_a_usage_error(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = check_agents_md.main(["--file", str(tmp_path / "absent.md")])
        assert code == check_agents_md.EXIT_USAGE
        assert "does not exist" in capsys.readouterr().err

    def test_drift_exits_one(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        broken = tmp_path / "AGENTS.md"
        broken.write_text("# empty\n")
        assert check_agents_md.main(["--file", str(broken), "--no-run"]) == check_agents_md.EXIT_DRIFT
        assert "DRIFT" in capsys.readouterr().err

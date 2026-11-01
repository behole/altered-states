"""Unit tests for the pull-request convention reviewer."""

from __future__ import annotations

from pathlib import Path

import pytest
import review_pr
from review_pr import ADVISORY, BLOCKING, FileChange, lock_for, parse_diff, render, review


def make_diff(*files: str) -> str:
    return "\n".join(files)


def file_diff(
    path: str,
    added: list[str] | None = None,
    removed: list[str] | None = None,
    *,
    new: bool = False,
    deleted: bool = False,
) -> str:
    """Build a diff hunk in the shape git actually emits."""
    lines = [f"diff --git a/{path} b/{path}"]
    if new:
        lines.append("new file mode 100644")
    if deleted:
        lines.append("deleted file mode 100644")
    lines.append("index 1111111..2222222 100644")
    lines.append(f"--- {'/dev/null' if new else 'a/' + path}")
    lines.append(f"+++ {'/dev/null' if deleted else 'b/' + path}")
    lines.append("@@ -1,0 +1,10 @@")
    lines.extend(f"+{line}" for line in added or [])
    lines.extend(f"-{line}" for line in removed or [])
    return "\n".join(lines)


class TestParsing:
    def test_paths_are_extracted_for_each_file(self) -> None:
        changes = parse_diff(make_diff(file_diff("a.py", ["x = 1"]), file_diff("b.md", ["hi"])))
        assert [change.path for change in changes] == ["a.py", "b.md"]

    def test_added_and_removed_lines_are_separated(self) -> None:
        changes = parse_diff(file_diff("a.py", ["new"], ["old"]))
        assert changes[0].added == ["new"]
        assert changes[0].removed == ["old"]

    def test_new_file_status_is_recorded(self) -> None:
        changes = parse_diff(file_diff("a.py", ["x"], new=True))
        assert changes[0].is_new is True

    def test_deleted_file_status_is_recorded(self) -> None:
        changes = parse_diff(file_diff("a.py", deleted=True))
        assert changes[0].is_deleted is True

    def test_index_and_header_lines_are_not_content(self) -> None:
        diff = "diff --git a/a.py b/a.py\nindex 123..456 100644\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n+x\n"
        assert parse_diff(diff)[0].added == ["x"]

    def test_empty_diff_yields_no_changes(self) -> None:
        assert parse_diff("") == []

    def test_python_and_test_classification(self) -> None:
        changes = parse_diff(make_diff(file_diff("bin/x.py", ["a"]), file_diff("tests/unit/test_x.py", ["b"])))
        assert changes[0].is_python is True and changes[0].is_test is False
        assert changes[1].is_test is True


class TestFileRules:
    def test_python_change_without_tests_is_advisory(self) -> None:
        findings = review(parse_diff(file_diff("bin/run_eval.py", ["x = 1"])))
        assert [finding.severity for finding in findings] == [ADVISORY]
        assert "no change under" in findings[0].message

    def test_python_change_with_tests_is_clean(self) -> None:
        findings = review(
            parse_diff(
                make_diff(
                    file_diff("bin/run_eval.py", ["x = 1"]),
                    file_diff("tests/unit/test_run_eval.py", ["def test_x(): ..."]),
                )
            )
        )
        assert findings == []

    def test_test_only_change_is_clean(self) -> None:
        assert review(parse_diff(file_diff("tests/unit/test_x.py", ["def test_a(): ..."]))) == []

    def test_hand_editing_the_built_page_is_advisory(self) -> None:
        findings = review(parse_diff(file_diff("site/index.html", ["<p>hi</p>"], ["<p>bye</p>"])))
        assert findings[0].severity == ADVISORY
        assert "template" in findings[0].message

    def test_deleting_a_journal_is_blocking(self) -> None:
        findings = review(parse_diff(file_diff("experiments/temporal-lab/runtime/journals/lsd.json", deleted=True)))
        assert findings[0].severity == BLOCKING
        assert "cannot be regenerated" in findings[0].message

    def test_deleting_captured_responses_is_blocking(self) -> None:
        findings = review(parse_diff(file_diff("experiments/same-prompt/output/run.md", deleted=True)))
        assert findings[0].severity == BLOCKING

    def test_deleting_ordinary_code_is_not_flagged(self) -> None:
        assert review(parse_diff(file_diff("bin/old_helper.py", deleted=True))) == []


class TestDependencyRules:
    def test_requirements_change_without_lock_is_blocking(self) -> None:
        findings = review(parse_diff(file_diff("bin/requirements.txt", ["openai==3.42.0"])))
        assert findings[0].severity == BLOCKING
        assert "bin/requirements.lock" in findings[0].message

    @pytest.mark.parametrize(
        "path",
        ["requirements.txt", "requirements-dev.txt", "requirements-test.txt", "bin/requirements.txt"],
    )
    def test_every_requirement_file_is_covered(self, path: str) -> None:
        findings = review(parse_diff(file_diff(path, ["x==1.0"])))
        assert [finding.severity for finding in findings] == [BLOCKING]
        assert lock_for(path) in findings[0].message

    def test_requirements_change_with_lock_is_clean(self) -> None:
        findings = review(
            parse_diff(
                make_diff(
                    file_diff("bin/requirements.txt", ["openai==3.42.0"]),
                    file_diff("bin/requirements.lock", ["openai==3.42.0"]),
                )
            )
        )
        assert [finding for finding in findings if finding.path == "bin/requirements.txt"] == []

    def test_lock_only_change_is_advisory(self) -> None:
        findings = review(parse_diff(file_diff("bin/requirements.lock", ["openai==3.43.0"])))
        assert findings[0].severity == ADVISORY
        assert "Dependabot" in findings[0].message


def fake_secrets() -> list[str]:
    """Credential-shaped strings, assembled rather than written out.

    A literal key in a test file is still a key to every secret scanner on the
    way in — Droid-Shield, `git push` protection, the provider's own crawler —
    so the fragments are concatenated at import time. The shapes are exactly
    what the real patterns match.
    """
    digits = "0123456789abcdefghij"
    return [
        "key = '" + "sk-" + "ant-" + digits + "klmnop" + "'",
        "router = '" + "sk-" + "or-v1-" + digits + "klmnop" + "'",
        "openai = '" + "sk-" + "proj-" + digits + "klmnop" + "'",
        "token = '" + "ghp" + "_" + digits + "klmnopqrst" + "'",
        "aws = '" + "AKIA" + "ABCDEFGHIJKLMNOP" + "'",
        "slack = '" + "xox" + "b-" + "1122334455" + "-" + digits[:10] + "'",
        "-----BEGIN " + "RSA " + "PRIVATE KEY" + "-----",
    ]


class TestSecretRules:
    def test_one_fixture_per_pattern(self) -> None:
        assert len(fake_secrets()) == len(review_pr.SECRET_PATTERNS)

    @pytest.mark.parametrize("index", range(7))
    def test_credential_shapes_are_blocking(self, index: int) -> None:
        findings = review(parse_diff(file_diff("bin/x.py", [fake_secrets()[index]])))
        assert any(finding.severity == BLOCKING and "looks like" in finding.message for finding in findings)

    def test_environment_variable_reference_is_clean(self) -> None:
        changes = parse_diff(
            make_diff(
                file_diff("bin/x.py", ["key = os.environ['DEEPSEEK_API_KEY']"]),
                file_diff("tests/unit/test_x.py", ["def test_a(): ..."]),
            )
        )
        assert review(changes) == []

    def test_removed_secret_is_not_flagged(self) -> None:
        changes = parse_diff(
            make_diff(
                file_diff("bin/x.py", ["clean"], [fake_secrets()[1]]),
                file_diff("tests/unit/test_x.py", ["def test_a(): ..."]),
            )
        )
        assert review(changes) == []


class TestFlagRules:
    def test_reference_to_an_undeclared_flag_is_blocking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(review_pr, "_declared_flags", set)
        findings = review(
            parse_diff(
                make_diff(
                    file_diff("build.py", ['flags.is_enabled("site.new_section")']),
                    file_diff("feature_flags.json", ['{"name": "site.other"}']),
                    file_diff("tests/unit/test_build.py", ["x"]),
                )
            )
        )
        assert any(finding.severity == BLOCKING and "site.new_section" in finding.message for finding in findings)

    def test_reference_to_a_declared_flag_is_clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(review_pr, "_declared_flags", lambda: {"site.music_section"})
        findings = review(
            parse_diff(
                make_diff(
                    file_diff("build.py", ['flags.is_enabled("site.music_section")']),
                    file_diff("tests/unit/test_build.py", ["x"]),
                )
            )
        )
        assert findings == []

    def test_flag_added_in_the_same_pr_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(review_pr, "_declared_flags", set)
        findings = review(
            parse_diff(
                make_diff(
                    file_diff("site/index.template.html", ["flagOn('site.brand_new')"]),
                    file_diff("feature_flags.json", ['  { "name": "site.brand_new", "enabled": true }']),
                )
            )
        )
        assert findings == []

    def test_committed_flags_json_is_well_formed(self) -> None:
        declared = review_pr._declared_flags()
        assert "site.music_section" in declared


class TestRendering:
    def test_report_counts_blocking_and_advisory(self) -> None:
        changes = parse_diff(
            make_diff(
                file_diff("bin/requirements.txt", ["x==1"]),
                file_diff("site/index.html", ["a"], ["b"]),
            )
        )
        report = render(review(changes), changes)
        assert "2 changed file(s)" in report
        assert "1 blocking, 1 advisory" in report

    def test_clean_diff_says_a_human_still_needs_to_review(self) -> None:
        changes = parse_diff(file_diff("tests/unit/test_x.py", ["def test_a(): ..."]))
        assert "human still needs to review" in render(review(changes), changes)

    def test_blocking_findings_use_a_marker(self) -> None:
        changes = parse_diff(file_diff("bin/requirements.txt", ["x==1"]))
        assert "[**blocking**]" in render(review(changes), changes)


class TestCli:
    def _run(self, tmp_path: Path, diff: str, *args: str) -> int:
        path = tmp_path / "pr.diff"
        path.write_text(diff)
        return review_pr.main(["--diff-file", str(path), *args])

    def test_clean_diff_exits_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        code = self._run(tmp_path, file_diff("tests/unit/test_x.py", ["def test_a(): ..."]))
        assert code == review_pr.EXIT_OK
        assert "Automated review" in capsys.readouterr().out

    def test_blocking_diff_exits_one(self, tmp_path: Path) -> None:
        assert self._run(tmp_path, file_diff("bin/requirements.txt", ["x==1"])) == review_pr.EXIT_BLOCKING

    def test_fail_on_never_always_exits_zero(self, tmp_path: Path) -> None:
        code = self._run(tmp_path, file_diff("bin/requirements.txt", ["x==1"]), "--fail-on", "never")
        assert code == review_pr.EXIT_OK

    def test_missing_diff_file_is_a_usage_error(self, tmp_path: Path) -> None:
        assert review_pr.main(["--diff-file", str(tmp_path / "absent.diff")]) == review_pr.EXIT_USAGE

    def test_output_file_receives_the_report(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = tmp_path / "review.md"
        self._run(tmp_path, file_diff("tests/unit/test_x.py", ["x"]), "--output", str(target))
        capsys.readouterr()
        assert "Automated review" in target.read_text()

    def test_diff_can_come_from_stdin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import io
        import sys

        monkeypatch.setattr(sys, "stdin", io.StringIO(file_diff("tests/unit/test_x.py", ["x"])))
        assert review_pr.main(["--fail-on", "never"]) == review_pr.EXIT_OK
        capsys.readouterr()


def test_file_change_defaults() -> None:
    change = FileChange(path="a.py")
    assert change.status == "modified"
    assert change.added == []

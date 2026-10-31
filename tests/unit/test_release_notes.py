"""Unit tests for conventional-commit release note generation."""

from __future__ import annotations

from pathlib import Path

import pytest
import release_notes
from release_notes import Commit, Notes


def a_commit(subject: str, body: str = "", sha: str = "abcdef1234567") -> Commit:
    return Commit(sha=sha, subject=subject, body=body)


class TestCommitParsing:
    def test_type_scope_and_summary_are_extracted(self) -> None:
        commit = a_commit("feat(site): add a music tab")
        assert (commit.kind, commit.scope, commit.summary) == ("feat", "site", "add a music tab")

    def test_scope_is_optional(self) -> None:
        commit = a_commit("fix: correct the phase table")
        assert commit.scope == ""
        assert commit.summary == "correct the phase table"

    def test_bang_marks_a_breaking_change(self) -> None:
        assert a_commit("feat(api)!: drop the v1 endpoint").is_breaking is True

    def test_breaking_change_footer_is_detected(self) -> None:
        assert a_commit("feat: rewrite", body="BREAKING CHANGE: flags renamed").is_breaking is True

    def test_ordinary_commit_is_not_breaking(self) -> None:
        assert a_commit("feat: add a tab").is_breaking is False

    def test_non_conventional_subject_is_other(self) -> None:
        commit = a_commit("Merge pull request #2 from behole/foo")
        assert commit.kind == "other"
        assert commit.summary.startswith("Merge pull request")

    def test_release_commit_is_recognised(self) -> None:
        assert a_commit("chore(release): v1.5.0").is_release_commit is True

    def test_rendered_line_names_scope_and_short_sha(self) -> None:
        assert a_commit("feat(site): add a tab").render() == "- **site:** add a tab (abcdef1)"

    def test_breaking_line_is_marked(self) -> None:
        assert "**BREAKING**" in a_commit("feat!: drop v1").render()


class TestNotes:
    def _notes(self, *subjects: str) -> Notes:
        commits = [a_commit(subject, sha=f"{index:07d}abc") for index, subject in enumerate(subjects)]
        return Notes(version="v1.5.0", commits=commits)

    def test_commits_are_grouped_by_type(self) -> None:
        notes = self._notes("feat: one", "fix: two", "docs: three")
        grouped = notes.grouped()
        assert [commit.summary for commit in grouped["feat"]] == ["one"]
        assert [commit.summary for commit in grouped["fix"]] == ["two"]
        assert [commit.summary for commit in grouped["docs"]] == ["three"]

    def test_hidden_types_are_counted_but_not_sectioned(self) -> None:
        notes = self._notes("chore: bump", "ci: retry", "feat: visible")
        assert len(notes.user_visible) == 1
        assert notes.grouped()["feat"][0].summary == "visible"

    def test_breaking_changes_get_their_own_section_first(self) -> None:
        rendered = self._notes("feat!: drop v1", "fix: tiny").render()
        assert rendered.index("## Breaking changes") < rendered.index("## Fixes")

    def test_sections_are_ordered_not_alphabetical(self) -> None:
        rendered = self._notes("docs: d", "feat: f").render()
        assert rendered.index("## Features") < rendered.index("## Documentation")

    def test_commits_within_a_section_are_sorted(self) -> None:
        rendered = self._notes("feat: zebra", "feat: apple").render()
        assert rendered.index("apple") < rendered.index("zebra")

    def test_empty_sections_are_omitted(self) -> None:
        assert "## Tests" not in self._notes("feat: one").render()

    def test_unclassified_commits_are_reported(self) -> None:
        rendered = self._notes("did something without a prefix").render()
        assert "## Unclassified" in rendered

    def test_no_user_visible_changes_says_so(self) -> None:
        assert "No user-visible changes" in self._notes("chore: bump").render()

    def test_header_counts_commits(self) -> None:
        assert "2 commit(s), 1 user-visible" in self._notes("cmd: x", "feat: y").render()

    def test_version_is_the_heading(self) -> None:
        assert self._notes("feat: y").render().startswith("# v1.5.0")


class TestSnapshotFromGit:
    def test_committed_history_parses(self) -> None:
        commits = release_notes.read_commits("HEAD")
        assert commits
        assert all(commit.sha for commit in commits)
        assert all(commit.subject for commit in commits)

    def test_this_repository_uses_conventional_subjects(self) -> None:
        """This repo's own history is the input `release.yml` parses on a tag.

        Asserting the commit count matters: on a shallow clone `git log`
        succeeds but returns nothing, and a version of this test without the
        floor would pass while checking nothing at all.
        """
        commits = release_notes.read_commits("HEAD")
        assert len(commits) >= 5, "checkout has no history; CI needs fetch-depth: 0"
        classified = [commit for commit in commits if commit.kind != "other"]
        # The convention was adopted mid-history, so a handful of older subjects
        # will never parse. The contract is that the overwhelming majority do —
        # a regression in naming shows up as this ratio dropping.
        assert len(classified) / len(commits) >= 0.95, (
            f"{len(commits) - len(classified)} of {len(commits)} commits are not conventional"
        )

    def test_git_log_output_is_parsed_field_by_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The record/field separators are unusual, so pin the exact format."""
        sha = "0" * 40
        raw = (
            f"{sha}{release_notes.FIELD_SEPARATOR}feat(site): add a tab{release_notes.FIELD_SEPARATOR}"
            f"Carries the tab.{release_notes.COMMIT_SEPARATOR}"
        )
        monkeypatch.setattr(release_notes, "git", lambda *args: raw)
        (commit,) = release_notes.read_commits("HEAD")
        assert (commit.sha, commit.kind, commit.scope, commit.summary) == (sha, "feat", "site", "add a tab")
        assert "Carries the tab." in commit.body

    def test_records_without_a_sha_are_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(release_notes, "git", lambda *args: release_notes.COMMIT_SEPARATOR.join(["", "oops"]))
        assert release_notes.read_commits("HEAD") == []

    def test_bad_revision_yields_no_commits(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert release_notes.read_commits("definitely-not-a-ref..HEAD") == []
        assert "ERROR" in capsys.readouterr().err


class TestCli:
    def test_notes_are_written_to_a_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = tmp_path / "notes.md"
        code = release_notes.main(["--from", "HEAD~2", "--to", "HEAD", "--version", "v9.9.9", "--output", str(target)])
        assert code == release_notes.EXIT_OK
        capsys.readouterr()
        assert target.read_text().startswith("# v9.9.9")

    def test_output_directory_is_created(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = tmp_path / "nested" / "notes.md"
        release_notes.main(["--from", "HEAD~1", "--output", str(target)])
        capsys.readouterr()
        assert target.parent.is_dir()

    def test_missing_tag_falls_back_to_history(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(release_notes, "latest_tag", lambda: None)
        assert release_notes.main(["--version", "x"]) == release_notes.EXIT_OK
        assert "no tags found" in capsys.readouterr().err

import io
import tarfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from utils import scenarios
from utils.ci.github import nightly
from utils.ci.github.nightly import (
    ActivationConfig,
    AutoMergeOptIn,
    CommandResult,
    GithubContext,
    NightlyOptions,
    extract_reports_from_logs_artifacts,
    process_activation_branch,
    run_nightly_activation,
    should_enable_auto_merge,
)
from utils.const import COMPONENT_GROUPS


@dataclass
class RecordedCommand:
    args: list[str]
    env: Mapping[str, str] | None = None
    input: str | None = None


class FakeRunner:
    def __init__(self, results: Sequence[CommandResult]) -> None:
        self._results = list(results)
        self.commands: list[RecordedCommand] = []

    def run(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        self.commands.append(RecordedCommand(list(args), env=env, input=input_text))
        if not self._results:
            return CommandResult(args=list(args), returncode=0)
        canned = self._results.pop(0)
        if canned.args:
            return canned
        return CommandResult(args=list(args), returncode=canned.returncode, stdout=canned.stdout, stderr=canned.stderr)


def result(stdout: str = "", returncode: int = 0, stderr: str = "") -> CommandResult:
    return CommandResult(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def options(tmp_path: Path) -> NightlyOptions:
    commit_headless = tmp_path / "commit-headless"
    commit_headless.write_text("#!/bin/sh\n", encoding="utf-8")
    return NightlyOptions(
        reports_dir=tmp_path,
        commit_headless=commit_headless,
        github=GithubContext(repository="DataDog/system-tests", server_url="https://github.com", run_id="123"),
        github_token="token",  # noqa: S106 - test token for fake command execution
        auto_merge_opt_ins=(AutoMergeOptIn(owner="asm-libraries", library="python"),),
    )


@scenarios.test_the_test
class Test_GithubNightly:
    def test_default_libraries_come_from_easy_win_component_group(self) -> None:
        assert [config.library for config in nightly.LIBRARIES] == sorted(COMPONENT_GROUPS.easy_win)
        assert [config.library for config in nightly.LIBRARIES if config.use_dev] == ["rust"]

    def test_cli_uses_explicit_runtime_arguments_and_env_token(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured: dict[str, NightlyOptions] = {}

        def fake_run_nightly_activation(options: NightlyOptions) -> int:
            captured["options"] = options
            return 0

        monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
        monkeypatch.setattr(nightly, "run_nightly_activation", fake_run_nightly_activation)

        exit_code = nightly.main(
            [
                "activate",
                "--reports-dir",
                str(tmp_path / "data"),
                "--commit-headless",
                str(tmp_path / "commit-headless"),
                "--repository",
                "DataDog/system-tests",
                "--server-url",
                "https://github.com",
                "--run-id",
                "123",
            ]
        )

        assert exit_code == 0
        assert captured["options"].reports_dir == tmp_path / "data"
        assert captured["options"].commit_headless == tmp_path / "commit-headless"
        assert captured["options"].github == GithubContext(
            repository="DataDog/system-tests",
            server_url="https://github.com",
            run_id="123",
        )
        assert captured["options"].github_token == "secret-token"

    def test_auto_merge_opt_in_requires_exact_owner_library(self) -> None:
        opt_ins = (AutoMergeOptIn(owner="asm-libraries", library="python"),)

        assert should_enable_auto_merge("asm-libraries", "python", opt_ins)
        assert not should_enable_auto_merge("asm-libraries", "ruby", opt_ins)
        assert not should_enable_auto_merge("apm-python", "python", opt_ins)

    def test_extract_reports_from_logs_artifacts(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "logs_python"
        artifact_dir.mkdir()
        report_content = b'{"context": {"library_name": "python"}}'

        with tarfile.open(artifact_dir / "artifact.tar.gz", "w:gz") as archive:
            info = tarfile.TarInfo("logs/report.json")
            info.size = len(report_content)
            archive.addfile(info, io.BytesIO(report_content))
            ignored = b"large log"
            ignored_info = tarfile.TarInfo("logs/weblog.log")
            ignored_info.size = len(ignored)
            archive.addfile(ignored_info, io.BytesIO(ignored))

        extract_reports_from_logs_artifacts(tmp_path)

        assert (artifact_dir / "logs/report.json").read_bytes() == report_content
        assert not (artifact_dir / "logs/weblog.log").exists()
        assert not (artifact_dir / "artifact.tar.gz").exists()

    def test_setup_failure_is_repeated_at_the_tail(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        artifact_dir = tmp_path / "logs_python"
        artifact_dir.mkdir()
        (artifact_dir / "artifact.tar.gz").write_bytes(b"not a tar archive")

        exit_code = run_nightly_activation(
            options(tmp_path),
            libraries=(ActivationConfig(library="python"),),
            runner=FakeRunner([]),
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "============ Nightly activation failures ============" in captured.out
        assert "setup:" in captured.out

    def test_no_change_activation_is_success(self, tmp_path: Path) -> None:
        runner = FakeRunner(
            [
                result(),  # git config user.name
                result(),  # git config user.email
                result(),  # gh auth setup-git
                result(),  # git checkout main
                result("No update were made\n"),  # activate_easy_wins exits 0 for no changes
                result(""),  # no easy-win branches
            ]
        )

        exit_code = run_nightly_activation(
            options(tmp_path),
            libraries=(ActivationConfig(library="python"),),
            runner=runner,
        )

        assert exit_code == 0
        assert ["git", "checkout", "main"] in [command.args for command in runner.commands]

    def test_activation_exit_one_with_error_is_failure(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        runner = FakeRunner(
            [
                result(),  # git config user.name
                result(),  # git config user.email
                result(),  # gh auth setup-git
                result(),  # git checkout main
                result(returncode=1, stderr="activation failed"),  # python activation
                result(""),  # no branches
            ]
        )

        exit_code = run_nightly_activation(
            options(tmp_path),
            libraries=(ActivationConfig(library="python"),),
            runner=runner,
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert captured.out.rstrip().endswith("activation failed")

    def test_failures_are_repeated_at_the_tail(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        runner = FakeRunner(
            [
                result(),  # git config user.name
                result(),  # git config user.email
                result(),  # gh auth setup-git
                result(),  # git checkout main
                result(returncode=2, stderr="activation exploded"),  # python activation
                result(""),  # no branches
                result(),  # git checkout main
                result("No update were made\n"),  # ruby no changes
                result(""),  # no branches
            ]
        )

        exit_code = run_nightly_activation(
            options(tmp_path),
            libraries=(ActivationConfig(library="python"), ActivationConfig(library="ruby")),
            runner=runner,
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        failure_summary = captured.out.rsplit("============ Nightly activation failures ============", maxsplit=1)[
            1
        ].strip()
        assert failure_summary.startswith("python: Activation command failed:")
        assert failure_summary.endswith("activation exploded")
        assert "ruby:" not in failure_summary

    def test_branch_failure_does_not_skip_other_branches(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        runner = FakeRunner(
            [
                result(),  # git config user.name
                result(),  # git config user.email
                result(),  # gh auth setup-git
                result(),  # git checkout main
                result(),  # activate_easy_wins
                result("easy-win/team-a/python easy-win/team-b/python"),  # branches
                result(""),  # team-a has no PR
                result(returncode=2, stderr="checkout failed"),  # team-a git checkout
                result(""),  # team-b has no PR
                result(),  # team-b git checkout
                result("main-sha\n"),  # git rev-parse main
                result("commit-sha\n"),  # git log
                result(returncode=2),  # remote branch does not exist
                result("signed-sha\n"),  # commit-headless
                result(),  # gh pr create
                result("789\n"),  # gh pr list after create
                result(),  # gh pr ready
            ]
        )

        exit_code = run_nightly_activation(
            options(tmp_path),
            libraries=(ActivationConfig(library="python"),),
            runner=runner,
        )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert captured.out.rstrip().endswith(
            "python/easy-win/team-a/python: Command failed: git checkout easy-win/team-a/python: checkout failed"
        )
        assert ["gh", "pr", "ready", "789"] in [command.args for command in runner.commands]

    def test_human_activity_guard_skips_branch_updates(self, tmp_path: Path) -> None:
        runner = FakeRunner(
            [
                result("123\n"),  # existing PR
                result("1\n"),  # human comments
                result("0\n"),  # human reviews
                result("1\n"),  # commit count
            ]
        )

        process_activation_branch(
            "easy-win/asm-libraries/python",
            "python",
            options(tmp_path),
            runner,
        )

        assert ["git", "checkout", "easy-win/asm-libraries/python"] not in [command.args for command in runner.commands]
        assert ["gh", "pr", "merge", "123", "--auto", "--squash"] not in [command.args for command in runner.commands]

    def test_auto_merge_runs_only_for_opted_in_pair(self, tmp_path: Path) -> None:
        runner = FakeRunner(
            [
                result(""),  # no existing PR
                result(),  # git checkout
                result("main-sha\n"),  # git rev-parse main
                result("commit-sha\n"),  # git log
                result(returncode=2),  # remote branch does not exist
                result("signed-sha\n"),  # commit-headless
                result(),  # gh pr create
                result("456\n"),  # gh pr list after create
                result(),  # gh pr ready
                result(),  # gh pr merge --auto --squash
            ]
        )

        process_activation_branch(
            "easy-win/asm-libraries/python",
            "python",
            options(tmp_path),
            runner,
        )

        assert ["gh", "pr", "merge", "456", "--auto", "--squash"] in [command.args for command in runner.commands]

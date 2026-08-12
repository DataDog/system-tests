from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from utils.const import COMPONENT_GROUPS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class ActivationConfig:
    library: str
    excluded_owners: tuple[str, ...] = ()
    use_dev: bool = False


@dataclass(frozen=True)
class AutoMergeOptIn:
    owner: str
    library: str


@dataclass(frozen=True)
class GithubContext:
    repository: str
    server_url: str
    run_id: str


@dataclass(frozen=True)
class NightlyOptions:
    reports_dir: Path
    commit_headless: Path
    github: GithubContext
    github_token: str
    auto_merge_opt_ins: tuple[AutoMergeOptIn, ...]


@dataclass(frozen=True)
class CommandResult:
    args: Sequence[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult: ...


@dataclass(frozen=True)
class PullRequestActivity:
    comments: int
    reviews: int
    commits: int

    @property
    def has_human_activity(self) -> bool:
        return self.comments > 0 or self.reviews > 0 or self.commits > 1


@dataclass(frozen=True)
class LibraryFailure:
    library: str
    message: str


class SubprocessRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            check=False,
            env=dict(env) if env is not None else None,
            input=input_text,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="")  # noqa: T201
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)  # noqa: T201
        return CommandResult(
            args=args,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


LIBRARIES: tuple[ActivationConfig, ...] = tuple(
    ActivationConfig(library, use_dev=library == "rust") for library in sorted(COMPONENT_GROUPS.easy_win)
)

AUTO_MERGE_OPT_INS: tuple[AutoMergeOptIn, ...] = (
    # AutoMergeOptIn(owner="asm-libraries", library="python"),
)

MIN_ACTIVATION_BRANCH_PARTS = 3


def should_enable_auto_merge(owner: str, library: str, opt_ins: Sequence[AutoMergeOptIn]) -> bool:
    return any(opt_in.owner == owner and opt_in.library == library for opt_in in opt_ins)


def extract_reports_from_logs_artifacts(reports_dir: Path) -> None:
    for archive_path in reports_dir.glob("logs_*/artifact.tar.gz"):
        _extract_report_files(archive_path, archive_path.parent)
        archive_path.unlink()


def _extract_report_files(archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith("/report.json"):
                continue
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination_root):
                raise RuntimeError(f"Unsafe path in artifact archive: {member.name}")
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                shutil.copyfileobj(extracted, output)


def run_nightly_activation(
    options: NightlyOptions,
    *,
    libraries: Sequence[ActivationConfig] = LIBRARIES,
    runner: CommandRunner | None = None,
) -> int:
    command_runner = runner or SubprocessRunner()
    failures: list[LibraryFailure] = []

    try:
        extract_reports_from_logs_artifacts(options.reports_dir)
        _prepare_git(command_runner)
        _prepare_github(command_runner)
        _prepare_commit_headless(options.commit_headless)
    except Exception as exc:
        failures.append(LibraryFailure("setup", str(exc)))
        _print_failure_summary(failures)
        return 1

    for library in libraries:
        print(f"============ Activating {library.library} ============")  # noqa: T201
        try:
            branches = activate_library(library, command_runner)
        except Exception as exc:
            failures.append(LibraryFailure(library.library, str(exc)))
            print(f"ERROR {library.library}: {exc}", file=sys.stderr)  # noqa: T201
            continue

        for branch in branches:
            try:
                process_activation_branch(branch, library.library, options, command_runner)
            except Exception as exc:
                failure_name = f"{library.library}/{branch}"
                failures.append(LibraryFailure(failure_name, str(exc)))
                print(f"ERROR {failure_name}: {exc}", file=sys.stderr)  # noqa: T201

    if failures:
        _print_failure_summary(failures)
        return 1

    return 0


def activate_library(config: ActivationConfig, runner: CommandRunner) -> list[str]:
    _run_checked(["git", "checkout", "main"], runner)
    command = [
        sys.executable,
        "-m",
        "utils.scripts.activate_easy_wins",
        "--no-download",
        "--split-co",
        "--components",
        config.library,
    ]
    if config.excluded_owners:
        command.append("--exclude")
        command.extend(config.excluded_owners)
    if config.use_dev:
        command.append("--dev")

    activation = runner.run(command)
    branches = _list_activation_branches(config.library, runner)
    if activation.returncode == 1 and not branches and not activation.stderr.strip():
        print(f"No activation changes for {config.library}")  # noqa: T201
        return []
    if activation.returncode != 0:
        raise RuntimeError(_command_error("Activation command failed", activation))
    return branches


def process_activation_branch(
    branch_name: str,
    library: str,
    options: NightlyOptions,
    runner: CommandRunner,
) -> None:
    print(f"============ Processing {branch_name} ============")  # noqa: T201
    owner = owner_from_branch(branch_name)
    pr_number = _find_pr_number(branch_name, runner)

    if pr_number is not None:
        activity = _get_pr_activity(options.github.repository, pr_number, runner)
        if activity.has_human_activity:
            print(  # noqa: T201
                f"PR #{pr_number} for {branch_name} has human activity "
                f"(comments={activity.comments}, reviews={activity.reviews}, commits={activity.commits}), skipping"
            )
            return
        print(f"PR #{pr_number} exists but has no human activity, updating")  # noqa: T201

    _push_signed_branch(branch_name, options, runner)

    if pr_number is None:
        _create_pr(branch_name, owner, library, options.github, runner)
        pr_number = _find_pr_number(branch_name, runner)
        if pr_number is None:
            raise RuntimeError(f"Could not find PR after creating it for {branch_name}")
        _run_checked(["gh", "pr", "ready", pr_number], runner)

    if should_enable_auto_merge(owner, library, options.auto_merge_opt_ins):
        print(f"Enabling auto-merge on PR #{pr_number}")  # noqa: T201
        _run_checked(["gh", "pr", "merge", pr_number, "--auto", "--squash"], runner)


def owner_from_branch(branch_name: str) -> str:
    parts = branch_name.split("/")
    if len(parts) < MIN_ACTIVATION_BRANCH_PARTS or parts[0] != "easy-win":
        raise RuntimeError(f"Unexpected activation branch name: {branch_name}")
    return parts[1]


def _prepare_git(runner: CommandRunner) -> None:
    _run_checked(["git", "config", "--global", "user.name", "github-actions[bot]"], runner)
    _run_checked(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], runner)


def _prepare_github(runner: CommandRunner) -> None:
    _run_checked(["gh", "auth", "setup-git"], runner)


def _prepare_commit_headless(commit_headless: Path) -> None:
    if not commit_headless.exists():
        raise RuntimeError(f"commit-headless binary not found: {commit_headless}")
    commit_headless.chmod(commit_headless.stat().st_mode | stat.S_IXUSR)


def _list_activation_branches(library: str, runner: CommandRunner) -> list[str]:
    result = _run_checked(
        ["git", "branch", "--list", f"easy-win/*/{library}", "--format=%(refname:short)"],
        runner,
    )
    return result.stdout.split()


def _find_pr_number(branch_name: str, runner: CommandRunner) -> str | None:
    result = _run_checked(
        ["gh", "pr", "list", "--head", branch_name, "--json", "number", "--jq", ".[0].number"],
        runner,
    )
    value = result.stdout.strip()
    if value in ("", "null"):
        return None
    return value


def _get_pr_activity(repository: str, pr_number: str, runner: CommandRunner) -> PullRequestActivity:
    comments = _api_count(
        [
            "gh",
            "api",
            f"repos/{repository}/issues/{pr_number}/comments",
            "--jq",
            '[.[] | select(.user.type != "Bot")] | length',
        ],
        runner,
    )
    reviews = _api_count(
        [
            "gh",
            "api",
            f"repos/{repository}/pulls/{pr_number}/reviews",
            "--jq",
            '[.[] | select(.user.type != "Bot")] | length',
        ],
        runner,
    )
    commits = _api_count(["gh", "api", f"repos/{repository}/pulls/{pr_number}/commits", "--jq", "length"], runner)
    return PullRequestActivity(comments=comments, reviews=reviews, commits=commits)


def _api_count(command: Sequence[str], runner: CommandRunner) -> int:
    result = _run_checked(command, runner)
    return int(result.stdout.strip() or "0")


def _push_signed_branch(branch_name: str, options: NightlyOptions, runner: CommandRunner) -> None:
    _run_checked(["git", "checkout", branch_name], runner)
    main_sha = _run_checked(["git", "rev-parse", "main"], runner).stdout.strip()
    commits = _run_checked(["git", "log", "--reverse", "--format=%H", f"{main_sha}..HEAD"], runner).stdout
    remote_branch_exists = (
        runner.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch_name]).returncode == 0
    )
    command = [
        str(options.commit_headless),
        "push",
        "-T",
        options.github.repository,
        "--branch",
        branch_name,
        "--head-sha",
        main_sha,
        "--force" if remote_branch_exists else "--create-branch",
    ]
    env = os.environ | {"HEADLESS_TOKEN": options.github_token}
    signed = _run_checked(command, runner, env=env, input_text=commits).stdout.strip()
    print(f"Pushed signed commit {signed} to {branch_name}")  # noqa: T201


def _create_pr(
    branch_name: str,
    owner: str,
    library: str,
    github: GithubContext,
    runner: CommandRunner,
) -> None:
    body = (
        f"Automated activation of easy-win tests for `{library}` owned by `{owner}`\n"
        f"[View nightly workflow run]({github.server_url}/{github.repository}/actions/runs/{github.run_id})\n"
        "- Auto-merge is only enabled for opted-in team/library pairs.\n"
        "- If the tests are failing it might be due to a change made since the last nightly system-tests run. "
        "You can close the PR, an updated one will be available tomorrow.\n"
        "- If you close the PR please also delete the branch"
    )
    _run_checked(
        [
            "gh",
            "pr",
            "create",
            "--title",
            f"Auto-activate {library} easy wins for {owner}",
            "--body",
            body,
            "--head",
            branch_name,
            "--base",
            "main",
            "--draft",
        ],
        runner,
    )


def _run_checked(
    args: Sequence[str],
    runner: CommandRunner,
    *,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> CommandResult:
    result = runner.run(args, env=env, input_text=input_text)
    if result.returncode != 0:
        raise RuntimeError(_command_error("Command failed", result))
    return result


def _command_error(prefix: str, result: CommandResult) -> str:
    command = " ".join(str(arg) for arg in result.args)
    details = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
    if not command:
        return details
    return f"{prefix}: {command}: {details}"


def _print_failure_summary(failures: Sequence[LibraryFailure]) -> None:
    print("============ Nightly activation failures ============")  # noqa: T201
    for failure in failures:
        print(f"{failure.library}: {failure.message}")  # noqa: T201


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run nightly easy-win activation automation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    activate = subparsers.add_parser("activate")
    activate.add_argument("--reports-dir", type=Path, required=True)
    activate.add_argument("--commit-headless", type=Path, required=True)
    activate.add_argument("--repository", required=True)
    activate.add_argument("--server-url", required=True)
    activate.add_argument("--run-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("GITHUB_TOKEN is required", file=sys.stderr)  # noqa: T201
        return 1

    if args.command == "activate":
        return run_nightly_activation(
            NightlyOptions(
                reports_dir=args.reports_dir,
                commit_headless=args.commit_headless,
                github=GithubContext(repository=args.repository, server_url=args.server_url, run_id=args.run_id),
                github_token=github_token,
                auto_merge_opt_ins=AUTO_MERGE_OPT_INS,
            )
        )

    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Step 11: open or update the draft pull request with the rule changes that apply.py made.

Usage:
    python3 -m utils.scripts.review_learning.open_pr --run .review-learning/run --dry-run
    python3 -m utils.scripts.review_learning.open_pr --run .review-learning/run

The monthly review_learning job runs it after the model is done, so the model never holds the write
token. It only publishes changes to .agents/rules/code-review/*.md, and it refuses any other change.
The pull request is always a draft, and it never merges by itself: system-tests-core reviews it.
If a review-learning pull request is still open, it publishes nothing, so a reviewer never loses work.
Outside CI, it only runs with --dry-run, so it never changes a local checkout.

It reuses the signed-commit flow of update_agent_version.py (commit-headless and the GitHub API).
"""

from __future__ import annotations

import argparse
import os
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.review_learning.common import LENSES_DIR, REPOSITORY, read_json
from utils.scripts.update_agent_version import GitHubApi, push_signed_commit, revoke_token, run_command

if TYPE_CHECKING:
    from collections.abc import Mapping

BRANCH = "review-learning/update"
OCTO_STS_POLICY = "self.gitlab-review-learning-pr"
MAX_REPORT_CHARS = 60_000  # GitHub refuses a pull request body above 65536 characters

REVIEW_GUIDE = """This pull request comes from the monthly `review_learning` job (see `docs/ai/review-learning.md`).
It only edits `.agents/rules/code-review/`.

**How to review**
- The report below lists the evidence of each change: the pull requests and the verified quotes.
- To reject a change, revert it in this pull request. If the reason holds for the future, write it in the rule,
  for example as `Not when:`. The job reads the rules, so it never proposes the opposite again.
- This pull request never merges by itself. A person from `system-tests-core` approves it.
- The next monthly run publishes nothing while this pull request is open.
"""


class UnexpectedChangeError(RuntimeError):
    """The working tree holds a change outside the lens files, so nothing is published."""


def changed_paths(root: Path) -> list[str]:
    """Return the tracked files that differ from HEAD."""
    output = run_command(root, ["git", "diff", "--name-only", "HEAD"], capture_stdout=True).stdout
    return sorted(line for line in output.splitlines() if line)


def check_paths(paths: list[str]) -> None:
    lens_dir = f"{LENSES_DIR}/"
    unexpected = [
        p for p in paths if not (p.startswith(lens_dir) and p.endswith(".md") and "/" not in p[len(lens_dir) :])
    ]
    if unexpected:
        raise UnexpectedChangeError(f"only lens files can be published, not: {', '.join(unexpected)}")


def pr_title(run_dir: Path) -> str:
    index = read_json(run_dir / "index.json")
    return f"Review learning: rule changes from {index['start']} to {index['end']}"


def pr_body(run_dir: Path, job_url: str | None) -> str:
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    if len(report) > MAX_REPORT_CHARS:
        report = report[:MAX_REPORT_CHARS] + "\n\n[The report is cut here. The job artifacts hold the full report.]\n"
    job = f"\nJob: {job_url}\n" if job_url else ""
    # The report quotes pull request text: break every @mention, so that it never notifies anyone.
    return f"{REVIEW_GUIDE}{job}\n---\n\n{report.replace('@', '@\u200b')}"


def find_open_pr(github: GitHubApi) -> int | None:
    head = urllib.parse.quote(f"DataDog:{BRANCH}", safe="")
    pull_requests = github.request("GET", f"/repos/{REPOSITORY}/pulls?head={head}&state=open")
    if not isinstance(pull_requests, list):
        raise TypeError("GitHub returned an invalid pull request list")
    numbers = [pr["number"] for pr in pull_requests if isinstance(pr, dict) and isinstance(pr.get("number"), int)]
    return numbers[0] if numbers else None


def commit_changes(root: Path, paths: list[str], title: str, env: Mapping[str, str]) -> str:
    """Commit the lens files on BRANCH, and return the base commit that commit-headless pushes on."""
    base_sha = run_command(root, ["git", "rev-parse", "HEAD"], capture_stdout=True, env=env).stdout.strip()
    run_command(root, ["git", "switch", "--force-create", BRANCH], env=env)
    run_command(root, ["git", "add", "--", *paths], env=env)
    identity = ["-c", "user.name=github-actions[bot]", "-c", "user.email=github-actions[bot]@users.noreply.github.com"]
    run_command(root, ["git", *identity, "commit", "-m", title], env=env)
    return base_sha


def publish(root: Path, run_dir: Path, paths: list[str], github: GitHubApi, env: Mapping[str, str]) -> object:
    """Open a new draft pull request. If one is still open, leave it as it is and publish nothing."""
    if (number := find_open_pr(github)) is not None:
        return f"#{number} is still open: review and close it first. Nothing is published."
    title = pr_title(run_dir)
    body = pr_body(run_dir, env.get("CI_JOB_URL"))
    base_sha = commit_changes(root, paths, title, env)
    print(f"Pushed signed commit {push_signed_commit(root, base_sha, github, env, BRANCH)} to {BRANCH}")
    data: dict[str, object] = {"base": "main", "head": BRANCH, "draft": True, "title": title, "body": body}
    return github.request("POST", f"/repos/{REPOSITORY}/pulls", data)


def write_token(root: Path) -> str:
    scope_args = ["--scope", REPOSITORY, "--policy", OCTO_STS_POLICY]
    token = run_command(root, ["dd-octo-sts", "token", *scope_args], capture_stdout=True, quiet=True).stdout.strip()
    if not token:
        raise RuntimeError("dd-octo-sts returned an empty GitHub token")
    return token


def print_dry_run(run_dir: Path, paths: list[str]) -> None:
    print(f"Would publish {', '.join(paths)} on {BRANCH}, with the title: {pr_title(run_dir)}")
    print(pr_body(run_dir, os.environ.get("CI_JOB_URL")))


def publish_with_token(root: Path, run_dir: Path, paths: list[str]) -> None:
    """Ask for the write token, publish, and always revoke the token."""
    token = write_token(root)
    try:
        result = publish(root, run_dir, paths, GitHubApi(token), {**os.environ, "GH_TOKEN": token})
        print(result.get("html_url") if isinstance(result, dict) else result)
    finally:
        revoke_token(root, token)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="print the pull request, and publish nothing")
    args = parser.parse_args()
    paths = changed_paths(args.repo_root)
    if not paths:
        print("No rule changes: no pull request.")
        return
    check_paths(paths)
    if args.dry_run:
        print_dry_run(args.run, paths)
    elif os.environ.get("GITLAB_CI") != "true":
        raise SystemExit("open_pr.py only publishes from the GitLab job. Use --dry-run locally.")
    else:
        publish_with_token(args.repo_root, args.run, paths)


if __name__ == "__main__":
    main()

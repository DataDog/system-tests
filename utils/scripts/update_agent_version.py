#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
AUTOMATION_BRANCH = "update-agent-version"
REPOSITORY = "DataDog/system-tests"
OCTO_STS_POLICY = "self.gitlab-update-agent-version"
GITHUB_API_URL = "https://api.github.com"
AUTO_MERGE_ALREADY_ENABLED = "auto merge is already enabled"

AGENT_VERSION_LOCK = Path("utils/build/virtual_machine/agent.lock")


def normalize_version(version: str) -> str:
    normalized = version.removeprefix("v")
    if VERSION_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Expected a stable Agent version, got: {version}")
    return normalized


def version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = normalize_version(version).split(".")
    return int(major), int(minor), int(patch)


def locked_agent_version(root: Path) -> str:
    for line in (root / AGENT_VERSION_LOCK).read_text().splitlines():
        if line.startswith("DD_AGENT_VERSION="):
            return normalize_version(line.removeprefix("DD_AGENT_VERSION="))
    raise ValueError(f"No DD_AGENT_VERSION found in {AGENT_VERSION_LOCK}")


def update_agent_version(root: Path, version: str) -> bool:
    normalized = normalize_version(version)
    lock_path = root / AGENT_VERSION_LOCK
    updated = f"# Pinned Agent version, updated automatically\nDD_AGENT_VERSION={normalized}\n"
    if lock_path.read_text() == updated:
        return False
    lock_path.write_text(updated)
    return True


def run_command(
    root: Path,
    args: Sequence[str],
    *,
    capture_output: bool = False,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=root, check=True, capture_output=capture_output, text=True, env=env)


class GitHubApi:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(self, method: str, path: str, data: dict[str, object] | None = None) -> object:
        request = urllib.request.Request(  # noqa: S310
            f"{GITHUB_API_URL}{path}",
            data=json.dumps(data).encode() if data is not None else None,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request) as response:  # noqa: S310
            return json.load(response)


def latest_agent_version(github: GitHubApi) -> str:
    release = github.request("GET", "/repos/DataDog/datadog-agent/releases/latest")
    if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
        raise TypeError("GitHub returned an invalid latest Agent release")
    return normalize_version(release["tag_name"])


def enable_auto_merge(github: GitHubApi, pull_request_node_id: str) -> None:
    result = github.request(
        "POST",
        "/graphql",
        {
            "query": "mutation($pullRequestId: ID!) { enablePullRequestAutoMerge(input: {"
            "pullRequestId: $pullRequestId, mergeMethod: SQUASH}) { pullRequest { number } } }",
            "variables": {"pullRequestId": pull_request_node_id},
        },
    )
    if not isinstance(result, dict):
        raise TypeError("GitHub returned an invalid auto-merge response")
    errors = result.get("errors") or []
    if not isinstance(errors, list):
        raise TypeError("GitHub returned an invalid auto-merge response")
    # A refreshed PR keeps the auto-merge enabled by a previous run, and GitHub rejects enabling it twice.
    if any(
        not isinstance(error, dict) or AUTO_MERGE_ALREADY_ENABLED not in str(error.get("message", "")).lower()
        for error in errors
    ):
        raise RuntimeError("GitHub failed to enable pull request auto-merge")


def publish_update(root: Path, version: str, github: GitHubApi, env: Mapping[str, str]) -> None:
    run_command(root, ["git", "remote", "set-url", "origin", f"https://github.com/{REPOSITORY}.git"], env=env)
    run_command(root, ["git", "switch", "--force-create", AUTOMATION_BRANCH], env=env)
    run_command(root, ["git", "add", str(AGENT_VERSION_LOCK)], env=env)
    run_command(root, ["git", "config", "user.name", "github-actions[bot]"], env=env)
    run_command(root, ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], env=env)
    run_command(
        root,
        ["git", "config", "credential.helper", "!f() { echo username=x-access-token; echo password=$GH_TOKEN; }; f"],
        env=env,
    )
    run_command(root, ["git", "commit", "-m", f"Update Agent to {version}"], env=env)
    run_command(root, ["git", "push", "--force", "--set-upstream", "origin", AUTOMATION_BRANCH], env=env)

    head = urllib.parse.quote(f"DataDog:{AUTOMATION_BRANCH}", safe="")
    pull_requests = github.request("GET", f"/repos/{REPOSITORY}/pulls?head={head}&state=open")
    if not isinstance(pull_requests, list):
        raise TypeError("GitHub returned an invalid pull request list")
    description: dict[str, object] = {
        "title": f"Update Agent to {version}",
        "body": "Automated daily update of the Agent version pinned by SSI tests. "
        "The PR will merge automatically after all required checks pass.",
    }
    if pull_requests:
        # The branch is force-pushed, so the open PR now describes the previous version: overwrite it.
        existing = pull_requests[0]
        if not isinstance(existing, dict) or not isinstance(existing.get("number"), int):
            raise TypeError("GitHub returned an invalid pull request list")
        pull_request = github.request("PATCH", f"/repos/{REPOSITORY}/pulls/{existing['number']}", description)
    else:
        pull_request = github.request(
            "POST",
            f"/repos/{REPOSITORY}/pulls",
            {"base": "main", "head": AUTOMATION_BRANCH, **description},
        )
    if not isinstance(pull_request, dict) or not isinstance(pull_request.get("node_id"), str):
        raise TypeError("GitHub returned an invalid pull request")
    enable_auto_merge(github, pull_request["node_id"])


def automate_update(root: Path, github: GitHubApi, env: Mapping[str, str], version: str | None = None) -> bool:
    normalized = normalize_version(version) if version is not None else latest_agent_version(github)
    locked = locked_agent_version(root)
    if version_key(normalized) <= version_key(locked):
        # GitHub reports the most recently published release as the latest one, not the highest
        # version: a patch released on an older branch must not roll the pin backward.
        print(f"Agent pin {locked} is not older than {normalized}")
        return False

    if not update_agent_version(root, normalized):
        print(f"Agent pins already current: {normalized}")
        return False

    publish_update(root, normalized, github, env)
    print(f"Published Agent pin update: {normalized}")
    return True


def revoke_token(root: Path, token: str) -> None:
    try:
        run_command(root, ["dd-octo-sts", "revoke", "-t", token], capture_output=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"dd-octo-sts token revocation failed with exit code {error.returncode}") from None


def run_automation(root: Path, version: str | None = None) -> bool:
    scope_args = ["--scope", REPOSITORY, "--policy", OCTO_STS_POLICY]
    run_command(root, ["dd-octo-sts", "version"])
    run_command(root, ["dd-octo-sts", "debug", *scope_args])
    token = run_command(root, ["dd-octo-sts", "token", *scope_args], capture_output=True).stdout.strip()
    if not token:
        raise RuntimeError("dd-octo-sts returned an empty GitHub token")

    github_env = os.environ.copy()
    github_env["GH_TOKEN"] = token
    github = GitHubApi(token)
    try:
        return automate_update(root, github, github_env, version)
    finally:
        revoke_token(root, token)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish an automated update of the Agent version pinned by SSI scenarios"
    )
    parser.add_argument("--version", help="Override the latest stable Agent version")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_automation(args.root, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

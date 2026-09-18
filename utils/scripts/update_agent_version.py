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


PIN_COMMENT = "Pinned Agent version, updated automatically"
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
AUTOMATION_BRANCH = "apmsp-3752/update-agent-version"
REPOSITORY = "DataDog/system-tests"
OCTO_STS_POLICY = "self.gitlab-update-agent-version"
GITHUB_API_URL = "https://api.github.com"

INSTALLER_PROVISION = Path("utils/build/virtual_machine/provisions/auto-inject/auto-inject_installer_manual.yml")
DOCKER_COMPOSE_PROVISION = Path(
    "utils/build/virtual_machine/provisions/auto-inject/docker/docker-compose-agent-prod.yml"
)


def normalize_version(version: str) -> str:
    normalized = version.removeprefix("v")
    if VERSION_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Expected a stable Agent version, got: {version}")
    return normalized


def _replace_once(path: Path, pattern: re.Pattern[str], replacement: str) -> bool:
    content = path.read_text()
    updated, replacement_count = pattern.subn(replacement, content)
    if replacement_count != 1:
        raise RuntimeError(f"Expected exactly one Agent version pin in {path}, found {replacement_count}")
    if updated == content:
        return False
    path.write_text(updated)
    return True


def update_agent_version(root: Path, version: str) -> bool:
    normalized = normalize_version(version)
    major_version, minor_version = normalized.split(".", maxsplit=1)

    installer_changed = _replace_once(
        root / INSTALLER_PROVISION,
        re.compile(
            rf"(?m)^    # {re.escape(PIN_COMMENT)}\n"
            r"    export DD_AGENT_MAJOR_VERSION=[^\n]+\n"
            r"    export DD_AGENT_MINOR_VERSION=[^\n]+$"
        ),
        f"    # {PIN_COMMENT}\n"
        f"    export DD_AGENT_MAJOR_VERSION={major_version}\n"
        f"    export DD_AGENT_MINOR_VERSION={minor_version}",
    )
    compose_changed = _replace_once(
        root / DOCKER_COMPOSE_PROVISION,
        re.compile(
            rf"(?m)^    # {re.escape(PIN_COMMENT)}\n"
            r"    image: gcr\.io/datadoghq/agent:[^\n]+$"
        ),
        f"    # {PIN_COMMENT}\n    image: gcr.io/datadoghq/agent:{normalized}",
    )
    return installer_changed or compose_changed


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


def publish_update(root: Path, version: str, github: GitHubApi, env: Mapping[str, str]) -> None:
    run_command(root, ["git", "remote", "set-url", "origin", f"https://github.com/{REPOSITORY}.git"], env=env)
    run_command(root, ["git", "switch", "--force-create", AUTOMATION_BRANCH], env=env)
    run_command(root, ["git", "add", str(INSTALLER_PROVISION), str(DOCKER_COMPOSE_PROVISION)], env=env)
    run_command(root, ["git", "config", "user.name", "github-actions[bot]"], env=env)
    run_command(root, ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], env=env)
    run_command(
        root,
        ["git", "config", "credential.helper", "!f() { echo username=x-access-token; echo password=$GH_TOKEN; }; f"],
        env=env,
    )
    run_command(root, ["git", "commit", "-m", f"APMSP-3752 update Agent to {version}"], env=env)
    run_command(root, ["git", "push", "--force", "--set-upstream", "origin", AUTOMATION_BRANCH], env=env)

    head = urllib.parse.quote(f"DataDog:{AUTOMATION_BRANCH}", safe="")
    pull_requests = github.request("GET", f"/repos/{REPOSITORY}/pulls?head={head}&state=open")
    if not isinstance(pull_requests, list):
        raise TypeError("GitHub returned an invalid pull request list")
    if pull_requests:
        pull_request = pull_requests[0]
    else:
        pull_request = github.request(
            "POST",
            f"/repos/{REPOSITORY}/pulls",
            {
                "base": "main",
                "head": AUTOMATION_BRANCH,
                "title": f"APMSP-3752 Update Agent to {version}",
                "body": "Automated daily update of the Agent version pinned by SSI tests. "
                "The PR will merge automatically after all required checks pass.",
            },
        )
    if not isinstance(pull_request, dict) or not isinstance(pull_request.get("node_id"), str):
        raise TypeError("GitHub returned an invalid pull request")
    auto_merge_result = github.request(
        "POST",
        "/graphql",
        {
            "query": "mutation($pullRequestId: ID!) { enablePullRequestAutoMerge(input: {"
            "pullRequestId: $pullRequestId, mergeMethod: SQUASH}) { pullRequest { number } } }",
            "variables": {"pullRequestId": pull_request["node_id"]},
        },
    )
    if not isinstance(auto_merge_result, dict) or auto_merge_result.get("errors"):
        raise RuntimeError("GitHub failed to enable pull request auto-merge")


def automate_update(root: Path, github: GitHubApi, env: Mapping[str, str], version: str | None = None) -> bool:
    normalized = normalize_version(version) if version is not None else latest_agent_version(github)
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

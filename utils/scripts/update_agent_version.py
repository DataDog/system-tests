#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


PIN_COMMENT = "Pinned Agent version, updated automatically by APMSP-3752"
PIN_COMMENT_PATTERN = rf"(?:Pin to .* agent release\. APMSP-[0-9]+|{re.escape(PIN_COMMENT)})"
VERSION_PATTERN = re.compile(r"^7\.[0-9]+\.[0-9]+$")
AUTOMATION_BRANCH = "apmsp-3752/update-agent-version"
REPOSITORY = "DataDog/system-tests"
OCTO_STS_POLICY = "self.gitlab-update-agent-version"

INSTALLER_PROVISION = Path("utils/build/virtual_machine/provisions/auto-inject/auto-inject_installer_manual.yml")
DOCKER_COMPOSE_PROVISION = Path(
    "utils/build/virtual_machine/provisions/auto-inject/docker/docker-compose-agent-prod.yml"
)


def normalize_version(version: str) -> str:
    normalized = version.removeprefix("v")
    if VERSION_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"Expected a stable Agent 7 version, got: {version}")
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
    minor_version = normalized.removeprefix("7.")

    installer_changed = _replace_once(
        root / INSTALLER_PROVISION,
        re.compile(
            rf"(?m)^    # {PIN_COMMENT_PATTERN}\n"
            r"    export DD_AGENT_MAJOR_VERSION=[^\n]+\n"
            r"    export DD_AGENT_MINOR_VERSION=[^\n]+$"
        ),
        f"    # {PIN_COMMENT}\n    export DD_AGENT_MAJOR_VERSION=7\n    export DD_AGENT_MINOR_VERSION={minor_version}",
    )
    compose_changed = _replace_once(
        root / DOCKER_COMPOSE_PROVISION,
        re.compile(
            rf"(?m)^    # {PIN_COMMENT_PATTERN}\n"
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


def latest_agent_version(root: Path, env: Mapping[str, str] | None = None) -> str:
    result = run_command(
        root,
        ["gh", "api", "repos/DataDog/datadog-agent/releases/latest", "--jq", ".tag_name"],
        capture_output=True,
        env=env,
    )
    return normalize_version(result.stdout.strip())


def publish_update(root: Path, version: str, env: Mapping[str, str] | None = None) -> None:
    run_command(root, ["gh", "auth", "setup-git"], env=env)
    run_command(root, ["git", "remote", "set-url", "origin", f"https://github.com/{REPOSITORY}.git"], env=env)
    run_command(root, ["git", "switch", "--force-create", AUTOMATION_BRANCH], env=env)
    run_command(root, ["git", "add", str(INSTALLER_PROVISION), str(DOCKER_COMPOSE_PROVISION)], env=env)
    run_command(root, ["git", "config", "user.name", "github-actions[bot]"], env=env)
    run_command(root, ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], env=env)
    run_command(root, ["git", "commit", "-m", f"APMSP-3752 update Agent to {version}"], env=env)
    run_command(root, ["git", "push", "--force", "--set-upstream", "origin", AUTOMATION_BRANCH], env=env)

    existing_pr = run_command(
        root,
        ["gh", "pr", "list", "--head", AUTOMATION_BRANCH, "--state", "open", "--json", "number", "--jq", ".[0].number"],
        capture_output=True,
        env=env,
    ).stdout.strip()
    if not existing_pr:
        run_command(
            root,
            [
                "gh",
                "pr",
                "create",
                "--base",
                "main",
                "--head",
                AUTOMATION_BRANCH,
                "--title",
                f"APMSP-3752 Update Agent to {version}",
                "--body",
                "Automated daily update of the Agent version pinned by SSI tests. "
                "The PR will merge automatically after all required checks pass.",
            ],
            env=env,
        )
    run_command(root, ["gh", "pr", "merge", AUTOMATION_BRANCH, "--auto", "--squash"], env=env)


def automate_update(root: Path, version: str | None = None, env: Mapping[str, str] | None = None) -> bool:
    normalized = normalize_version(version) if version is not None else latest_agent_version(root, env)
    if not update_agent_version(root, normalized):
        print(f"Agent pins already current: {normalized}")
        return False

    publish_update(root, normalized, env)
    print(f"Published Agent pin update: {normalized}")
    return True


def run_automation(root: Path, version: str | None = None) -> bool:
    scope_args = ["--scope", REPOSITORY, "--policy", OCTO_STS_POLICY]
    run_command(root, ["dd-octo-sts", "version"])
    run_command(root, ["dd-octo-sts", "debug", *scope_args])
    token = run_command(root, ["dd-octo-sts", "token", *scope_args], capture_output=True).stdout.strip()
    if not token:
        raise RuntimeError("dd-octo-sts returned an empty GitHub token")

    github_env = os.environ.copy()
    github_env["GH_TOKEN"] = token
    try:
        return automate_update(root, version, github_env)
    finally:
        run_command(root, ["dd-octo-sts", "revoke", "-t", token])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish an automated update of the Agent version pinned by SSI scenarios"
    )
    parser.add_argument("--version", help="Override the latest stable Agent 7 version")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_automation(args.root, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

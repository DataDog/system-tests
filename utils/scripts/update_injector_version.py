#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from utils.scripts.update_agent_version import GitHubApi, PinUpdate, publish_update, revoke_token, run_command

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


# Injector OCI tags carry a package revision: the registry has no bare x.y.z tag.
VERSION_PATTERN = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)-([0-9]+)$")
REPOSITORY = "DataDog/system-tests"
OCTO_STS_POLICY = "self.gitlab-update-injector-version"
INJECTOR_TAGS_URL = "https://install.datadoghq.com/v2/apm-inject-package/tags/list"

AUTO_INJECT_LOCK = Path("utils/build/auto_inject.lock")

INJECTOR_PIN_UPDATE = PinUpdate(
    name="injector",
    lock_path=AUTO_INJECT_LOCK,
    branch="update-injector-version",
    body="Automated daily update of the injector version pinned by SSI tests to the latest release "
    "published on install.datadoghq.com. The PR will merge automatically after all required checks pass.",
)


def version_key(version: str) -> tuple[int, int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Expected a released injector OCI tag (x.y.z-N), got: {version}")
    major, minor, patch, revision = match.groups()
    return int(major), int(minor), int(patch), int(revision)


def locked_injector_version(root: Path) -> str:
    version = (root / AUTO_INJECT_LOCK).read_text().strip()
    version_key(version)
    return version


def update_injector_version(root: Path, version: str) -> bool:
    version_key(version)
    lock_path = root / AUTO_INJECT_LOCK
    updated = f"{version}\n"
    if lock_path.read_text() == updated:
        return False
    lock_path.write_text(updated)
    return True


def fetch_injector_tags() -> list[object]:
    with urllib.request.urlopen(INJECTOR_TAGS_URL) as response:  # noqa: S310
        tag_list = json.load(response)
    if not isinstance(tag_list, dict) or not isinstance(tag_list.get("tags"), list):
        raise TypeError("The registry returned an invalid injector tag list")
    return tag_list["tags"]


def latest_injector_version(tags: Sequence[object]) -> str:
    # The registry also holds floating tags (0, 0.71) and dev, beta and rc builds: only releases qualify.
    released = [tag for tag in tags if isinstance(tag, str) and VERSION_PATTERN.fullmatch(tag)]
    if not released:
        raise ValueError("The registry returned no released injector tags")
    return max(released, key=version_key)


def automate_update(root: Path, github: GitHubApi, env: Mapping[str, str], version: str | None = None) -> bool:
    latest = version if version is not None else latest_injector_version(fetch_injector_tags())
    locked = locked_injector_version(root)
    if version_key(latest) <= version_key(locked):
        print(f"Injector pin {locked} is not older than {latest}")
        return False

    update_injector_version(root, latest)
    publish_update(root, latest, github, env, INJECTOR_PIN_UPDATE)
    print(f"Published injector pin update: {latest}")
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
    github = GitHubApi(token)
    try:
        return automate_update(root, github, github_env, version)
    finally:
        revoke_token(root, token)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish an automated update of the injector version pinned by SSI scenarios"
    )
    parser.add_argument("--version", help="Override the latest released injector version (x.y.z-N)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_automation(args.root, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

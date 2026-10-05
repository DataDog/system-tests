#!/usr/bin/env python3
# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
"""Bump the pinned Datadog Lambda Extension version in the lambda base images.

The extension is pinned (not `:latest`) because the base-image content hash only
covers local build-context files: a floating tag would freeze silently on the
image's first build and never refresh (see utils/build/docker/python_lambda/runtime.base.Dockerfile,
utils/build/docker/java_lambda/runtime.base.Dockerfile, and
utils/build/docker/ruby_lambda/runtime.base.Dockerfile). This script keeps that pin current.
"""

import re
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILES = [
    REPO_ROOT / "utils" / "build" / "docker" / "python_lambda" / "runtime.base.Dockerfile",
    REPO_ROOT / "utils" / "build" / "docker" / "java_lambda" / "runtime.base.Dockerfile",
    REPO_ROOT / "utils" / "build" / "docker" / "ruby_lambda" / "runtime.base.Dockerfile",
]

REGISTRY = "public.ecr.aws"
REPOSITORY = "datadog/lambda-extension"

_PINNED_IMAGE = re.compile(rf"({re.escape(REGISTRY)}/{re.escape(REPOSITORY)}):(\d+)")


def _anonymous_token() -> str:
    """Fetch a pull-scoped anonymous token for the public ECR registry."""
    response = requests.get(
        f"https://{REGISTRY}/token/",
        params={"service": REGISTRY, "scope": f"repository:{REPOSITORY}:pull"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_latest_stable_version() -> str:
    """Return the highest plain-numeric tag published for the extension image.

    Tags such as ``100-alpine`` or ``100-fips`` are build variants of the same
    release and are ignored; only bare numeric tags (e.g. ``100``) are considered.
    """
    token = _anonymous_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://{REGISTRY}/v2/{REPOSITORY}/tags/list"

    numeric_tags: list[int] = []
    next_url: str | None = url
    while next_url:
        response = requests.get(next_url, headers=headers, timeout=30)
        response.raise_for_status()
        numeric_tags += [int(tag) for tag in response.json()["tags"] if tag.isdigit()]

        # The registry API paginates via a standard Link header when there are more results.
        link = response.links.get("next")
        next_url = link["url"] if link else None

    if not numeric_tags:
        raise ValueError(f"No numeric tags found for {REGISTRY}/{REPOSITORY}")

    return str(max(numeric_tags))


def update_pinned_version(dockerfile: Path, new_version: str) -> bool:
    """Update the pinned tag in the given base Dockerfile. Returns whether it changed."""
    text = dockerfile.read_text()
    match = _PINNED_IMAGE.search(text)
    if match is None:
        raise ValueError(f"{dockerfile}: could not find a pinned {REGISTRY}/{REPOSITORY}:<version> reference")

    current_version = match.group(2)
    if current_version == new_version:
        return False

    updated_text = _PINNED_IMAGE.sub(rf"\g<1>:{new_version}", text)
    dockerfile.write_text(updated_text)
    return True


def main() -> int:
    """Bump the pinned lambda-extension version if a newer one is published.

    Returns:
        0 if an update was made, 1 if already up to date

    """
    print(f"Fetching latest {REPOSITORY} version...")
    latest_version = get_latest_stable_version()
    print(f"Latest published version: {latest_version}")

    changed = False
    for dockerfile in DOCKERFILES:
        if update_pinned_version(dockerfile, latest_version):
            print(f"  {dockerfile.relative_to(REPO_ROOT)}: updated pinned lambda-extension version to {latest_version}")
            changed = True
        else:
            print(f"  {dockerfile.relative_to(REPO_ROOT)}: already pinned to {latest_version}")

    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())

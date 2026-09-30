#!/usr/bin/env python3
# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
"""Bump pinned AWS Lambda base-runtime image digests in the lambda base images.

These images are pinned by digest (not a floating tag like `:17`) because AWS moves
such tags in place for runtime/OS/security updates, and the base-image content hash
only covers local build-context files: a floating tag would freeze silently on the
image's first build and never refresh (see utils/build/docker/java_lambda/runtime.base.Dockerfile).
This script keeps that pin current.
"""

import re
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "public.ecr.aws"

# (repository, tag, dockerfile) for every AWS Lambda runtime image pinned by digest.
RUNTIME_IMAGES = [
    ("lambda/java", "17", REPO_ROOT / "utils" / "build" / "docker" / "java_lambda" / "runtime.base.Dockerfile"),
]

_MANIFEST_ACCEPT = (
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.v2+json, "
    "application/vnd.oci.image.manifest.v1+json"
)


def _anonymous_token(repository: str) -> str:
    """Fetch a pull-scoped anonymous token for the public ECR registry."""
    response = requests.get(
        f"https://{REGISTRY}/token/",
        params={"service": REGISTRY, "scope": f"repository:{repository}:pull"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["token"]


def get_current_digest(repository: str, tag: str) -> str:
    """Return the digest a floating tag currently resolves to."""
    token = _anonymous_token(repository)
    response = requests.head(
        f"https://{REGISTRY}/v2/{repository}/manifests/{tag}",
        headers={"Authorization": f"Bearer {token}", "Accept": _MANIFEST_ACCEPT},
        timeout=30,
    )
    response.raise_for_status()
    digest = response.headers.get("Docker-Content-Digest")
    if not digest:
        raise ValueError(f"{REGISTRY}/{repository}:{tag}: response had no Docker-Content-Digest header")
    return digest


def update_pinned_digest(repository: str, tag: str, dockerfile: Path, new_digest: str) -> bool:
    """Update the pinned digest for `repository:tag` in `dockerfile`. Returns whether it changed."""
    pattern = re.compile(rf"({re.escape(REGISTRY)}/{re.escape(repository)}:{re.escape(tag)})@sha256:([0-9a-f]{{64}})")
    text = dockerfile.read_text()
    match = pattern.search(text)
    if match is None:
        raise ValueError(
            f"{dockerfile}: could not find a pinned {REGISTRY}/{repository}:{tag}@sha256:<digest> reference"
        )

    current_digest = f"sha256:{match.group(2)}"
    if current_digest == new_digest:
        return False

    updated_text = pattern.sub(rf"\g<1>@{new_digest}", text)
    dockerfile.write_text(updated_text)
    return True


def main() -> int:
    """Bump any pinned AWS Lambda runtime image digest that AWS has moved.

    Returns:
        0 if an update was made, 1 if already up to date

    """
    changed = False
    for repository, tag, dockerfile in RUNTIME_IMAGES:
        print(f"Fetching current digest for {REGISTRY}/{repository}:{tag}...")
        current_digest = get_current_digest(repository, tag)

        if update_pinned_digest(repository, tag, dockerfile, current_digest):
            print(f"  {dockerfile.relative_to(REPO_ROOT)}: updated pinned digest to {current_digest}")
            changed = True
        else:
            print(f"  {dockerfile.relative_to(REPO_ROOT)}: already pinned to {current_digest}")

    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())

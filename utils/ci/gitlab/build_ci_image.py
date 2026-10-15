"""Build (and sign) the CI images used to run system-tests jobs.

Called by the ``build_ci_image`` job in .gitlab-ci.yml. Computes the expected
tags from the content of the Dockerfiles (and requirements.txt for the
ci-runner), checks that $CI_IMAGE (utils/ci/gitlab/main.yml) matches the
computed ci-runner tag, then builds and pushes via ``docker buildx bake``
whichever of image-builder/ci-runner is missing from the registry, signing
each newly built image with ddsign.

Also used by the ``mirror_images`` job (with ``--check-only``) so both jobs
share a single implementation of the $CI_IMAGE-vs-computed-tag check instead
of each re-implementing the sha256sum/comparison logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKER_DIR = REPO_ROOT / "utils" / "ci" / "gitlab" / "docker"
REGISTRY = "registry.ddbuild.io/system-tests"
BAKE_FILE = DOCKER_DIR / "docker-bake.hcl"
IMAGES = ("image-builder", "ci-runner")


def _sha256_tag(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _image_exists(image: str) -> bool:
    result = subprocess.run(["docker", "manifest", "inspect", image], capture_output=True, check=False)
    return result.returncode == 0


def _check_ci_image(expected_image: str, ci_image: str) -> None:
    if expected_image != ci_image:
        print(f"❌ CI_IMAGE mismatch: hardcoded '{ci_image}' does not match computed '{expected_image}'")  # noqa: T201
        print("   Update CI_IMAGE in utils/ci/gitlab/main.yml:")  # noqa: T201
        print("     cat utils/ci/gitlab/docker/system-tests.Dockerfile requirements.txt | sha256sum | cut -c1-12")  # noqa: T201
        sys.exit(1)


def _build_images(targets: list[str], image_builder_tag: str, ci_runner_tag: str) -> None:
    # docker buildx bake writes --metadata-file atomically (write + rename), so an
    # already-open file descriptor to the path would still point at the old, empty
    # inode after the rename. Reserve the path, close our fd, let buildx create the
    # real file, then reopen by path to read it.
    fd, metadata_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    subprocess.run(
        [
            "docker",
            "buildx",
            "bake",
            "--push",
            "--metadata-file",
            metadata_path,
            "-f",
            str(BAKE_FILE),
            *targets,
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "IMAGE_BUILDER_TAG": image_builder_tag, "CI_RUNNER_TAG": ci_runner_tag},
        check=True,
    )
    metadata = json.loads(Path(metadata_path).read_text())

    for name in targets:
        digest = metadata[name]["containerimage.digest"]
        subprocess.run(["ddsign", "sign", f"{REGISTRY}/{name}@{digest}"], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        choices=IMAGES,
        help="Only build this image instead of every image in %(choices)s",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check that $CI_IMAGE matches the computed ci-runner tag, without building/pushing anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ci_image = os.environ.get("CI_IMAGE", "")

    image_builder_tag = _sha256_tag(DOCKER_DIR / "image-builder.Dockerfile")
    ci_runner_tag = _sha256_tag(DOCKER_DIR / "system-tests.Dockerfile", REPO_ROOT / "requirements.txt")

    expected_image = f"{REGISTRY}/ci-runner:{ci_runner_tag}"

    if args.check_only:
        _check_ci_image(expected_image, ci_image)
        return

    tags = {"image-builder": image_builder_tag, "ci-runner": ci_runner_tag}

    if args.image:
        tags = {args.image: tags[args.image]}

    targets = []
    for name, tag in tags.items():
        image = f"{REGISTRY}/{name}:{tag}"
        if _image_exists(image):
            print(f"Image {image} already exists, skipping build")  # noqa: T201
        else:
            print(f"Building image {image}")  # noqa: T201
            targets.append(name)

    if targets:
        _build_images(targets, image_builder_tag, ci_runner_tag)
    else:
        print("All images already exist, nothing to build")  # noqa: T201

    _check_ci_image(expected_image, ci_image)


if __name__ == "__main__":
    main()

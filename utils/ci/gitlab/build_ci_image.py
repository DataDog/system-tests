"""Build (and sign) the CI images used to run system-tests jobs.

Called by the ``build_ci_image`` job in .gitlab-ci.yml. Computes the expected
tags from the content of the Dockerfiles (and requirements.txt and
validate_param_env.py for the ci-runner). Checks that $CI_IMAGE (utils/ci/gitlab/main.yml)
and $REVIEW_LEARNING_IMAGE (.gitlab-ci.yml) match the computed tags. Then builds and pushes
via ``docker buildx bake`` whichever of image-builder/ci-runner/review-learning is missing
from the registry, and signs each newly built image with ddsign.

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
IMAGES = ("image-builder", "ci-runner", "review-learning")


def _sha256_tag(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _image_exists(image: str) -> bool:
    result = subprocess.run(["docker", "manifest", "inspect", image], capture_output=True, check=False)
    return result.returncode == 0


# For each hardcoded image: its variable, the file that sets it, and how to compute its tag.
HARDCODED_IMAGES = {
    "ci-runner": (
        "CI_IMAGE",
        "utils/ci/gitlab/main.yml",
        "cat utils/ci/gitlab/docker/system-tests.Dockerfile requirements.txt"
        " utils/ci/gitlab/validate_param_env.py | sha256sum | cut -c1-12",
    ),
    "review-learning": (
        "REVIEW_LEARNING_IMAGE",
        ".gitlab-ci.yml",
        "cat utils/ci/gitlab/docker/review-learning.Dockerfile | sha256sum | cut -c1-12",
    ),
}


def _check_hardcoded_images(tags: dict[str, str]) -> None:
    """Report every hardcoded image that does not match its computed tag, then fail once."""
    errors = []
    for name, (variable, file, command) in HARDCODED_IMAGES.items():
        expected, hardcoded = f"{REGISTRY}/{name}:{tags[name]}", os.environ.get(variable, "")
        if hardcoded != expected:
            errors.append(f"❌ {variable} is '{hardcoded}', expected '{expected}'. Update it in {file}: {command}")
    if errors:
        print("\n".join(errors))  # noqa: T201
        sys.exit(1)


def _build_images(targets: list[str], tags: dict[str, str]) -> None:
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
        env={**os.environ, **{f"{name.upper().replace('-', '_')}_TAG": tag for name, tag in tags.items()}},
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
        help="Only check that $CI_IMAGE and $REVIEW_LEARNING_IMAGE match their computed tags, without building.",
    )
    return parser.parse_args()


def _compute_tags() -> dict[str, str]:
    return {
        "image-builder": _sha256_tag(DOCKER_DIR / "image-builder.Dockerfile"),
        "ci-runner": _sha256_tag(
            DOCKER_DIR / "system-tests.Dockerfile",
            REPO_ROOT / "requirements.txt",
            REPO_ROOT / "utils" / "ci" / "gitlab" / "validate_param_env.py",
        ),
        "review-learning": _sha256_tag(DOCKER_DIR / "review-learning.Dockerfile"),
    }


def _build_missing(names: list[str], tags: dict[str, str]) -> None:
    targets = []
    for name in names:
        image = f"{REGISTRY}/{name}:{tags[name]}"
        if _image_exists(image):
            print(f"Image {image} already exists, skipping build")  # noqa: T201
        else:
            print(f"Building image {image}")  # noqa: T201
            targets.append(name)
    if targets:
        _build_images(targets, tags)
    else:
        print("All images already exist, nothing to build")  # noqa: T201


def main() -> None:
    args = parse_args()
    tags = _compute_tags()
    if not args.check_only:
        _build_missing([args.image] if args.image else list(IMAGES), tags)
    _check_hardcoded_images(tags)


if __name__ == "__main__":
    main()

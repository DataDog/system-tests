"""Build (and sign) the CI images used to run system-tests jobs, and the proxy image they use.

Called by the ``build_ci_image*`` jobs in .gitlab-ci.yml. Computes the expected
tags from the content of the Dockerfiles (and requirements.txt for the
ci-runner) and checks that $CI_IMAGE (utils/ci/gitlab/main.yml) matches the
computed ci-runner tag.

The ci-runner and proxy images are multi-arch (see ``PLATFORMS``) so jobs can run on
both amd64 and arm64 runners. The proxy tag is the hash of its Dockerfile, which
utils/_context/containers.py recomputes to pull it when USE_IMAGE_MIRROR is set.
docker-in-docker runners cannot build multi-platform images, so (like utils/base_images/build_base_images.py):

* ``--platform <platform>`` natively builds and pushes ``<image>:<tag>-<arch>``
  (one CI job per architecture). The amd64 job also builds the amd64-only
  image-builder at ``image-builder:<tag>`` and signs it.
* ``--merge`` combines the single-platform images into the multi-arch
  ``<image>:<tag>`` and signs it with ddsign.

Each step skips images that are already published, so it is safe to re-run.

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
# Proxy used by the system-tests scenarios. GitLab CI pulls it from REGISTRY rather than
# docker.io, as docker.io only has an amd64 datadog/system-tests:proxy-v1.
PROXY_DOCKERFILE = REPO_ROOT / "utils" / "build" / "docker" / "proxy.Dockerfile"
PLATFORMS = ("linux/amd64", "linux/arm64")
# image-builder only runs the build_ci_image* amd64 jobs, so it stays single-platform.
IMAGE_BUILDER_PLATFORM = "linux/amd64"


def _sha256_tag(*paths: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _platform_tag(image: str, platform: str) -> str:
    """Return the intermediate single-platform tag merged into the multi-arch ``image``."""
    return f"{image}-{platform.rsplit('/', 1)[-1]}"


def _manifest(image: str) -> dict | None:
    """Return the manifest (or manifest list) of ``image``, or None if it is not published."""
    result = subprocess.run(["docker", "manifest", "inspect", image], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def _image_exists(image: str) -> bool:
    return _manifest(image) is not None


def _index_platforms(image: str) -> set[str]:
    """Return the platforms of the multi-arch ``image``.

    Empty if it is missing or is a single-platform image (e.g. a ci-runner tag
    published before it became multi-arch), so that it gets rebuilt as multi-arch.
    """
    manifest = _manifest(image) or {}
    return {
        f"{entry['platform']['os']}/{entry['platform']['architecture']}"
        for entry in manifest.get("manifests", [])
        if "platform" in entry
    }


def _check_ci_image(expected_image: str, ci_image: str) -> None:
    if expected_image != ci_image:
        print(f"❌ CI_IMAGE mismatch: hardcoded '{ci_image}' does not match computed '{expected_image}'")  # noqa: T201
        print("   Update CI_IMAGE in utils/ci/gitlab/main.yml:")  # noqa: T201
        print("     cat utils/ci/gitlab/docker/system-tests.Dockerfile requirements.txt | sha256sum | cut -c1-12")  # noqa: T201
        sys.exit(1)


def _sign(image: str, digest: str) -> None:
    subprocess.run(["ddsign", "sign", f"{image.rsplit(':', 1)[0]}@{digest}"], check=True)


def _bake(target: str, tag: str, platform: str) -> str:
    """Build and push ``target`` as ``tag`` for ``platform``, and return the pushed digest."""
    print(f"Building image {tag} ({platform})")  # noqa: T201
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
            "--progress=plain",
            "--metadata-file",
            metadata_path,
            "--set",
            f"{target}.tags={tag}",
            "--set",
            f"{target}.platform={platform}",
            "-f",
            str(BAKE_FILE),
            target,
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    return json.loads(Path(metadata_path).read_text())[target]["containerimage.digest"]


def build_platform(platform: str, image_builder: str, multi_arch_images: dict[str, str]) -> None:
    if platform == IMAGE_BUILDER_PLATFORM:
        if _image_exists(image_builder):
            print(f"Image {image_builder} already exists, skipping build")  # noqa: T201
        else:
            _sign(image_builder, _bake("image-builder", image_builder, platform))

    for target, image in multi_arch_images.items():
        single_platform_tag = _platform_tag(image, platform)
        if platform in _index_platforms(image):
            print(f"Image {image} already exists for {platform}, skipping build")  # noqa: T201
        elif _image_exists(single_platform_tag):
            print(f"Image {single_platform_tag} already exists, skipping build")  # noqa: T201
        else:
            # Signed by --merge, which runs on a runner that has ddsign.
            _bake(target, single_platform_tag, platform)


def merge_platforms(image: str) -> None:
    if _index_platforms(image) >= set(PLATFORMS):
        print(f"Image {image} already exists for {', '.join(PLATFORMS)}, skipping merge")  # noqa: T201
        return

    sources = [_platform_tag(image, platform) for platform in PLATFORMS]
    missing = [source for source in sources if not _image_exists(source)]
    if missing:
        print(f"❌ Cannot create {image}, single-platform image(s) not published: {', '.join(missing)}")  # noqa: T201
        print("   Did every build_ci_image_<arch> job succeed?")  # noqa: T201
        sys.exit(1)

    print(f"Creating multi-arch image {image} from {', '.join(sources)}")  # noqa: T201
    subprocess.run(["docker", "buildx", "imagetools", "create", "--tag", image, *sources], check=True)

    # The manifest list digest is the sha256 of its raw bytes.
    raw_index = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", "--raw", image], capture_output=True, check=True
    ).stdout
    index = json.loads(raw_index)

    # Sign the manifest list and each per-platform image it references.
    _sign(image, f"sha256:{hashlib.sha256(raw_index).hexdigest()}")
    for entry in index["manifests"]:
        _sign(image, entry["digest"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--platform",
        choices=PLATFORMS,
        help="Build and push the single-platform <image>:<tag>-<arch> of ci-runner and proxy (plus image-builder "
        f"on {IMAGE_BUILDER_PLATFORM})",
    )
    mode.add_argument(
        "--merge",
        action="store_true",
        help="Combine the already pushed single-platform images into the multi-arch ci-runner and proxy, and sign them",
    )
    mode.add_argument(
        "--check-only",
        action="store_true",
        help="Only check that $CI_IMAGE matches the computed ci-runner tag, without building/pushing anything.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ci_image = os.environ.get("CI_IMAGE", "")

    image_builder = f"{REGISTRY}/image-builder:{_sha256_tag(DOCKER_DIR / 'image-builder.Dockerfile')}"
    ci_runner = f"{REGISTRY}/ci-runner:" + _sha256_tag(
        DOCKER_DIR / "system-tests.Dockerfile", REPO_ROOT / "requirements.txt"
    )

    # Must match the tag computed by utils/_context/containers.py:_proxy_image_name
    proxy = f"{REGISTRY}/proxy:{_sha256_tag(PROXY_DOCKERFILE)}"
    multi_arch_images = {"ci-runner": ci_runner, "proxy": proxy}

    if args.platform:
        build_platform(args.platform, image_builder, multi_arch_images)
    elif args.merge:
        for image in multi_arch_images.values():
            merge_platforms(image)

    _check_ci_image(ci_runner, ci_image)


if __name__ == "__main__":
    main()

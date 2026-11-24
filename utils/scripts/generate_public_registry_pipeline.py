"""Write a GitLab child pipeline that publishes datadog/system-tests images to registry.datadoghq.com.

CI pulls every ``datadog/system-tests:<tag>`` image from Docker Hub today, where anonymous pulls are
rate limited. registry.datadoghq.com has no pull rate limit, but only the DataDog/public-images
pipeline can push to it. This script lists the images that system-tests uses (the base images of
``utils/build/docker/base-images.lock.json`` and the ``datadog/system-tests`` entries of
``mirror_images.lock.yaml``), checks which tags registry.datadoghq.com does not have yet, and writes
one DataDog/public-images trigger job for each of them. The source of each
copy is the system-tests mirror in registry.ddbuild.io, which the mirror_images and build_base_images
jobs fill before this script runs.

A tag that registry.datadoghq.com already has is never published again. Base image tags end with a
content hash, so they never change. To publish new content of another image (e.g. a buddy), push it
with a new tag (e.g. python_buddy-v3).

Usage:
    python utils/scripts/generate_public_registry_pipeline.py --output public-registry-pipeline.yml
"""

import argparse
from pathlib import Path
import sys
import urllib.error
import urllib.request

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
# base_image.py is stdlib-only and is imported directly, without the heavy `utils` package.
sys.path.insert(0, str(REPO_ROOT / "utils" / "base_images"))

from base_image import load_base_image_lock, mirror_base_image  # noqa: E402

MIRROR_LOCK = REPO_ROOT / "mirror_images.lock.yaml"
IMAGE_PREFIX = "datadog/system-tests:"
PUBLIC_REGISTRY = "registry.datadoghq.com"
PUBLIC_REPOSITORY = "system-tests"
MANIFEST_ACCEPT = (
    "application/vnd.oci.image.index.v1+json,"
    "application/vnd.docker.distribution.manifest.list.v2+json,"
    "application/vnd.oci.image.manifest.v1+json,"
    "application/vnd.docker.distribution.manifest.v2+json"
)


def wanted_images(mirror_lock_path: Path = MIRROR_LOCK) -> dict[str, str]:
    """Return tag -> source reference for each datadog/system-tests image."""
    images: dict[str, str] = {}
    for image in load_base_image_lock().values():
        images[image.removeprefix(IMAGE_PREFIX)] = mirror_base_image(image)

    mirror_lock = yaml.safe_load(mirror_lock_path.read_text())
    for image, entry in mirror_lock["images"].items():
        if image.startswith(IMAGE_PREFIX):
            images[image.removeprefix(IMAGE_PREFIX)] = entry["target"]
    return images


def is_published(tag: str) -> bool:
    """Return whether registry.datadoghq.com has system-tests:<tag>."""
    url = f"https://{PUBLIC_REGISTRY}/v2/{PUBLIC_REPOSITORY}/manifests/{tag}"
    request = urllib.request.Request(url, method="HEAD", headers={"Accept": MANIFEST_ACCEPT})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.status == 200  # noqa: PLR2004
    except urllib.error.HTTPError as exc:
        if exc.code == 404:  # noqa: PLR2004
            return False
        raise


def missing_images(images: dict[str, str]) -> dict[str, str]:
    """Return tag -> source reference for each image that registry.datadoghq.com does not have."""
    return {tag: source for tag, source in sorted(images.items()) if not is_published(tag)}


def child_pipeline(missing: dict[str, str]) -> dict[str, dict[str, object]]:
    """Return the child pipeline: one DataDog/public-images trigger job per image to publish."""
    if not missing:
        # A child pipeline needs at least one job.
        return {
            "nothing_to_publish": {
                "image": "registry.ddbuild.io/images/docker:29.4.0-noble-py3",
                "tags": ["arch:amd64"],
                "script": [f"echo 'All system-tests images are already on {PUBLIC_REGISTRY}'"],
            }
        }

    pipeline: dict[str, dict[str, object]] = {}
    for tag, source in missing.items():
        pipeline[f"publish_{tag}"] = {
            "trigger": {"project": "DataDog/public-images", "branch": "main", "strategy": "depend"},
            "variables": {
                "IMG_SOURCES": source,
                "IMG_DESTINATIONS": f"{PUBLIC_REPOSITORY}:{tag}",
                # `prod` selects registry.datadoghq.com only. Docker Hub already gets these images
                # from the jobs that build them.
                "IMG_REGISTRIES": "prod",
            },
        }
    return pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True, help="Path of the child pipeline file to write")
    args = parser.parse_args()

    missing = missing_images(wanted_images())
    sys.stdout.write(f"{len(missing)} image(s) to publish to {PUBLIC_REGISTRY}/{PUBLIC_REPOSITORY}\n")
    for tag, source in missing.items():
        sys.stdout.write(f"  {source} -> {PUBLIC_REGISTRY}/{PUBLIC_REPOSITORY}:{tag}\n")
    args.output.write_text(yaml.safe_dump(child_pipeline(missing), sort_keys=False))


if __name__ == "__main__":
    main()

"""Enumerate every Docker image required by the CI scenarios, for mirroring.

Companion to ``utils/scripts/get-image-list.py``: where that script emits a
docker-compose file of images to pull for a *single* scenario/library/weblog
(and drops images that already exist in the local Docker daemon), this script
unions the images across *all* CI-run ``DockerScenario`` instances and the full
library x weblog matrix, with no dependency on a running Docker daemon.

The output (one image reference per line) feeds the dd-repo-tools
``mirror_images.py add`` command, which records them in ``mirror_images.yaml``.

Run from the repository root (paths are resolved relative to the cwd, like
``get-image-list.py``).
"""

import argparse
from pathlib import Path

from utils._context._scenarios import get_all_scenarios, DockerScenario

# Scenarios excluded from the GitLab end-to-end pipeline. Mirrors the
# `excluded_scenarios` input in .gitlab-ci.yml so the mirrored image set matches
# what actually runs in CI. Override with --exclude when the CI list changes.
DEFAULT_EXCLUDED = (
    "DEBUGGER_EXPRESSION_LANGUAGE",
    "APM_TRACING_E2E_SINGLE_SPAN",
    "APM_TRACING_E2E_OTEL",
    "OTEL_COLLECTOR_E2E",
)


def _library_weblog_pairs() -> list[tuple[str, str]]:
    """Every (library, weblog) pair, derived from the weblog Dockerfiles.

    WeblogContainer.get_image_list reads utils/build/docker/<library>/<weblog>.Dockerfile,
    so the directory name is the library and the file stem is the weblog. The
    empty pair captures library-independent images (agent, integrations,
    buddies) that every get_image_list call returns regardless of arguments.
    """
    pairs = {("", "")}
    for path in Path().glob("utils/build/docker/*/*.Dockerfile"):
        pairs.add((path.parent.name, path.stem))
    return sorted(pairs)


def _is_mirrorable(image: str) -> bool:
    """Keep only images that can be pulled from a public registry and mirrored."""
    if image.startswith("system_tests/"):
        return False  # built locally, never pulled from a registry
    if "$" in image:
        return False  # unresolved Dockerfile/template placeholder (e.g. ${NORMALIZED_BRANCH})
    # already on the destination registry => nothing to mirror
    return not image.startswith("registry.ddbuild.io/")


def collect_images(excluded: set[str]) -> list[str]:
    pairs = _library_weblog_pairs()
    images: set[str] = set()
    for scenario in get_all_scenarios():
        if not isinstance(scenario, DockerScenario) or scenario.name in excluded:
            continue
        for library, weblog in pairs:
            images.update(scenario.get_image_list(library, weblog))
    return sorted(image for image in images if _is_mirrorable(image))


def main(excluded: set[str]) -> None:
    for image in collect_images(excluded):
        print(image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="mirror_images_list",
        description="List every Docker image required by the CI scenarios (for mirror_images add)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default=",".join(DEFAULT_EXCLUDED),
        help="Comma-separated scenario names to exclude (default: the CI excluded_scenarios set)",
    )
    args = parser.parse_args()
    main({name.strip() for name in args.exclude.split(",") if name.strip()})

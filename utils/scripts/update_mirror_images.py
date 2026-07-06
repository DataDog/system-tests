"""Regenerate the mirror-images manifest and lock file from the CI scenarios.

Run from a system-tests checkout, with the runner venv active:

    python utils/scripts/update_mirror_images.py

It unions every Docker image required by the CI-run ``DockerScenario`` instances
(across the full library x weblog matrix), records them in ``mirror_images.yaml``
via the dd-repo-tools ``mirror_images.py add`` command, then resolves digests
into ``mirror_images.lock.yaml`` via ``lock``.

It never pushes or mirrors anything: commit the updated ``mirror_images.yaml``
and ``mirror_images.lock.yaml`` yourself.

Companion to ``utils/scripts/get-image-list.py`` (which emits a docker-compose
file of images to pull for a *single* scenario/library/weblog); this script is
docker-free for the enumeration step and covers *all* CI scenarios at once.
``lock`` does require a registry tool (crane/skopeo/docker) and network access.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Make `utils` importable and resolve paths regardless of the caller's cwd, so a
# plain `python utils/scripts/update_mirror_images.py` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils._context._scenarios import get_all_scenarios, DockerScenario  # noqa: E402

# Pinned dd-repo-tools mirror_images.py (override with $MIRROR_IMAGES_URL).
MIRROR_IMAGES_URL = os.environ.get(
    "MIRROR_IMAGES_URL",
    "https://binaries.ddbuild.io/dd-repo-tools/default/ca/d6c8f8ec4b1fb69b36e96dc204e5f79bed6bf067/mirror_images.py",
)

# Destination registry for the mirrored images (override with $MIRROR_DEST_REGISTRY).
DEFAULT_DEST_REGISTRY = "registry.ddbuild.io/system-tests/mirror"

MIRROR_YAML = REPO_ROOT / "mirror_images.yaml"
BUILDKITD_TOML = REPO_ROOT / "utils" / "build" / "docker" / "buildkitd.toml"

# Header written when mirror_images.yaml does not exist yet. The mirror_images.py
# `add` command preserves existing comments, so this is only used on first run.
MIRROR_YAML_HEADER = """\
# Docker images mirrored into registry.ddbuild.io/system-tests/mirror.
#
# Generated: this file lists every image required by the CI scenarios.
# Regenerate after changing scenarios or weblog Dockerfiles with:
#
#   python utils/scripts/update_mirror_images.py
#
# The `mirror_images_check` CI job fails if this file is out of date.
"""

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
    for path in Path("utils/build/docker").glob("*/*.Dockerfile"):
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


def _run_mirror_images(*args: str) -> None:
    """Invoke the pinned dd-repo-tools mirror_images.py via uv."""
    if shutil.which("uv") is None:
        sys.exit("error: 'uv' is required to run mirror_images.py — install it from https://docs.astral.sh/uv/")
    env = dict(os.environ)
    env.setdefault("MIRROR_DEST_REGISTRY", DEFAULT_DEST_REGISTRY)
    cmd = [
        "uv",
        "run",
        "--no-config",
        "--script",
        MIRROR_IMAGES_URL,
        "--mirror-yaml",
        str(MIRROR_YAML),
        *args,
    ]
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def main(excluded: set[str], *, skip_lock: bool) -> None:
    # get_image_list reads Dockerfiles relative to the repo root.
    os.chdir(REPO_ROOT)

    images = collect_images(excluded)
    print(f"Collected {len(images)} mirrorable image(s) from the CI scenarios.", flush=True)

    if not MIRROR_YAML.exists():
        MIRROR_YAML.write_text(MIRROR_YAML_HEADER)

    _run_mirror_images("add", *images)
    if not skip_lock:
        _run_mirror_images("lock")
        _run_mirror_images("buildkitd", "--output", str(BUILDKITD_TOML))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="update_mirror_images",
        description="Regenerate mirror_images.yaml and mirror_images.lock.yaml from the CI scenarios",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        default=",".join(DEFAULT_EXCLUDED),
        help="Comma-separated scenario names to exclude (default: the CI excluded_scenarios set)",
    )
    parser.add_argument(
        "--skip-lock",
        action="store_true",
        help="Only update mirror_images.yaml; do not resolve digests into the lock file "
        "(used by the CI drift check, which has no registry credentials)",
    )
    args = parser.parse_args()
    main({name.strip() for name in args.exclude.split(",") if name.strip()}, skip_lock=args.skip_lock)

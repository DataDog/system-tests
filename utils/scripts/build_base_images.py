"""Rebuild and push weblog base images whose content-hash tag is missing from Docker Hub.

Run from a system-tests checkout, with the runner venv active:

    python utils/scripts/build_base_images.py

For every library with a `utils/build/docker/<library>/weblog_metadata.yml`
declaring a `base_image_dependencies` section, and for every docker-bake.hcl target
listed there:

  1. Resolve the target's bake config (context/dockerfile/args) via
     `docker buildx bake --print`.
  2. Compute a content hash from: the resolved bake config (tags excluded), the
     content of the target's Dockerfile, and the content of every git-tracked file
     under the paths listed in `base_image_dependencies`.
  3. Take the base tag declared in the bake file (e.g. "datadog/system-tests:express4.base")
     and append "-<hash12>" to get the final tag.
  4. Skip the build if that tag already exists on Docker Hub (`docker manifest inspect`);
     otherwise build and push it with that tag.

This is idempotent and safe to run on every push: it never overwrites an existing
tag, it only creates new ones when the relevant files change.

Pass --dry-run to only print the computed tag and whether it already exists,
without ever building or pushing (useful to find the tag to put in a weblog
Dockerfile's FROM clause after dependencies change).
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

# Make `utils` importable and resolve paths regardless of the caller's cwd, so a
# plain `python utils/scripts/build_base_images.py` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils._context.weblog_metadata import WeblogMetaData  # noqa: E402
from utils.const import COMPONENT_GROUPS  # noqa: E402


def _bake_file(library: str) -> Path:
    return REPO_ROOT / "utils" / "build" / "docker" / library / "docker-bake.hcl"


def _bake_config(bake_file: Path, target: str) -> dict:
    """Resolved bake config (context, dockerfile, args, tags) for a single target."""
    result = subprocess.run(
        ["docker", "buildx", "bake", "--print", "--progress", "quiet", "-f", str(bake_file), target],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["target"][target]


def _tracked_files(path: str) -> list[Path]:
    """Every git-tracked file under `path` (a file or a directory), sorted."""
    result = subprocess.run(
        ["git", "ls-files", path],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(REPO_ROOT / line for line in result.stdout.splitlines() if line)


def compute_hash(bake_config: dict, dependencies: list[str]) -> str:
    """Content hash for a base image target: bake config (minus tags) + Dockerfile
    content + content of every git-tracked file under `dependencies`.
    """
    digest = hashlib.sha256()

    config_without_tags = {k: v for k, v in bake_config.items() if k != "tags"}
    digest.update(json.dumps(config_without_tags, sort_keys=True).encode())

    dockerfile = REPO_ROOT / bake_config["context"] / bake_config["dockerfile"]
    digest.update(dockerfile.read_bytes())

    files: list[Path] = []
    for dep in dependencies:
        files.extend(_tracked_files(dep))

    for file in sorted(set(files)):
        digest.update(str(file.relative_to(REPO_ROOT)).encode())
        digest.update(file.read_bytes())

    return digest.hexdigest()[:12]


def image_exists(tag: str) -> bool:
    result = subprocess.run(
        ["docker", "manifest", "inspect", tag],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    return result.returncode == 0


def build_and_push(bake_file: Path, target: str, tag: str) -> None:
    print(f"Building and pushing {tag}")
    subprocess.run(
        [
            "docker",
            "buildx",
            "bake",
            "--push",
            "--progress=plain",
            "--set",
            f"{target}.tags={tag}",
            "-f",
            str(bake_file),
            target,
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def process_library(library: str, *, dry_run: bool) -> None:
    dependencies_by_target = WeblogMetaData.load_base_image_dependencies(library)
    if not dependencies_by_target:
        return

    bake_file = _bake_file(library)
    if not bake_file.exists():
        print(f"Warning: {library} declares base_image_dependencies but has no docker-bake.hcl, skipping")
        return

    for target, dependencies in dependencies_by_target.items():
        bake_config = _bake_config(bake_file, target)
        base_tag = bake_config["tags"][0]
        content_hash = compute_hash(bake_config, dependencies)
        tag = f"{base_tag}-{content_hash}"

        if dry_run:
            state = "exists" if image_exists(tag) else "missing"
            print(f"{library}/{target}: {tag} ({state})")
            continue

        if image_exists(tag):
            print(f"{tag} already exists, skipping")
            continue

        build_and_push(bake_file, target, tag)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild and push weblog base images with a content-hash tag")
    parser.add_argument("--library", help="Only process this library (default: all libraries)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the computed tag and whether it exists on Docker Hub; never build or push",
    )
    args = parser.parse_args()

    libraries = [args.library] if args.library else sorted(COMPONENT_GROUPS.all)
    for library in libraries:
        process_library(library, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

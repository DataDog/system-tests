"""Rebuild and push weblog base images when their content-hash tag is missing from Docker Hub.

For each library with a `utils/build/docker/<library>/docker-bake.hcl` and each target in its
"default" group, this script:

  1. Resolves the bake config via `docker buildx bake --print`.
  2. Parses `COPY` instructions in the Dockerfile for local dependencies.
  3. Hardlinks those files + the Dockerfile into an isolated build context.
  4. Hashes the bake config (tags excluded) + that context.
  5. Appends "-<hash12>" to the base tag (e.g. `datadog/system-tests:express4.base-<hash12>`).
  6. Skips if that tag already exists on Docker Hub; otherwise builds and pushes.

Idempotent: never overwrites an existing tag. Use --dry-run to print the computed tag without
building or pushing.

Dockerfile constraints (required for dependency detection to work):
  - No `ADD`; use `COPY <source> <dest>` only (one source per instruction, no remote URLs).
  - Sources are paths relative to the Dockerfile's directory; wildcards via `Path.glob()` are OK.
  - No `RUN --mount` (those paths are invisible to this script).
  - `COPY --from=<stage-or-image>` is skipped (not a local path).

The isolated build context ensures any missed dependency causes a loud build failure rather than
a silently incomplete image.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

# So `python utils/scripts/build_base_images.py` works regardless of the caller's cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils.const import COMPONENT_GROUPS  # noqa: E402

BUILD_CONTEXT_ROOT = REPO_ROOT / ".base_image_build"

_SOURCE_AND_DEST_TOKEN_COUNT = 2
_MANIFEST_INSPECT_ATTEMPTS = 3
_MANIFEST_INSPECT_RETRY_DELAY_SECONDS = 5.0
_MISSING_MANIFEST_ERRORS = ("manifest unknown", "no such manifest")


def _bake_file(library: str) -> Path:
    return REPO_ROOT / "utils" / "build" / "docker" / library / "docker-bake.hcl"


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """Run a command and print its output if it fails."""
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: command failed: {' '.join(cmd)}")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        result.check_returncode()
    return result


def _all_bake_configs(bake_file: Path) -> dict[str, dict]:
    """Return the resolved config for each default bake target."""
    result = _run(["docker", "buildx", "bake", "--print", "--progress", "quiet", "-f", str(bake_file), "default"])
    return json.loads(result.stdout)["target"]


def _files_under(context_root: Path, path: Path) -> list[Path]:
    """Return the non-ignored files under a context-relative path."""
    result = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", str(path)], cwd=context_root)
    files = sorted(Path(line) for line in result.stdout.splitlines() if line)
    if not files:
        raise ValueError(
            f"{context_root / path}: matched by a COPY source, but every file under it is "
            "gitignored (or it is not inside a git repository at all)"
        )
    return files


def _dockerfile_logical_lines(dockerfile: Path) -> list[str]:
    """Return joined Dockerfile instructions without comments or blank lines."""
    logical_lines: list[str] = []
    buffer = ""
    for raw_line in dockerfile.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if line.endswith("\\"):
            buffer += line[:-1] + " "
            continue
        buffer += line
        logical_lines.append(buffer.strip())
        buffer = ""
    if buffer:  # pragma: no cover - malformed Dockerfile ending on a continuation
        logical_lines.append(buffer.strip())
    return logical_lines


def parse_copy_dependencies(dockerfile: Path) -> list[str]:
    """Return local COPY sources and validate Dockerfile constraints."""
    dependencies: list[str] = []
    for line in _dockerfile_logical_lines(dockerfile):
        instruction, _, rest = line.partition(" ")
        instruction = instruction.upper()

        if instruction == "ADD":
            raise ValueError(f"{dockerfile}: ADD is not allowed in a base Dockerfile, use COPY instead: {line!r}")

        if instruction == "RUN" and "--mount" in rest:
            raise ValueError(f"{dockerfile}: RUN --mount is not allowed in a base Dockerfile: {line!r}")

        if instruction != "COPY":
            continue

        tokens = rest.split()
        flags = [t for t in tokens if t.startswith("--")]
        paths = [t for t in tokens if not t.startswith("--")]

        if any(flag.startswith("--from=") for flag in flags):
            continue  # copies from another build stage or an external image, not a local path

        if paths and paths[0].startswith("["):
            raise ValueError(
                f"{dockerfile}: exec-form (JSON array) COPY is not supported, use 'COPY <source> <dest>': {line!r}"
            )

        if len(paths) != _SOURCE_AND_DEST_TOKEN_COUNT:
            raise ValueError(
                f"{dockerfile}: COPY must be of the form 'COPY [flags] <source> <dest>' "
                f"(exactly one source), got: {line!r}"
            )

        source, _dest = paths
        dependencies.append(source)

    return dependencies


def _dependency_paths(context_root: Path, dockerfile: Path) -> list[Path]:
    """Return sorted, unique dependency paths within the build context."""
    files: set[Path] = set()
    for source in parse_copy_dependencies(dockerfile):
        matches = sorted(context_root.glob(source))
        if not matches:
            raise ValueError(f"{dockerfile}: COPY source {source!r} matched no files")

        for match in matches:
            resolved = match.resolve()
            try:
                relative = resolved.relative_to(context_root)
            except ValueError:
                raise ValueError(
                    f"{dockerfile}: COPY source {source!r} escapes the Dockerfile's context directory ({context_root})"
                ) from None
            files.update(_files_under(context_root, relative))
    return sorted(files)


def compute_hash(build_dir: Path, bake_config: dict) -> str:
    """Hash the bake config and materialized build context."""
    digest = hashlib.sha256()

    config_without_tags = {k: v for k, v in bake_config.items() if k != "tags"}
    digest.update(json.dumps(config_without_tags, sort_keys=True).encode())

    for file in sorted(p for p in build_dir.rglob("*") if p.is_file()):
        digest.update(str(file.relative_to(build_dir)).encode())
        digest.update(stat.S_IMODE(file.lstat().st_mode).to_bytes(4, "big"))
        digest.update(file.read_bytes())

    return digest.hexdigest()[:12]


def _link_or_copy(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, dest)
    except OSError:
        # e.g. source and dest are on different filesystems
        shutil.copy2(source, dest)


def materialize_build_context(
    library: str, target: str, context_root: Path, dockerfile: Path, dependencies: list[Path]
) -> Path:
    """Create an isolated build context containing the Dockerfile and dependencies."""
    build_dir = BUILD_CONTEXT_ROOT / library / target
    shutil.rmtree(build_dir, ignore_errors=True)
    build_dir.mkdir(parents=True)

    for file in dependencies:
        _link_or_copy(context_root / file, build_dir / file)

    _link_or_copy(dockerfile, build_dir / dockerfile.relative_to(context_root))

    print(f"Build context for {library}/{target} ({build_dir}):")
    for file in sorted(build_dir.rglob("*")):
        if file.is_file():
            print(f"  {file.relative_to(build_dir)}")

    return build_dir


def image_exists(
    tag: str,
    *,
    attempts: int = _MANIFEST_INSPECT_ATTEMPTS,
    retry_delay_seconds: float = _MANIFEST_INSPECT_RETRY_DELAY_SECONDS,
) -> bool:
    """Return whether a tag exists, retrying inconclusive registry failures."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(1, attempts + 1):
        result = subprocess.run(
            ["docker", "manifest", "inspect", tag],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True

        error = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if any(missing_error in error.lower() for missing_error in _MISSING_MANIFEST_ERRORS):
            if error:
                print(error)
            return False

        if error:
            print(error)
        if attempt < attempts:
            print(f"Warning: failed to inspect {tag}; retrying in {retry_delay_seconds}s")
            time.sleep(retry_delay_seconds)
            continue

        raise RuntimeError(f"Could not determine whether {tag} exists after {attempts} attempts")

    raise AssertionError("unreachable")


def build_and_push(bake_file: Path, target: str, tag: str, build_dir: Path, dockerfile_name: str) -> None:
    print(f"Building and pushing {tag}")
    _run(
        [
            "docker",
            "buildx",
            "bake",
            "--push",
            "--progress=plain",
            "--set",
            f"{target}.tags={tag}",
            "--set",
            f"{target}.context={build_dir}",
            "--set",
            f"{target}.dockerfile={dockerfile_name}",
            "-f",
            str(bake_file),
            target,
        ]
    )


def process_target(
    library: str, bake_file: Path, target: str, tag: str, build_dir: Path, dockerfile: str, *, dry_run: bool
) -> None:
    if dry_run:
        state = "exists" if image_exists(tag) else "missing"
        print(f"{library}/{target}: {tag} ({state})")
        return

    if image_exists(tag):
        print(f"{tag} already exists, skipping")
        return

    build_and_push(bake_file, target, tag, build_dir, dockerfile)


def process_library(library: str) -> list[tuple]:
    """Prepare each bake target for a library."""
    bake_file = _bake_file(library)
    if not bake_file.exists():
        return []

    targets = []
    for target, bake_config in _all_bake_configs(bake_file).items():
        # `docker buildx bake --print` may report `context` as absolute or relative.
        context_root = (REPO_ROOT / bake_file.parent / bake_config["context"]).resolve()
        dockerfile = context_root / bake_config["dockerfile"]

        dependencies = _dependency_paths(context_root, dockerfile)

        # Materialize before hashing, so the hash is computed from the exact files the build
        # will see.
        build_dir = materialize_build_context(library, target, context_root, dockerfile, dependencies)

        base_tag = bake_config["tags"][0]
        content_hash = compute_hash(build_dir, bake_config)
        tag = f"{base_tag}-{content_hash}"
        targets.append((library, bake_file, target, tag, build_dir, bake_config["dockerfile"]))

    return targets


def _changed_libraries() -> set[str] | None:
    """Return libraries changed from origin/main, or None if unknown."""
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--name-only", merge_base, "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        print(f"Warning: could not determine changed libraries ({exc}); processing all libraries")
        return None

    prefix = "utils/build/docker/"
    return {line[len(prefix) :].split("/", 1)[0] for line in diff.splitlines() if line.startswith(prefix)} - {""}


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild and push weblog base images with a content-hash tag")
    parser.add_argument("--library", help="Only process this library (default: all libraries)")
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only process libraries whose files changed vs the merge-base with origin/main "
        "(falls back to all libraries if that cannot be determined)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the computed tag and whether it exists on Docker Hub; never build or push",
    )
    args = parser.parse_args()

    if args.library:
        if not _bake_file(args.library).exists():
            print(f"Error: unknown library {args.library!r}: no bake file at {_bake_file(args.library)}")
            sys.exit(1)
        libraries = [args.library]
    else:
        libraries = sorted(COMPONENT_GROUPS.all)
        if args.changed_only:
            changed = _changed_libraries()
            if changed is not None:
                libraries = [lib for lib in libraries if lib in changed]
                print(f"--changed-only: processing {libraries or '(no changed libraries)'}")

    targets = []
    for library in libraries:
        targets += process_library(library)

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_target, *t, dry_run=args.dry_run): (t[0], t[2]) for t in targets}
        for future in concurrent.futures.as_completed(futures):
            library, target = futures[future]
            try:
                future.result()
            except Exception as exc:  # surface any target failure as a non-zero exit
                print(f"Error: {library}/{target} failed to build/push: {exc}")
                failures.append(f"{library}/{target}")

    if failures:
        print("The following targets failed to build/push:")
        for failure in failures:
            print(f"  {failure}")
        sys.exit(1)


if __name__ == "__main__":
    main()

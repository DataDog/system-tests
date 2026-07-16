"""Rebuild and push weblog base images whose content-hash tag is missing from Docker Hub.

Usage (from a system-tests checkout, runner venv active):

    python utils/scripts/build_base_images.py

For every library with a `utils/build/docker/<library>/docker-bake.hcl` file, and every target
in that file's "default" group:

  1. Resolve the target's bake config via `docker buildx bake --print`.
  2. Parse the Dockerfile's `COPY` instructions for local, non-gitignored dependencies.
  3. Materialize those files, plus the Dockerfile, into an isolated build context (see "Safety
     net" below).
  4. Hash the bake config (tags excluded) plus that materialized context.
  5. Append "-<hash12>" to the bake file's base tag (e.g. "datadog/system-tests:express4.base").
  6. Skip if that tag already exists on Docker Hub (`docker manifest inspect`); otherwise build
     and push.

Idempotent: never overwrites an existing tag, only creates new ones when dependencies change.

Pass --dry-run to only print the computed tag and whether it already exists, without building
or pushing (useful to find the tag for a weblog Dockerfile's FROM clause after deps change).

Base Dockerfile constraints
----------------------------
So the dependency list above can be derived mechanically from the Dockerfile alone, every
`<target>.base.Dockerfile` built by this script must follow these rules:

  - No `ADD`. Use `COPY` only (no whole-context copies, no remote URLs); wildcards are allowed
    (see "Wildcard sources" below).
  - Every `COPY` has exactly one source: `COPY [flags] <source> <dest>`.
  - The bake target's `context` is always the Dockerfile's own directory, so `COPY` sources are
    plain paths relative to it (`COPY app.js .`, not `COPY utils/build/docker/nodejs/fastify/app.js .`).
  - No `RUN --mount`: those mounts read paths this script cannot see, so they'd silently escape
    the derived dependency list.

`COPY --from=<stage-or-image>` is exempt from these rules and skipped when deriving dependencies
(not a local repository path).

Wildcard sources
-----------------
A `COPY` source is resolved with `Path.glob()` against the Dockerfile's own directory (a plain
path just matches itself). A pattern matching zero files raises (likely a typo); a pattern
matching *fewer* files than intended cannot be detected and silently ships an incomplete image.
The materialized build context's file list is printed before every build to make that case easy
to catch by eye.

Safety net: isolated build context
-----------------------------------
Every detected dependency is hardlinked (falling back to a copy, e.g. across filesystems) into
`.base_image_build/<library>/<target>/`, and the image is built from that directory instead of
the real one. This way, a Dockerfile reference the parser failed to detect as a dependency makes
the build fail loudly ("file not found") instead of silently succeeding against the full
repository checkout. The content hash is computed from this same materialized directory (see
`compute_hash`), not a separate read of the dependency paths, so the hashed files and the built
files are identical by construction.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# So `python utils/scripts/build_base_images.py` works regardless of the caller's cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils.const import COMPONENT_GROUPS  # noqa: E402

BUILD_CONTEXT_ROOT = REPO_ROOT / ".base_image_build"

_SOURCE_AND_DEST_TOKEN_COUNT = 2


def _bake_file(library: str) -> Path:
    return REPO_ROOT / "utils" / "build" / "docker" / library / "docker-bake.hcl"


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    """Run `cmd`, printing stderr (and stdout, if any) before raising on failure."""
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
    """Resolved bake config (context, dockerfile, args, tags) for every target in the bake
    file's "default" group.
    """
    result = _run(["docker", "buildx", "bake", "--print", "--progress", "quiet", "-f", str(bake_file), "default"])
    return json.loads(result.stdout)["target"]


def _files_under(context_root: Path, path: Path) -> list[Path]:
    """Every non-gitignored file under `path` (a file or directory, relative to `context_root`),
    itself relative to `context_root`, sorted.

    Filters on `.gitignore` alone, not on git-tracked status, since this script runs against a
    real checkout where untracked-but-not-ignored files are still valid dependencies.

    Raises if `path` exists on disk but every file under it is gitignored, rather than silently
    producing an empty dependency.
    """
    result = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", str(path)], cwd=context_root)
    files = sorted(Path(line) for line in result.stdout.splitlines() if line)
    if not files:
        raise ValueError(
            f"{context_root / path}: matched by a COPY source, but every file under it is "
            "gitignored (or it is not inside a git repository at all)"
        )
    return files


def _dockerfile_logical_lines(dockerfile: Path) -> list[str]:
    """Dockerfile lines with backslash-continuations joined into one logical line each, and
    full-line comments/blank lines dropped.
    """
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
    """Local `COPY` source paths (relative to `dockerfile`'s own directory) that a base
    Dockerfile depends on. Enforces this module's Dockerfile constraints: no `ADD`, no
    `RUN --mount`, and every `COPY` has exactly one source.
    """
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

        if len(paths) != _SOURCE_AND_DEST_TOKEN_COUNT:
            raise ValueError(
                f"{dockerfile}: COPY must be of the form 'COPY [flags] <source> <dest>' "
                f"(exactly one source), got: {line!r}"
            )

        source, _dest = paths
        dependencies.append(source)

    return dependencies


def _dependency_paths(context_root: Path, dockerfile: Path) -> list[Path]:
    """Every non-gitignored file (relative to `context_root`) that `dockerfile` depends on,
    sorted and deduplicated. `context_root` is `dockerfile`'s own directory.

    Each COPY source is resolved with `Path.glob()` (a plain path just matches itself). A source
    matching zero files raises (likely a typo); see this module's docstring ("Wildcard sources")
    for why a pattern matching fewer files than intended can't be detected here.

    Every match must resolve to a path under `context_root` itself, per this module's Dockerfile
    constraints (e.g. a `nodejs` base image can't depend on a file under
    `utils/build/docker/python/`).
    """
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
    """Content hash for a base image target: bake config (minus tags) + path and content of
    every file in `build_dir` (the isolated build context already materialized by
    `materialize_build_context`, including the Dockerfile itself).
    """
    digest = hashlib.sha256()

    config_without_tags = {k: v for k, v in bake_config.items() if k != "tags"}
    digest.update(json.dumps(config_without_tags, sort_keys=True).encode())

    for file in sorted(p for p in build_dir.rglob("*") if p.is_file()):
        digest.update(str(file.relative_to(build_dir)).encode())
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
    """Hardlink (falling back to a copy) every file in `dependencies` (relative to
    `context_root`, already flattened and deduplicated by `_dependency_paths`), plus `dockerfile`
    itself, into a fresh `.base_image_build/<library>/<target>/` directory, mirroring each
    file's path relative to `context_root`. Building from this directory instead of the real one
    is the safety net described in this module's docstring.
    """
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


def image_exists(tag: str) -> bool:
    """Whether `tag` exists on the registry. `docker manifest inspect` exits non-zero both for
    a genuinely missing tag and for unrelated failures (auth, network); print stderr either way
    so a real failure isn't mistaken for a missing tag.
    """
    result = subprocess.run(
        ["docker", "manifest", "inspect", tag],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and result.stderr:
        print(result.stderr.strip())
    return result.returncode == 0


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


def process_library(library: str, *, dry_run: bool) -> None:
    bake_file = _bake_file(library)
    if not bake_file.exists():
        return

    for target, bake_config in _all_bake_configs(bake_file).items():
        # `docker buildx bake --print` may report `context` as absolute or relative.
        context_root = (REPO_ROOT / bake_config["context"]).resolve()
        dockerfile = context_root / bake_config["dockerfile"]

        dependencies = _dependency_paths(context_root, dockerfile)

        # Materialize before hashing, so the hash is computed from the exact files the build
        # will see.
        build_dir = materialize_build_context(library, target, context_root, dockerfile, dependencies)

        base_tag = bake_config["tags"][0]
        content_hash = compute_hash(build_dir, bake_config)
        tag = f"{base_tag}-{content_hash}"

        if dry_run:
            state = "exists" if image_exists(tag) else "missing"
            print(f"{library}/{target}: {tag} ({state})")
            continue

        if image_exists(tag):
            print(f"{tag} already exists, skipping")
            continue

        build_and_push(bake_file, target, tag, build_dir, bake_config["dockerfile"])


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

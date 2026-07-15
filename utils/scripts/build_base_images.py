"""Rebuild and push weblog base images whose content-hash tag is missing from Docker Hub.

Run from a system-tests checkout, with the runner venv active:

    python utils/scripts/build_base_images.py

For every library with a `utils/build/docker/<library>/docker-bake.hcl` file, and for every
target in that file's "default" group:

  1. Resolve the target's bake config (context/dockerfile/args) via `docker buildx bake --print`.
  2. Parse the target's Dockerfile for its `COPY` instructions to determine which local,
     non-gitignored files (relative to the Dockerfile's own directory, which is required to be
     the bake target's context — see "Base Dockerfile constraints" below) the image depends on.
  3. Materialize those files, plus the Dockerfile itself, into an isolated build context (see
     "Safety net" below) — hardlinking is essentially free, so this always happens next, before
     even computing the hash.
  4. Compute a content hash from the resolved bake config (tags excluded) and the path and
     content of every file in that materialized build context.
  5. Take the base tag declared in the bake file (e.g. "datadog/system-tests:express4.base") and
     append "-<hash12>" to get the final tag.
  6. Skip the build if that tag already exists on Docker Hub (`docker manifest inspect`);
     otherwise build and push the already-materialized build context with that tag.

This is idempotent and safe to run on every push: it never overwrites an existing tag, it only
creates new ones when the relevant files change.

Pass --dry-run to only print the computed tag and whether it already exists, without ever
building or pushing (useful to find the tag to put in a weblog Dockerfile's FROM clause after
dependencies change).

Base Dockerfile constraints
----------------------------
So that the dependency list above can be derived mechanically and unambiguously from the
Dockerfile alone, every `<target>.base.Dockerfile` built by this script must follow these rules:

  - No `ADD`. Use `COPY` for everything (no whole-context-directory copies, no remote URLs).
    `COPY` sources may contain glob wildcards (see "Wildcard sources" below).
  - Every `COPY` instruction has exactly one source: `COPY [flags] <source> <dest>`. Split
    multi-source `COPY` instructions into one `COPY` per source.
  - The bake target's `context` is always the Dockerfile's own directory, so every `COPY`
    source is a plain path relative to that directory (`COPY app.js .`, not
    `COPY utils/build/docker/nodejs/fastify/app.js .`).
  - No `RUN --mount`. Bind/cache/secret mounts read from paths this script cannot see, so they
    would silently escape the derived dependency list.

`COPY --from=<stage-or-image>` is unaffected by these rules: multi-stage copies and copies from
an external image aren't local repository paths, so they're skipped when deriving dependencies
(buildx/buildkit resolves them independently).

Wildcard sources
-----------------
A `COPY` source is resolved with `Path.glob()` against the Dockerfile's own directory, so a
plain path (no wildcard) and a glob pattern are handled the same way: a plain path simply
matches itself, a pattern is expanded to every file/directory it matches. A pattern matching
zero files raises (almost certainly a typo), but that is the only completeness check available:
a pattern matching *fewer* files than intended does not raise, because Docker's own wildcard
expansion, run again at build time against the materialized build context (see below), only
ever sees the files that same pattern already matched when we computed dependencies — it can't
disagree with a match we already computed by construction. So an incomplete wildcard match
doesn't fail the build the way a missing literal dependency does; it just silently ships an
incomplete image. The materialized build context's file list is printed before every build
specifically to make that failure mode easy to catch by eye.

Safety net: isolated build context
-----------------------------------
Every detected dependency is hardlinked (falling back to a plain copy if hardlinking isn't
possible, e.g. across filesystems) into `.base_image_build/<library>/<target>/`, and the image
is built from *that* directory instead of the real one, after printing that directory's file
list. Hardlinking is only a directory-entry operation (no data is duplicated), so this is
essentially free. Its purpose is correctness, not performance: if the Dockerfile references a
file that the parser failed to detect as a dependency, the build fails loudly ("file not found")
instead of silently succeeding against the full repository checkout — which would let an
incomplete dependency list (and thus an under-hashed, stale-looking tag) go unnoticed. (This
guarantee does not extend to an incomplete wildcard match, see above — the printed file list is
the mitigation for that case.)

The content hash is computed directly from this materialized directory (see `compute_hash`),
not from a second, independent read of the dependency paths: this way "the files the hash was
computed from" and "the files the build can actually see" are the same files by construction,
not two separate computations that are merely supposed to produce the same result.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Make `utils` importable and resolve paths regardless of the caller's cwd, so a
# plain `python utils/scripts/build_base_images.py` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from utils.const import COMPONENT_GROUPS  # noqa: E402

BUILD_CONTEXT_ROOT = REPO_ROOT / ".base_image_build"

# A `COPY [flags] <source> <dest>` line has exactly one source and one destination path
# (see this module's docstring, "Base Dockerfile constraints").
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
    """Every non-gitignored file under `path` (a file or a directory, relative to
    `context_root`), itself relative to `context_root`, sorted.

    This deliberately filters on `.gitignore` rules alone, not on whether a file is committed
    or even staged (`--cached --others --exclude-standard` includes both tracked files and
    untracked-but-not-ignored ones): this script always runs against a real checkout, tracked
    or not, so there is nothing to gain from requiring content to be in the git index, only
    the risk of silently skipping a real, intended, not-yet-committed dependency. What must
    still be filtered out is gitignored content that happens to sit on disk under a dependency
    path (e.g. a locally installed, never-committed `node_modules/`), since that is never meant
    to be part of the image's tracked dependency set.

    Raises if `path` exists on disk (so `_dependency_paths` already accepted it as a match) but
    every file under it turns out to be gitignored, since that would otherwise silently produce
    an empty dependency with no explanation.
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
    Dockerfile depends on. Enforces the constraints listed in this module's docstring:
    no `ADD`, no `RUN --mount`, and every `COPY` has exactly one source.

    `COPY --from=<stage-or-image>` lines are recognized and skipped (not a local repo path).
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
    sorted and deduplicated. `context_root` is `dockerfile`'s own directory, per this module's
    Dockerfile constraints. This is the single place dependencies are resolved: both
    `compute_hash` and `materialize_build_context` operate on exactly this list, so "the files
    the hash was computed from" and "the files that get hardlinked" are the same set by
    construction, not by two independent computations happening to agree.

    Each COPY source is resolved with `Path.glob()`, so a plain path and a glob pattern are
    handled uniformly (a plain path just matches itself). A source matching zero files raises,
    since that's almost certainly a typo; see this module's docstring ("Wildcard sources") for
    why a pattern matching *fewer* files than intended is not, and cannot be, detected here.

    Every match must resolve to a path under `context_root` itself: per this module's Dockerfile
    constraints, a base Dockerfile's `COPY` sources are only ever meant to reach within its own
    directory (e.g. a `nodejs` base image has no business depending on a file under
    `utils/build/docker/python/`), so a source escaping `context_root` is rejected even if it
    stays inside the repository.

    Each match is then flattened to its constituent files via `_files_under`, which also filters
    out gitignored content (e.g. a locally installed, never-committed `node_modules/` sitting
    under a dependency directory): two COPY sources can overlap (a directory and one of its own
    files listed separately), so the final list is deduplicated.
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
    `materialize_build_context`, which includes the Dockerfile itself alongside its
    dependencies).

    Hashing the materialized directory directly, rather than separately re-reading dependencies
    from `context_root`, guarantees "the files the hash was computed from" and "the files the
    build can actually see" are the exact same files by construction (same inodes, even), not
    two independent reads that are merely supposed to agree.
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
    file's path relative to `context_root`.

    Building from this directory instead of the real one is a safety net: it makes "the files
    the hash was computed from" and "the files the build can actually see" the same set by
    construction, so a dependency the parser failed to detect causes a build failure (missing
    file) instead of silently succeeding against the full repository checkout.

    That guarantee doesn't extend to a wildcard COPY source matching fewer files than intended
    (see this module's docstring, "Wildcard sources"): the build can't detect that on its own,
    so the resulting file tree is printed here to make it easy to catch by eye instead.
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
    """Whether `tag` exists on the registry. `docker manifest inspect` exits non-zero both
    when the tag genuinely doesn't exist and on unrelated failures (auth, network); print
    the error either way so a real failure isn't silently mistaken for a missing tag.
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
        # REPO_ROOT is only ever used here, to locate the bake target's own context directory
        # (`docker buildx bake --print` may report it as either absolute or relative). Every
        # dependency-resolution/hash/materialize step downstream operates purely in terms of
        # context_root, never REPO_ROOT again.
        context_root = (REPO_ROOT / bake_config["context"]).resolve()
        dockerfile = context_root / bake_config["dockerfile"]

        dependencies = _dependency_paths(context_root, dockerfile)

        # Materialize before hashing (hardlinking is essentially free, see this module's
        # docstring), so the hash is always computed from the exact files the build will see,
        # never from a separate read of context_root that is merely supposed to match.
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

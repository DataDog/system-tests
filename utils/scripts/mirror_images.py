#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml==6.0.3", "dulwich==1.2.4"]
# ///
"""Manage mirrored Docker images: generate lock files, mirror, and lint.

Uses CLI tools (crane, skopeo, docker, podman, nerdctl) for registry
operations instead of Python registry libraries. Whichever tool is
available on PATH will be used.
"""

import argparse
import collections
import fnmatch
import functools
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import yaml
from dulwich.errors import NotGitRepository
from dulwich.repo import Repo

# Force line-buffered output so parallel progress lines appear immediately.
print = functools.partial(print, flush=True)  # type: ignore[assignment]

# Log-line prefix convention: human-facing diagnostics use "  [level] message"
# with level in {warning, error, fatal}. Stick to this so log filters and
# eyeballed output stay consistent across modules.

# Mirror destination registry is resolved lazily via `_dest_registry()`
# from `MIRROR_DEST_REGISTRY` or the origin remote — see the helper below.


class Digest(str):
    """A `sha256:<64 hex>` container image digest.

    Subclassing `str` so it round-trips through YAML and string formatting
    transparently while still rejecting malformed values at construction.
    """
    _RE = re.compile(r"^sha256:[0-9a-f]{64}$")

    def __new__(cls, value: str) -> "Digest":
        if not cls._RE.match(value):
            raise ValueError(
                f"invalid digest (expected sha256:<64 hex>): {value!r}")
        return super().__new__(cls, value)


# Substrings that strongly indicate an authentication/authorization failure
# from a container registry CLI's stderr. Used both to fail-fast in mirror
# Phase 2 and to distinguish "not present" from "auth broken" in checks.
_AUTH_ERROR_SIGNALS = ("unauthorized", "401", "403", "denied", "forbidden",
                       "authentication required")
# Substrings registries / CLI tools use for "manifest not found" / 404.
_NOT_FOUND_SIGNALS = ("manifest_unknown", "manifest unknown", "not found",
                      "name unknown", "no such manifest", "404")


def _is_auth_error(stderr: str) -> bool:
    s = stderr.lower()
    return any(sig in s for sig in _AUTH_ERROR_SIGNALS)


def _is_not_found(stderr: str) -> bool:
    s = stderr.lower()
    return any(sig in s for sig in _NOT_FOUND_SIGNALS)


def _find_project_dir() -> str:
    """Locate the project root: walk up from cwd until a `.git` entry is found.

    `MIRROR_IMAGES_PROJECT_DIR` overrides the auto-detection and is used as-is.
    Falls back to cwd if no `.git` is found anywhere up the tree, in which
    case path lookups will fail later with a clear FileNotFoundError.
    """
    override = os.environ.get("MIRROR_IMAGES_PROJECT_DIR")
    if override:
        return override

    current = os.getcwd()
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.getcwd()
        current = parent


PROJECT_DIR = _find_project_dir()
MIRROR_YAML = os.path.join(PROJECT_DIR, "mirror_images.yaml")
LOCK_YAML = os.path.join(PROJECT_DIR, "mirror_images.lock.yaml")


def _detect_repo_name(project_dir: str) -> str | None:
    """Best-effort repo name from the `origin` remote URL.

    Returns the last path segment with a trailing `.git` stripped, for
    both SSH (`git@host:org/repo.git`) and HTTPS URLs. None when the
    directory isn't a git repo or has no `origin` remote.
    """
    try:
        repo = Repo(project_dir)
    except NotGitRepository:
        return None
    try:
        url = repo.get_config().get((b"remote", b"origin"), b"url").decode()
    except KeyError:
        return None
    finally:
        repo.close()
    url = url.strip().removesuffix(".git")
    name = url.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return name or None


@functools.cache
def _dest_registry() -> str:
    """Mirror destination registry, resolved lazily so non-mirroring
    subcommands (`add`, `--help`) work outside a git checkout.

    `MIRROR_DEST_REGISTRY` wins; otherwise build it from the origin
    remote name; otherwise exit with instructions.
    """
    env = os.environ.get("MIRROR_DEST_REGISTRY")
    if env:
        return env
    repo = _detect_repo_name(PROJECT_DIR)
    if repo:
        return f"registry.ddbuild.io/ci/{repo}/mirror"
    print(
        "  [error] cannot determine mirror destination registry — no\n"
        "  'origin' remote found in this checkout. Set\n"
        "  MIRROR_DEST_REGISTRY=registry.ddbuild.io/ci/<repo>/mirror.",
        file=sys.stderr,
    )
    sys.exit(2)

# ---------------------------------------------------------------------------
# Registry CLI abstraction
# ---------------------------------------------------------------------------


def _find_tool(names: list[str]) -> str | None:
    """Return the first tool name found on PATH."""
    for name in names:
        if shutil.which(name):
            return name
    return None


def _find_digest_tool() -> str:
    """Find a tool that can report registry-canonical image digests.

    Only crane, skopeo, and `docker buildx imagetools` surface the canonical
    manifest digest. `docker manifest inspect`, `podman manifest inspect`
    and `nerdctl manifest inspect` return reformatted JSON whose hash does
    not match the registry's bytes, so they're rejected — the resulting
    lock file would pin digests that the source registry does not store.
    """
    tool = _find_tool(["crane", "skopeo", "docker"])
    if not tool:
        print(
            "No digest tool found. Install one of: crane, skopeo, docker (with buildx).",
            file=sys.stderr)
        sys.exit(1)
    return tool


def _find_copy_tool() -> str:
    """Find a tool that can copy images between registries."""
    tool = _find_tool(["crane", "skopeo", "docker"])
    if not tool:
        print(
            "No image copy tool found. Install one of: crane, skopeo, docker",
            file=sys.stderr)
        sys.exit(1)
    return tool


def resolve_digest(image_ref: str, tool: str) -> Digest:
    """Resolve image:tag -> sha256:... using the given CLI tool.

    All three supported tools return the registry-canonical manifest digest:
    `crane digest`, `skopeo inspect --format '{{.Digest}}'`, and
    `docker buildx imagetools inspect --format '{{.Manifest.Digest}}'`.
    Plain `docker manifest inspect` does *not* — it returns reformatted
    JSON whose sha256 doesn't match the registry's bytes — so we use the
    buildx imagetools path instead.
    """
    if tool == "crane":
        cmd = ["crane", "digest", image_ref]
    elif tool == "skopeo":
        cmd = [
            "skopeo", "inspect", "--format", "{{.Digest}}",
            f"docker://{image_ref}",
        ]
    elif tool == "docker":
        cmd = [
            "docker", "buildx", "imagetools", "inspect",
            "--format", "{{.Manifest.Digest}}", image_ref,
        ]
    else:
        raise ValueError(f"Unknown tool: {tool}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{tool} failed for {image_ref}: {result.stderr.strip()}")

    return Digest(result.stdout.strip())


def check_digest_exists(image_ref_with_digest: str, tool: str) -> bool:
    """Return True if digest is present at the target, False if confirmed absent.

    Raises RuntimeError on auth/network/registry errors so the caller can
    distinguish "needs copy" (404) from "operator must investigate"
    (everything else). Treating any non-zero exit as "needs copy" hides
    expired credentials behind a flood of redundant copy attempts.
    """
    if tool == "crane":
        cmd = ["crane", "manifest", image_ref_with_digest]
    elif tool == "skopeo":
        cmd = [
            "skopeo", "inspect", "--raw",
            f"docker://{image_ref_with_digest}",
        ]
    elif tool == "docker":
        cmd = [
            "docker", "buildx", "imagetools", "inspect",
            image_ref_with_digest,
        ]
    else:
        raise ValueError(f"Unknown tool: {tool}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True

    stderr = result.stderr.strip()
    if _is_not_found(stderr):
        return False

    raise RuntimeError(
        f"{tool} manifest check failed for {image_ref_with_digest} "
        f"(exit {result.returncode}): {stderr or '(no stderr)'}")


def copy_image(source_ref: str, target: str, tool: str) -> tuple[bool, str]:
    """Copy an image from source to target. Returns (success, error_msg)."""
    if tool == "crane":
        cmd = [tool, "copy", "--platform", "all", source_ref, target]
    elif tool == "skopeo":
        cmd = [
            tool, "copy", "--all", f"docker://{source_ref}",
            f"docker://{target}"
        ]
    elif tool == "docker":
        cmd = [
            tool, "buildx", "imagetools", "create", "-t", target, source_ref
        ]
    else:
        raise ValueError(f"Unknown copy tool: {tool}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, ""


def list_tags(image_repo: str, tool: str) -> list[str]:
    """List all tags for a repository.

    Only crane and skopeo expose tag listing; docker has no equivalent in
    the buildx/imagetools surface. When the active tool is docker we skip
    vague-tag pinning instead of failing the run.
    """
    if tool == "docker":
        print("  [warning] docker has no tag-listing API; "
              "version pinning for vague tags will be skipped. Install "
              "crane or skopeo for full tag resolution.", file=sys.stderr)
        return []

    if tool == "crane":
        result = subprocess.run(["crane", "ls", image_repo],
                                capture_output=True,
                                text=True)
    elif tool == "skopeo":
        result = subprocess.run(
            ["skopeo", "list-tags", f"docker://{image_repo}"],
            capture_output=True,
            text=True,
        )
    else:
        raise ValueError(f"Unknown tool for tag listing: {tool}")

    if result.returncode != 0:
        print(
            f"  [warning] failed to list tags for {image_repo}: "
            f"{result.stderr.strip()}",
            file=sys.stderr)
        return []

    if tool == "crane":
        return result.stdout.strip().splitlines()

    try:
        data = json.loads(result.stdout)
        return data.get("Tags", [])
    except json.JSONDecodeError as exc:
        print(f"  [warning] failed to parse tags for {image_repo}: {exc}",
              file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Image reference parsing & YAML config
# ---------------------------------------------------------------------------


def parse_image_ref(raw: str) -> str:
    """Normalize a Docker image reference to registry/repo:tag form."""
    ref = raw.strip()
    parts = ref.split("/", 1)
    if len(parts) == 1:
        registry = "index.docker.io"
        repo = f"library/{ref}"
    elif "." in parts[0] or ":" in parts[0]:
        registry = parts[0]
        repo = parts[1]
    else:
        registry = "index.docker.io"
        repo = ref

    if ":" not in repo:
        repo = f"{repo}:latest"

    return f"{registry}/{repo}"


@dataclass(frozen=True)
class MirrorEntry:
    """A single entry in mirror_images.yaml.

    Two on-disk shapes exist so the common case stays terse:

        - alpine:3.20

    when the destination follows the default `DEST_REGISTRY/<source>`
    convention, or a single-key mapping with an explicit override:

        - nginx:1.27.5:
            target: registry.ddbuild.io/ci/libdatadog-build/custom/nginx:1.27.5

    `to_yaml` round-trips back to whichever form the entry's `target`
    implies; an unset `target` always emits the bare-string form.

    Two computed attributes are available but not persisted to YAML:

    ``source_registry``
        The normalised source registry hostname (e.g. ``docker.io``,
        ``ghcr.io``).  Stored eagerly at construction time.

    ``target_registry``
        The mirror host+path prefix for this source registry, e.g.
        ``registry.ddbuild.io/ci/myrepo/mirror`` for ``docker.io`` or
        ``registry.ddbuild.io/ci/myrepo/mirror/ghcr.io`` for ``ghcr.io``.
        Computed lazily.
    """
    source: str
    target: str | None = None
    source_registry: str = field(init=False)

    def __post_init__(self) -> None:
        raw_registry = parse_image_ref(self.source).split("/", 1)[0]
        registry = "docker.io" if raw_registry == "index.docker.io" else raw_registry
        object.__setattr__(self, "source_registry", registry)

    @property
    def target_registry(self) -> "str | None":
        """Mirror prefix for this source registry.
        """
        image_path = (
            self.source if self.source_registry == "docker.io"
            else self.source[len(self.source_registry) + 1:]
        )
        t = self.resolved_target()
        suffix = f"/{image_path}"
        return t[: -len(suffix)] if t.endswith(suffix) else None

    def resolved_target(self) -> str:
        return self.target if self.target is not None else f"{_dest_registry()}/{self.source}"

    @classmethod
    def from_yaml(cls, raw: object) -> "MirrorEntry":
        if isinstance(raw, str):
            return cls(source=raw)
        if isinstance(raw, dict) and len(raw) == 1:
            (source, opts), = raw.items()
            if not isinstance(source, str):
                raise ValueError(
                    f"expected entry key to be str, got {type(source).__name__}: {source!r}")
            if opts is None:
                opts = {}
            elif not isinstance(opts, dict):
                raise ValueError(
                    f"expected options for {source!r} to be a mapping or null, "
                    f"got {type(opts).__name__}: {opts!r}")
            target = opts.get("target")
            if target is not None and not isinstance(target, str):
                raise ValueError(
                    f"expected target for {source!r} to be a str, "
                    f"got {type(target).__name__}: {target!r}")
            return cls(source=source, target=target)
        raise ValueError(
            f"expected str or single-key dict, got {type(raw).__name__}: {raw!r}")

    def to_yaml(self) -> "str | dict[str, dict[str, str]]":
        if self.target is None:
            return self.source
        return {self.source: {"target": self.target}}


@dataclass(frozen=True)
class LockEntry:
    """A single resolved image in mirror_images.lock.yaml."""
    digest: Digest
    target: str
    tag: str

    @classmethod
    def from_yaml(cls, raw: dict) -> "LockEntry":
        try:
            return cls(
                digest=Digest(raw["digest"]),
                target=raw["target"],
                tag=raw["tag"],
            )
        except KeyError as exc:
            raise ValueError(f"missing field in lock entry: {exc}") from exc

    def to_yaml(self) -> "dict[str, str]":
        # Field order matters for stable yaml output.
        return {"digest": str(self.digest), "target": self.target, "tag": self.tag}


@dataclass(frozen=True)
class MirrorManifest:
    """Parsed mirror_images.yaml: images plus lint ignore lists.

    `ignore_patterns` suppresses `lint` flags for image references that
    are intentionally not mirrored (test fixtures, refs that resolve at
    build time via a variable, alternate registries the repo trusts).

    `ignore_paths` skips entire directories from lint scanning (e.g.
    vendored submodules, example/ trees).
    """
    entries: list[MirrorEntry]
    ignore_patterns: list[re.Pattern[str]]
    # Raw `ignore.images` strings kept alongside the compiled patterns so
    # `add` can round-trip them verbatim (preserving the user's quoting)
    # without re-reading the file.
    ignore_images_raw: list[str]
    ignore_paths: list[str]
    was_mapping_form: bool

    def is_ignored(self, image: str) -> bool:
        return any(p.fullmatch(image) for p in self.ignore_patterns)


def _parse_str_list(value: object, what: str, path: str) -> list[str]:
    """Validate a YAML value as a list[str], filtering+warning on bad entries."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{what} in {path} must be a list")
    out: list[str] = []
    for i, raw in enumerate(value):
        if not isinstance(raw, str):
            print(
                f"  [warning] {what}[{i}] in {path} must be a string, "
                f"got {type(raw).__name__}", file=sys.stderr)
            continue
        out.append(raw)
    return out


def parse_mirror_yaml(path: str) -> MirrorManifest:
    """Parse mirror_images.yaml.

    Two on-disk shapes are accepted:

        # legacy flat list
        - alpine:3.20

        # mapping form, enables `ignore:`
        images:
          - alpine:3.20
        ignore:
          images:
            - public\\.ecr\\.aws/.*
          paths:
            - vendor

    Empty / comments-only / explicit `null` files yield an empty manifest
    so a freshly `init`'d project works immediately with `add`, `lock`,
    etc.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return MirrorManifest(
            entries=[], ignore_patterns=[], ignore_images_raw=[],
            ignore_paths=[], was_mapping_form=False,
        )

    ignore_images_raw: list[str] = []
    ignore_paths: list[str] = []

    if isinstance(data, list):
        raw_entries: list = data
        was_mapping = False
    elif isinstance(data, dict):
        raw_entries = data.get("images") or []
        if not isinstance(raw_entries, list):
            raise ValueError(f"'images' in {path} must be a list")
        ignore_section = data.get("ignore")
        if ignore_section is not None:
            if not isinstance(ignore_section, dict):
                raise ValueError(
                    f"'ignore' in {path} must be a mapping with 'images' "
                    f"and/or 'paths' keys")
            ignore_images_raw = _parse_str_list(
                ignore_section.get("images"), "ignore.images", path)
            ignore_paths = _parse_str_list(
                ignore_section.get("paths"), "ignore.paths", path)
        was_mapping = True
    else:
        raise ValueError(
            f"Expected YAML list or mapping in {path}, got {type(data).__name__}")

    entries: list[MirrorEntry] = []
    for i, raw in enumerate(raw_entries):
        try:
            entries.append(MirrorEntry.from_yaml(raw))
        except ValueError as exc:
            print(f"  [warning] ignoring entry #{i} in {path}: {exc}",
                  file=sys.stderr)

    ignore_patterns: list[re.Pattern[str]] = []
    for i, raw in enumerate(ignore_images_raw):
        try:
            ignore_patterns.append(re.compile(raw))
        except re.error as exc:
            print(f"  [warning] ignore.images[{i}] {raw!r} in {path} is "
                  f"not a valid regex: {exc}", file=sys.stderr)

    return MirrorManifest(
        entries=entries,
        ignore_patterns=ignore_patterns,
        ignore_images_raw=ignore_images_raw,
        ignore_paths=ignore_paths,
        was_mapping_form=was_mapping,
    )


def parse_lock_yaml(path: str) -> dict[str, LockEntry]:
    """Parse mirror_images.lock.yaml into {source: LockEntry}."""
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "images" not in data:
        raise ValueError(
            f"Malformed lock file {path}: expected a YAML mapping with an 'images' key"
        )
    images = data["images"]
    if not isinstance(images, dict):
        raise ValueError(
            f"Malformed lock file {path}: 'images' must be a mapping, "
            f"got {type(images).__name__}")
    return {src: LockEntry.from_yaml(info) for src, info in images.items()}


# ---------------------------------------------------------------------------
# Tag resolution for vague tags (e.g. "latest")
# ---------------------------------------------------------------------------


def _version_sort_key(tag: str) -> list[tuple[int, int | str]]:
    """Sort key that orders version-like tags so the highest version comes last.

    Numeric parts sort before string parts so that "1.2.3" < "1.2.10".
    """
    parts = re.split(r"[.\-+]", tag.lstrip("v"))
    return [(0, int(p)) if p.isdigit() else (1, p) for p in parts]


def find_specific_tag(image_ref: str, digest: str, tool: str) -> str:
    """Given a vague tag (e.g. 'latest'), find the most specific version tag
    that shares the same digest.

    Uses a dedicated inner ThreadPoolExecutor so this function is safe to
    call from a worker of an outer pool. (Submitting back into the *same*
    pool you are running in deadlocks once every worker is a parent.)
    """
    if ":" in image_ref:
        repo = image_ref.rsplit(":", 1)[0]
    else:
        repo = image_ref

    all_tags = list_tags(repo, tool)
    if not all_tags:
        return ""

    # "clean" = pure version tags like "1.2.3" or "v1.2.3"
    clean_re = re.compile(r"^v?\d+(\.\d+)+$")
    # "suffixed" = version + single suffix like "1.2.3-alpine"
    suffixed_re = re.compile(r"^v?\d+(\.\d+)+-[a-zA-Z][a-zA-Z0-9]*$")

    clean_tags = sorted(
        [t for t in all_tags if clean_re.match(t)],
        key=_version_sort_key, reverse=True,
    )
    clean_set = set(clean_tags)
    suffixed_tags = sorted(
        [t for t in all_tags if suffixed_re.match(t) and t not in clean_set],
        key=_version_sort_key, reverse=True,
    )

    candidates = clean_tags[:30] + suffixed_tags[:20]
    if not candidates:
        return ""

    def _resolve_tag(tag: str) -> tuple[str, Digest | None]:
        try:
            d = resolve_digest(f"{repo}:{tag}", tool)
            return tag, d
        except (RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            print(f"    [warning] could not resolve {repo}:{tag}: {exc}",
                  file=sys.stderr)
            return tag, None

    matches = []
    with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as inner_pool:
        futures = [inner_pool.submit(_resolve_tag, tag) for tag in candidates]
        for future in as_completed(futures):
            tag, tag_digest = future.result()
            if tag_digest == digest:
                matches.append(tag)

    if not matches:
        return ""

    # Prefer clean version tags (e.g. "1.2.3") over suffixed ones (e.g. "1.2.3-alpine")
    clean_matches = sorted(
        [t for t in matches if clean_re.match(t)],
        key=_version_sort_key, reverse=True,
    )
    if clean_matches:
        return clean_matches[0]

    matches.sort(key=_version_sort_key, reverse=True)
    return matches[0]


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------


def _write_lock_file(path: str, results: dict[str, LockEntry]) -> None:
    """Write the lock file with current results, sorted for stable output."""
    lock_data = {
        "version": 1,
        "images": {k: results[k].to_yaml() for k in sorted(results)},
    }
    dir_name = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp", prefix=".lock_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("# Auto-generated by: uv run bin/mirror_images.py lock\n")
            f.write("# Do not edit manually.\n")
            yaml.dump(lock_data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def cmd_lock(args: argparse.Namespace) -> int:
    """Generate mirror_images.lock.yaml with resolved digests."""
    tool = _find_digest_tool()
    entries = parse_mirror_yaml(args.mirror_yaml).entries
    declared_sources = {e.source for e in entries}
    output_path = args.output or LOCK_YAML

    # Load existing lock file to preserve previously resolved entries
    results: dict[str, LockEntry] = {}
    if os.path.exists(output_path):
        try:
            existing = parse_lock_yaml(output_path)
            results.update(existing)
            print(f"Loaded {len(results)} existing entries from {output_path}")
        except (OSError, yaml.YAMLError, ValueError) as exc:
            print(
                f"  [warning] could not parse existing lock file {output_path}: {exc}",
                file=sys.stderr)
            print("  [warning] resolving all images from scratch.",
                  file=sys.stderr)

    def _current_lock_entries() -> dict[str, LockEntry]:
        """Return only the results that are still declared in mirror_images.yaml."""
        return {k: results[k] for k in results if k in declared_sources}

    # Only resolve entries not already in the lock file
    to_resolve = [e for e in entries if e.source not in results]
    if not to_resolve:
        print(f"All {len(entries)} images already resolved in {output_path}")
        _write_lock_file(output_path, _current_lock_entries())
        return 0

    print(
        f"Resolving {len(to_resolve)} of {len(entries)} images using {tool} (parallelism={args.jobs})..."
    )

    errors: list[tuple[str, str]] = []
    pinning_failures: list[str] = []
    fatal_write_error: Exception | None = None

    def _resolve(entry: MirrorEntry):
        digest = resolve_digest(entry.source, tool)
        normalized = parse_image_ref(entry.source)
        tag = normalized.rsplit(":", 1)[1]

        pinning_failed = False
        if tag == "latest":
            pinned = find_specific_tag(entry.source, digest, tool) or tag
            pinning_failed = (pinned == tag)
            tag = pinned

        return entry, digest, tag, pinning_failed

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(_resolve, entry): entry.source
            for entry in to_resolve
        }
        for future in as_completed(futures):
            src = futures[future]
            try:
                entry, digest, tag, pinning_failed = future.result()
            except (OSError, RuntimeError, subprocess.SubprocessError,
                    ValueError) as exc:
                errors.append((src, str(exc)))
                print(f"  [error] resolving {src}: {exc}", file=sys.stderr)
                continue

            original_tag = entry.source.rsplit(":", 1)[-1]
            tag_info = f" (tag: {tag})" if tag != original_tag else ""
            print(f"  {entry.source}: {digest}{tag_info}")
            if pinning_failed:
                pinning_failures.append(entry.source)

            results[entry.source] = LockEntry(
                digest=digest,
                target=entry.resolved_target(),
                tag=tag,
            )
            try:
                _write_lock_file(output_path, _current_lock_entries())
            except (OSError, yaml.YAMLError) as exc:
                fatal_write_error = exc
                print(f"\n  [fatal] failed to write {output_path}: {exc}",
                      file=sys.stderr)
                for f in futures:
                    f.cancel()
                break

    if fatal_write_error is not None:
        return 1

    if pinning_failures:
        print(
            f"\n  [warning] {len(pinning_failures)} entr{'y' if len(pinning_failures) == 1 else 'ies'} "
            "kept a vague tag — tag pinning failed (transient registry error?). "
            "The digest is pinned, but the human-readable tag is not specific:",
            file=sys.stderr)
        for src in pinning_failures:
            print(f"    - {src}: tag={results[src].tag}", file=sys.stderr)

    if errors:
        print(f"\nFailed to resolve {len(errors)} image(s):", file=sys.stderr)
        for src, err in errors:
            print(f"  - {src}: {err}", file=sys.stderr)
        return 1

    print(f"\nWrote {output_path} ({len(results)} images)")
    return 0


# ---------------------------------------------------------------------------
# Mirror
# ---------------------------------------------------------------------------


_AUTH_FAILURE_THRESHOLD = 3


def cmd_mirror(args: argparse.Namespace) -> int:
    """Sync images from lock file to target registry using crane/skopeo."""
    lock_path = args.lock_yaml
    if not os.path.exists(lock_path):
        print(f"Lock file not found: {lock_path}", file=sys.stderr)
        print("Run 'mirror_images.py lock' first.", file=sys.stderr)
        return 1

    digest_tool = _find_digest_tool()
    copy_tool = _find_copy_tool()
    images = parse_lock_yaml(lock_path)

    # Phase 1: check which images need copying
    print(
        f"Phase 1: checking {len(images)} images using {digest_tool} ({args.jobs} workers)..."
    )

    def _check_if_mirrored(source: str, info: LockEntry):
        # Resolve the target *tag* (not just the digest) so we re-copy when
        # the bytes already live in the repo under a different tag — e.g.
        # a previous run mirrored the same digest as `mirror/foo:1` and
        # this run wants `mirror/foo:1.2.3`. Skipping by digest alone would
        # leave the new tag alias unset and consumers pulling by tag get
        # `manifest unknown`.
        print(f"  ? {source} -> {info.target}")
        try:
            actual = resolve_digest(info.target, digest_tool)
        except RuntimeError as exc:
            if _is_not_found(str(exc)):
                return source, info, False
            raise
        return source, info, actual == info.digest

    to_copy: list[tuple[str, LockEntry]] = []
    already_present = 0
    checked = 0
    check_errors: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(_check_if_mirrored, src, info): src
            for src, info in images.items()
        }
        for future in as_completed(futures):
            src = futures[future]
            checked += 1
            try:
                source, info, present = future.result()
            except (OSError, RuntimeError, subprocess.SubprocessError,
                    ValueError) as exc:
                check_errors.append((src, str(exc)))
                print(f"  [error] checking {src}: {exc}", file=sys.stderr)
                continue
            if present:
                already_present += 1
                print(
                    f"  = [{checked}/{len(images)}] {source} (already mirrored)"
                )
            else:
                to_copy.append((source, info))
                print(f"  + [{checked}/{len(images)}] {source} (needs copy)")

    if check_errors:
        print(
            f"\n  [fatal] {len(check_errors)} image(s) failed pre-flight check "
            "(not a 404). This usually means broken auth, network, or registry "
            "config. Refusing to attempt copies until checks pass:",
            file=sys.stderr)
        for src, err in check_errors:
            print(f"    - {src}: {err}", file=sys.stderr)
        return 2

    if not to_copy:
        print(f"\nAll {len(images)} images are up to date.")
        return 0

    print(
        f"\n{already_present} already mirrored, {len(to_copy)} to copy using {copy_tool}.\n"
    )

    # Phase 2: copy missing images in parallel, fail-fast on persistent auth errors.
    print(
        f"\nPhase 2: copying {len(to_copy)} images using {copy_tool} ({args.jobs} workers)..."
    )

    errors: list[tuple[str, str]] = []
    auth_failures = 0
    aborted_for_auth = False
    abort_lock = threading.Lock()

    def _do_copy(idx: int, source: str, info: LockEntry):
        source_ref = f"{parse_image_ref(source).rsplit(':', 1)[0]}@{info.digest}"
        if args.dry_run:
            return idx, source, info, source_ref, True, "[dry-run]"
        ok, err = copy_image(source_ref, info.target, copy_tool)
        return idx, source, info, source_ref, ok, err

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        indexed = list(enumerate(sorted(to_copy), 1))
        future_map = {
            pool.submit(_do_copy, i, src, info): (src, info)
            for i, (src, info) in indexed
        }
        for future in as_completed(future_map):
            if future.cancelled():
                continue
            idx, source, info, source_ref, ok, err = future.result()
            print(
                f"  -> [{idx}/{len(to_copy)}] {source} ({info.digest[:19]}...)\n"
                f"     src:  {source_ref}\n"
                f"     dest: {info.target}")
            if args.dry_run:
                print(
                    f"     [dry-run] {copy_tool} copy {source_ref} {info.target}"
                )
                continue
            if ok:
                print(f"     OK")
                continue
            errors.append((source, err))
            print(
                f"     [error] ({copy_tool}) {err or '(no stderr)'}",
                file=sys.stderr)
            if _is_auth_error(err):
                with abort_lock:
                    auth_failures += 1
                    if (auth_failures >= _AUTH_FAILURE_THRESHOLD
                            and not aborted_for_auth):
                        aborted_for_auth = True
                        print(
                            f"\n  [fatal] {auth_failures} auth-shaped copy failures — "
                            "cancelling remaining copies. Check destination registry "
                            "credentials.",
                            file=sys.stderr)
                        for f in future_map:
                            f.cancel()

    if errors:
        print(f"\nFailed to copy {len(errors)} image(s):", file=sys.stderr)
        for src, err in errors:
            print(f"  - {src}: {err}", file=sys.stderr)
        return 1

    action = "would copy" if args.dry_run else "copied"
    print(
        f"\nDone: {already_present} already present, {len(to_copy)} {action}.")
    return 0


# ---------------------------------------------------------------------------
# BuildKit daemon config generation
# ---------------------------------------------------------------------------


def cmd_buildkitd(args: argparse.Namespace) -> int:
    entries = parse_mirror_yaml(args.mirror_yaml).entries
    if not entries:
        print("  [error] no entries in mirror_images.yaml.", file=sys.stderr)
        return 1

    registry_to_mirror: dict[str, str] = {}

    for entry in entries:
        mirror = entry.target_registry
        if mirror is None:
            print(
                f"  [warning] skipping {entry.source!r}: explicit target does not "
                "follow the standard {dest}/{image_path} convention.",
                file=sys.stderr,
            )
            continue

        reg = entry.source_registry
        existing = registry_to_mirror.get(reg)
        if existing is not None and existing != mirror:
            print(
                f"  [error] conflicting mirror addresses for {reg!r}:\n"
                f"    {existing!r} (seen earlier)\n"
                f"    {mirror!r} (from {entry.source!r})",
                file=sys.stderr,
            )
            return 1

        registry_to_mirror[reg] = mirror

    lines = [
        "# Auto-generated by: mirror_images buildkitd",
        "# Do not edit manually — regenerate with:",
        "#   mirror_images buildkitd",
        "",
    ]
    for reg in sorted(registry_to_mirror):
        lines.append(f'[registry."{reg}"]')
        lines.append(f'  mirrors = ["{registry_to_mirror[reg]}"]')
        lines.append("")

    content = "\n".join(lines)

    if args.output:
        with open(args.output, "w") as f:
            f.write(content)
        print(f"Wrote {args.output} ({len(registry_to_mirror)} registry mirror(s))")
    else:
        print(content, end="")

    return 0


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------


def find_public_image_refs(
    skip_dirs: tuple[str, ...] = (),
) -> list[tuple[str, int, str, str]]:
    """Scan the repo for image references not using registry.ddbuild.io.

    `skip_dirs` are repo-relative directory paths to skip (typically
    sourced from `mirror_images.yaml#ignore.paths`).
    """
    internal_prefixes = ("registry.ddbuild.io/", "486234852809.dkr.ecr")
    hits = []

    _ignore_prefixes = internal_prefixes + (
        "$", "{", "nginx-datadog-test-",
    )

    def _is_external(img: str) -> bool:
        if any(img.startswith(p) for p in _ignore_prefixes):
            return False
        return bool(re.match(r"^[a-zA-Z0-9]", img))

    def _read_lines(filepath):
        try:
            with open(filepath) as f:
                return list(enumerate(f, 1))
        except OSError as exc:
            print(f"  [warning] Could not read {filepath}: {exc}",
                  file=sys.stderr)
            return []

    # Trailing `/` keeps "foo" from matching "foo-bar".
    _skip_dir_prefixes = tuple(
        os.path.join(PROJECT_DIR, d) + os.sep for d in skip_dirs
    )

    def _in_skip_dir(filepath):
        return filepath.startswith(_skip_dir_prefixes)

    def _scan_dockerfiles():
        for filepath in glob.glob(os.path.join(PROJECT_DIR, "**/Dockerfile*"),
                                  recursive=True):
            if "/.git/" in filepath or _in_skip_dir(filepath):
                continue
            for lineno, line in _read_lines(filepath):
                stripped = line.strip()
                m = re.match(r"^FROM\s+(\S+)", stripped, re.IGNORECASE)
                if m and _is_external(m.group(1)):
                    hits.append((filepath, lineno, stripped, m.group(1)))
                for m in re.finditer(r"--from=(\S+)", stripped):
                    img = m.group(1)
                    if ("/" in img or ":" in img) and _is_external(img):
                        hits.append((filepath, lineno, stripped, img))

    def _scan_yaml_image_fields():
        skip_path_fragments = ("/.git/", "/.gitlab/")
        for pattern in ("**/*.yml", "**/*.yaml"):
            for filepath in glob.glob(os.path.join(PROJECT_DIR, pattern),
                                      recursive=True):
                if any(frag in filepath for frag in skip_path_fragments):
                    continue
                if _in_skip_dir(filepath):
                    continue
                for lineno, line in _read_lines(filepath):
                    m = re.match(r"^\s*image:\s+['\"]?(\S+?)['\"]?\s*$", line)
                    if m and _is_external(m.group(1)):
                        hits.append(
                            (filepath, lineno, line.rstrip(), m.group(1)))

    _scan_dockerfiles()
    _scan_yaml_image_fields()
    return hits


def _collect_gitlab_ci_files(entry: str) -> list[str]:
    """Starting from a GitLab CI YAML file, follow local includes and return all file paths."""
    collected = []
    visited: set[str] = set()
    queue: collections.deque[str] = collections.deque([entry])
    while queue:
        path = queue.popleft()
        abspath = os.path.join(PROJECT_DIR, path) if not os.path.isabs(path) else path
        if abspath in visited or not os.path.isfile(abspath):
            continue
        visited.add(abspath)
        collected.append(abspath)
        try:
            with open(abspath) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as exc:
            print(f"  [warning] Could not parse {abspath}: {exc}",
                  file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        includes = data.get("include", [])
        if isinstance(includes, dict):
            includes = [includes]
        if not isinstance(includes, list):
            continue
        for inc in includes:
            if isinstance(inc, str):
                queue.append(os.path.join(PROJECT_DIR, inc))
            elif isinstance(inc, dict) and "local" in inc:
                queue.append(os.path.join(PROJECT_DIR, inc["local"]))
    return collected


# Templates that map matrix variable names to image name patterns.
# {value} is replaced with the matrix variable value.
_GITLAB_MATRIX_IMAGE_TEMPLATES: dict[str, list[str]] = {
    "BASE_IMAGE": ["{value}"],
    "INGRESS_NGINX_VERSION": [
        "registry.k8s.io/ingress-nginx/controller:v{value}"
    ],
    "RESTY_VERSION": ["openresty/openresty:{value}-alpine"],
}


def _extract_matrix_combos(job: dict) -> list[dict]:
    """Extract the parallel:matrix combo list from a GitLab CI job definition."""
    parallel = job.get("parallel")
    if not isinstance(parallel, dict):
        return []
    matrix = parallel.get("matrix")
    if not isinstance(matrix, list):
        return []
    return [c for c in matrix if isinstance(c, dict)]


def _expand_matrix_images(combo: dict) -> list[str]:
    """Expand a single matrix combo into image references using known templates."""
    images = []
    for var_name, templates in _GITLAB_MATRIX_IMAGE_TEMPLATES.items():
        values = combo.get(var_name, [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for val in values:
            for tmpl in templates:
                images.append(tmpl.format(value=val))
    return images


def find_gitlab_ci_images() -> list[tuple[str, str]]:
    """Extract public image references from GitLab CI matrix variables.

    Returns a list of (source_file_relpath, image_ref) tuples.
    """
    ci_entry = os.path.join(PROJECT_DIR, ".gitlab-ci.yml")
    if not os.path.isfile(ci_entry):
        return []

    results = []
    for filepath in _collect_gitlab_ci_files(ci_entry):
        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as exc:
            print(f"  [warning] Could not parse {filepath}: {exc}",
                  file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue

        relpath = os.path.relpath(filepath, PROJECT_DIR)
        for _job_name, job in data.items():
            if not isinstance(job, dict):
                continue
            for combo in _extract_matrix_combos(job):
                for img in _expand_matrix_images(combo):
                    results.append((relpath, img))

    return results


def cmd_lint(args: argparse.Namespace) -> int:
    """Check that all images are referenced from registry.ddbuild.io."""
    manifest = parse_mirror_yaml(args.mirror_yaml)
    declared = {e.source: e.resolved_target() for e in manifest.entries}
    rc = 0

    # --- Check 1: public image references in Dockerfiles and YAML ---
    public_refs = [r for r in find_public_image_refs(tuple(manifest.ignore_paths))
                   if not manifest.is_ignored(r[3])]

    if public_refs:
        by_image: dict[str, list[tuple[str, int, str]]] = {}
        for filepath, lineno, line, img in public_refs:
            by_image.setdefault(img, []).append((filepath, lineno, line))

        undeclared = []
        print(
            "Public image references found (should use registry.ddbuild.io mirror):\n"
        )
        for img in sorted(by_image):
            replacement = declared.get(img)
            if not replacement:
                replacement = f"{_dest_registry()}/{img}"
                undeclared.append(img)

            print(f"  {img}")
            print(f"    -> {replacement}")
            for filepath, lineno, line in by_image[img]:
                relpath = os.path.relpath(filepath, PROJECT_DIR)
                print(f"       {relpath}:{lineno}")
            print()

        if undeclared:
            print(
                "Images not declared in mirror_images.yaml (add them first):")
            for img in sorted(undeclared):
                print(f"  - {img}")
            print()

        print(
            f"{len(public_refs)} public image reference(s) across {len(by_image)} image(s)."
        )
        rc = 1

    # --- Check 2: GitLab CI matrix images must be in mirror_images.yaml ---
    ci_images = [(src, img) for src, img in find_gitlab_ci_images()
                 if not manifest.is_ignored(img)]
    if ci_images:
        missing: dict[str, list[str]] = {}
        for source_file, img in ci_images:
            if img not in declared:
                missing.setdefault(img, []).append(source_file)

        if missing:
            print("GitLab CI matrix images not declared in mirror_images.yaml:\n")
            for img in sorted(missing):
                sources = sorted(set(missing[img]))
                print(f"  - {img}")
                for src in sources:
                    print(f"      {src}")
            print(
                f"\n{len(missing)} image(s) from GitLab CI not in mirror_images.yaml."
            )
            rc = 1
        else:
            print("All GitLab CI matrix images are declared in mirror_images.yaml.")

    if rc == 0:
        print("All image references use registry.ddbuild.io.")
    return rc


# ---------------------------------------------------------------------------
# List ignored image references
# ---------------------------------------------------------------------------


def cmd_ignored(args: argparse.Namespace) -> int:
    """Emit JSON listing image refs suppressed by mirror_images.yaml ignores.

    Default: only refs outside `ignore.paths` whose source matches
    `ignore.images`. With `--scan-paths`, also walks into `ignore.paths`
    directories and reports refs found there (rule="path").
    """
    manifest = parse_mirror_yaml(args.mirror_yaml)

    skip_dirs: tuple[str, ...] = () if args.scan_paths else tuple(manifest.ignore_paths)
    refs = find_public_image_refs(skip_dirs)

    def _match_path(relpath: str) -> str | None:
        for p in manifest.ignore_paths:
            if relpath == p or relpath.startswith(p + os.sep):
                return p
        return None

    def _match_pattern(img: str) -> str | None:
        for p in manifest.ignore_patterns:
            if p.fullmatch(img):
                return p.pattern
        return None

    def _rec(img, rule, matched, file, line):
        return {"image": img, "rule": rule, "matched": matched,
                "file": file, "line": line}

    suppressed: list[dict] = []
    for filepath, lineno, _line, img in refs:
        relpath = os.path.relpath(filepath, PROJECT_DIR)
        # Path rule wins over image-pattern when both apply, since lint
        # would never reach the image check for files inside an ignored
        # directory.
        path_match = _match_path(relpath)
        if path_match is not None:
            suppressed.append(_rec(img, "path", path_match, relpath, lineno))
            continue
        pattern_match = _match_pattern(img)
        if pattern_match is not None:
            suppressed.append(_rec(img, "pattern", pattern_match, relpath, lineno))

    for src_file, img in find_gitlab_ci_images():
        pattern_match = _match_pattern(img)
        if pattern_match is not None:
            suppressed.append(_rec(img, "pattern", pattern_match, src_file, None))

    suppressed.sort(key=lambda r: (r["image"], r["file"], r["line"] or 0))

    output = {
        "patterns": [p.pattern for p in manifest.ignore_patterns],
        "paths": manifest.ignore_paths,
        "scanned_ignored_paths": args.scan_paths,
        "suppressed": suppressed,
    }
    print(json.dumps(output, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Add images
# ---------------------------------------------------------------------------


def _write_mirror_yaml(
    path: str,
    entries: list[MirrorEntry],
    ignore_section: dict[str, list[str]],
    use_mapping_form: bool,
) -> None:
    """Rewrite mirror_images.yaml preserving leading comments.

    Uses mapping form (`images:` / `ignore:`) when either the file already
    used that form or the ignore section is non-empty; otherwise emits
    the legacy flat list. Bare-string entries keep their quoted shape;
    custom-target entries round-trip through yaml.dump.
    """
    with open(path) as f:
        header_lines = []
        for line in f:
            if line.startswith("#") or line.strip() == "":
                header_lines.append(line)
            else:
                break

    def _entry_lines(entry: MirrorEntry, indent: str = "") -> str:
        shape = entry.to_yaml()
        if isinstance(shape, str):
            return f'{indent}- "{shape}"\n'
        return "".join(
            f"{indent}{line}\n"
            for line in yaml.dump([shape], default_flow_style=False, sort_keys=False).splitlines()
        )

    with open(path, "w") as f:
        f.writelines(header_lines)
        if use_mapping_form:
            f.write("images:\n")
            for entry in entries:
                f.write(_entry_lines(entry, indent="  "))
            if any(ignore_section.values()):
                f.write("\nignore:\n")
                for key in ("images", "paths"):
                    items = ignore_section.get(key) or []
                    if not items:
                        continue
                    f.write(f"  {key}:\n")
                    for item in items:
                        for line in yaml.dump(
                                [item], default_flow_style=False,
                                sort_keys=False).splitlines():
                            f.write(f"    {line}\n")
        else:
            for entry in entries:
                f.write(_entry_lines(entry))


def cmd_add(args: argparse.Namespace) -> int:
    """Add one or more images to mirror_images.yaml (if not already present)."""
    try:
        manifest = parse_mirror_yaml(args.mirror_yaml)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    entries = list(manifest.entries)
    existing = {e.source for e in entries}

    added = []
    for img in args.images:
        if img in existing:
            print(f"  already listed: {img}")
        else:
            entries.append(MirrorEntry(source=img))
            existing.add(img)
            added.append(img)
            print(f"  added: {img}")

    if not added:
        print("\nNo new images to add.")
        return 0

    # Sort bare-string entries (default target) by source; keep entries
    # with a custom target after them in their original order.
    bare = sorted([e for e in entries if e.target is None], key=lambda e: e.source)
    custom = [e for e in entries if e.target is not None]
    entries = bare + custom

    ignore_section = {"images": manifest.ignore_images_raw, "paths": manifest.ignore_paths}
    use_mapping = manifest.was_mapping_form or any(ignore_section.values())
    _write_mirror_yaml(args.mirror_yaml, entries, ignore_section, use_mapping)

    print(f"\nAdded {len(added)} image(s) to {args.mirror_yaml}")
    return 0


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


_INIT_TEMPLATE = """\
# Images to mirror into registry.ddbuild.io.
# See: https://github.com/DataDog/dd-repo-tools/blob/main/shared/mirror-images/mirror_images.md
#
# Flat-list form:
#   - "alpine:3.20"
#   - "nginx:1.27.5":
#       target: registry.ddbuild.io/ci/example/custom/nginx:1.27.5
#
# Mapping form (enables `ignore`):
#   images:
#     - "alpine:3.20"
#   ignore:
#     images:
#       - "public\\.ecr\\.aws/.*"
#     paths:
#       - "vendor"
"""


def cmd_init(args: argparse.Namespace) -> int:
    """Write a starter mirror_images.yaml at the project root."""
    path = args.mirror_yaml
    if os.path.exists(path) and not args.force:
        print(f"{path} already exists. Use --force to overwrite.",
              file=sys.stderr)
        return 1
    with open(path, "w") as f:
        f.write(_INIT_TEMPLATE)
    print(f"Wrote {path}")
    print("Next: `mirror_images lock` to resolve digests, "
          "then `mirror_images mirror` to copy.")
    return 0


# ---------------------------------------------------------------------------
# Relock images
# ---------------------------------------------------------------------------


def cmd_relock(args: argparse.Namespace) -> int:
    """Re-resolve digests for images matching the given patterns.

    Removes matching entries from the lock file, then runs the lock
    command to re-resolve them. Patterns use fnmatch-style wildcards
    (e.g. 'nginx:1.29.*', 'openresty/*').
    """
    lock_path = args.output or LOCK_YAML
    if not os.path.exists(lock_path):
        print(f"Lock file not found: {lock_path}", file=sys.stderr)
        print("Run 'lock' first to create it.", file=sys.stderr)
        return 1

    existing = parse_lock_yaml(lock_path)
    patterns = args.patterns

    matched = []
    for src in list(existing):
        if any(fnmatch.fnmatch(src, pat) for pat in patterns):
            matched.append(src)
            del existing[src]

    if not matched:
        print(f"No images in lock file matched: {', '.join(patterns)}")
        return 1

    print(f"Removing {len(matched)} image(s) from lock file to re-resolve:")
    for src in sorted(matched):
        print(f"  - {src}")

    # Write out the lock file without the matched entries
    _write_lock_file(lock_path, existing)

    # Now run the normal lock flow which will resolve the missing entries
    print()
    return cmd_lock(args)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mirror_images",
        description="Manage mirrored Docker images")
    parser.add_argument(
        "--mirror-yaml",
        default=MIRROR_YAML,
        help=f"Path to mirror_images.yaml (default: {MIRROR_YAML})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Write a starter mirror_images.yaml",
        description="Create mirror_images.yaml at the project root with a "
        "small example. Refuses to overwrite an existing file unless --force.",
    )
    init_parser.set_defaults(func=cmd_init)
    init_parser.add_argument(
        "-f", "--force", action="store_true",
        help="Overwrite mirror_images.yaml if it already exists")

    lock_parser = subparsers.add_parser(
        "lock", help="Generate mirror_images.lock.yaml with resolved digests")
    lock_parser.set_defaults(func=cmd_lock)
    lock_parser.add_argument("-j",
                             "--jobs",
                             type=int,
                             default=16,
                             help="Parallel workers (default: 16)")
    lock_parser.add_argument(
        "-o",
        "--output",
        help="Output path (default: mirror_images.lock.yaml)")

    mirror_parser = subparsers.add_parser(
        "mirror", help="Sync images from lock file to target registry")
    mirror_parser.set_defaults(func=cmd_mirror)
    mirror_parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=16,
        help="Parallel workers for checking (default: 16)")
    mirror_parser.add_argument("--lock-yaml",
                               default=LOCK_YAML,
                               help="Path to lock file")
    mirror_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without copying")

    buildkitd_parser = subparsers.add_parser(
        "buildkitd",
        help="Generate a buildkitd.toml mirror config from mirror_images.yaml",
        description=(
            "Read mirror_images.yaml and emit a buildkitd.toml with one\n"
            "[registry.\"X\"] section per source registry."
        ),
    )
    buildkitd_parser.set_defaults(func=cmd_buildkitd)
    buildkitd_parser.add_argument(
        "-o",
        "--output",
        help="Output path for buildkitd.toml (default: print to stdout)",
    )

    lint_parser = subparsers.add_parser(
        "lint", help="Check that all image references use registry.ddbuild.io")
    lint_parser.set_defaults(func=cmd_lint)

    ignored_parser = subparsers.add_parser(
        "ignored",
        help="List image references suppressed by mirror_images.yaml `ignore:` rules (JSON)",
        description="Print JSON listing image refs that lint is silently "
        "skipping. By default only `ignore.images` regex hits are scanned. "
        "Pass --scan-paths to also walk into `ignore.paths` directories.",
    )
    ignored_parser.set_defaults(func=cmd_ignored)
    ignored_parser.add_argument(
        "--scan-paths", action="store_true",
        help="Also descend into `ignore.paths` directories and report refs found there",
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Add images to mirror_images.yaml",
        description=
        "Add one or more Docker image references to mirror_images.yaml. "
        "Images already listed are skipped. The file is re-sorted after adding."
    )
    add_parser.set_defaults(func=cmd_add)
    add_parser.add_argument(
        "images",
        nargs="+",
        metavar="IMAGE",
        help="Image references to add (e.g. 'nginx:1.30.0' 'alpine:3.21')")

    relock_parser = subparsers.add_parser(
        "relock",
        help="Re-resolve digests for specific images in the lock file",
        description="Remove matching entries from mirror_images.lock.yaml and "
        "re-resolve their digests. Uses fnmatch-style wildcards. "
        "Example: 'nginx:1.29.*' matches nginx:1.29.0, nginx:1.29.5-alpine, etc."
    )
    relock_parser.set_defaults(func=cmd_relock)
    relock_parser.add_argument(
        "patterns",
        nargs="+",
        metavar="PATTERN",
        help=
        "Glob patterns to match image names (e.g. 'nginx:1.29.*' 'openresty/*')"
    )
    relock_parser.add_argument("-j",
                               "--jobs",
                               type=int,
                               default=16,
                               help="Parallel workers (default: 16)")
    relock_parser.add_argument(
        "-o",
        "--output",
        help="Path to lock file (default: mirror_images.lock.yaml)")

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

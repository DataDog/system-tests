"""Rewrite Docker image references to the system-tests mirror.

When the `USE_IMAGE_MIRROR` env var is truthy, image references that have been
mirrored into `registry.ddbuild.io/system-tests/mirror` (see mirror_images.yaml /
mirror_images.lock.yaml and the `mirror_images` CI job) are rewritten to their
mirror target, so CI pulls from the mirror instead of docker.io / ghcr.io / etc.

It is off by default: with the flag unset (local runs, or any environment where
the mirror is not reachable) every reference is returned unchanged.

The source -> target mapping is read from mirror_images.lock.yaml, which holds
the exact target for each mirrored image. Anything not listed there (locally
built `system_tests/*` images, unmirrored refs, multi-stage build stage names)
is left untouched.
"""

import functools
import os
from pathlib import Path

import yaml

# mirror_images.lock.yaml lives at the repo root (this file is utils/_context/).
_LOCK_PATH = Path(__file__).resolve().parents[2] / "mirror_images.lock.yaml"


def mirror_enabled() -> bool:
    return os.environ.get("USE_IMAGE_MIRROR", "").strip().lower() in ("1", "true", "yes")


@functools.lru_cache(maxsize=1)
def _mapping() -> dict[str, str]:
    """Return {source_ref: mirror_target_ref} from the lock file ({} if absent)."""
    try:
        with open(_LOCK_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError):
        return {}

    images = data.get("images") if isinstance(data, dict) else None
    if not isinstance(images, dict):
        return {}

    mapping: dict[str, str] = {}
    for source, info in images.items():
        if isinstance(info, dict) and isinstance(info.get("target"), str):
            mapping[source] = info["target"]
    return mapping


def mirror_image(name: str) -> str:
    """Return the mirror target for `name` when mirroring is enabled, else `name`.

    Only exact matches in the lock file are rewritten, so unmirrored and
    locally-built references pass through unchanged.
    """
    if not mirror_enabled():
        return name
    return _mapping().get(name, name)

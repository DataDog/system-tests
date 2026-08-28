"""Resolve stable weblog base-image aliases through the committed lock.

Deliberately stdlib-only (no ``utils`` package or venv) so CI can import it
before the runner virtualenv exists.
"""

import argparse
import json
import re
import sys
from pathlib import Path

LOCK_VERSION = 1
LOCK_PATH = Path(__file__).resolve().parents[1] / "build" / "docker" / "base-images.lock.json"
ALIAS_PREFIX = "system_tests_base_"

_FROM_IMAGE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)", re.IGNORECASE | re.MULTILINE)
_LOCKED_IMAGE = re.compile(r"^datadog/system-tests:[a-zA-Z0-9_.-]+\.base-[0-9a-f]{12}$")
_ALIAS = re.compile(rf"^{ALIAS_PREFIX}[a-z0-9_]+$")


class BaseImageLockError(ValueError):
    """The base-image lock or a symbolic Dockerfile reference is invalid."""


def load_base_image_lock(lock_path: Path = LOCK_PATH) -> dict[str, str]:
    """Load and strictly validate a version-1 base-image lock."""
    try:
        data = json.loads(lock_path.read_text())
    except FileNotFoundError:
        raise BaseImageLockError(
            f"base-image lock not found at {lock_path}; regenerate it with "
            "python utils/scripts/update-base-image-lock.py"
        ) from None
    except (OSError, json.JSONDecodeError) as exc:
        raise BaseImageLockError(f"could not read base-image lock {lock_path}: {exc}") from None

    if not isinstance(data, dict) or set(data) != {"version", "images"}:
        raise BaseImageLockError(f"{lock_path}: expected exactly 'version' and 'images' keys")
    if data["version"] != LOCK_VERSION:
        raise BaseImageLockError(f"{lock_path}: unsupported version {data['version']!r}; expected {LOCK_VERSION}")
    if not isinstance(data["images"], dict):
        raise BaseImageLockError(f"{lock_path}: 'images' must be an object")

    images: dict[str, str] = {}
    for alias, image in data["images"].items():
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
            raise BaseImageLockError(f"{lock_path}: invalid base-image alias {alias!r}")
        if not isinstance(image, str) or not _LOCKED_IMAGE.fullmatch(image):
            raise BaseImageLockError(f"{lock_path}: invalid locked image for {alias}: {image!r}")
        images[alias] = image
    return images


def base_image_aliases(dockerfile_text: str) -> list[str]:
    """Return unique symbolic base-image aliases used by FROM instructions."""
    aliases: list[str] = []
    for image in _FROM_IMAGE.findall(dockerfile_text):
        if image.startswith(ALIAS_PREFIX) and image not in aliases:
            if not _ALIAS.fullmatch(image):
                raise BaseImageLockError(f"invalid base-image alias in Dockerfile: {image!r}")
            aliases.append(image)
    return aliases


def base_image_contexts(dockerfile_text: str, lock_path: Path = LOCK_PATH) -> dict[str, str]:
    """Return alias-to-locked-image mappings required to build a Dockerfile."""
    aliases = base_image_aliases(dockerfile_text)
    if not aliases:
        return {}

    lock = load_base_image_lock(lock_path)
    missing = [alias for alias in aliases if alias not in lock]
    if missing:
        raise BaseImageLockError(
            f"{lock_path}: missing base-image lock entr{'y' if len(missing) == 1 else 'ies'} for {', '.join(missing)}"
        )
    return {alias: lock[alias] for alias in aliases}


def base_image_ref(dockerfile_text: str, lock_path: Path = LOCK_PATH) -> str | None:
    """Return the first real system-tests base image used by a Dockerfile."""
    contexts = base_image_contexts(dockerfile_text, lock_path)
    if contexts:
        return next(iter(contexts.values()))

    # Backwards-compatible detection makes migration failures visible without
    # forcing unrelated Dockerfiles to load the lock.
    for image in _FROM_IMAGE.findall(dockerfile_text):
        if image.startswith("datadog/system-tests:"):
            return image
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve weblog base-image aliases")
    parser.add_argument(
        "--build-contexts",
        metavar="DOCKERFILE",
        type=Path,
        help="Print alias=docker-image://reference lines for docker buildx",
    )
    args = parser.parse_args()
    if args.build_contexts is None:
        parser.error("--build-contexts is required")

    try:
        contexts = base_image_contexts(args.build_contexts.read_text())
    except (OSError, BaseImageLockError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    for alias, image in contexts.items():
        print(f"{alias}=docker-image://{image}")


if __name__ == "__main__":
    main()

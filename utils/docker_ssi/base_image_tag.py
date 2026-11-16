"""Registry tag of the Docker SSI base images.

All the base images are stored in one repository. The tag ends with a hash of everything used to
build the image, so any change gives a new tag, and a new tag is built and pushed automatically.
"""

import hashlib
import json
from pathlib import Path

BASE_IMAGE_REPOSITORY = "system-tests/docker-ssi-base"
BASE_IMAGE_BUILD_DIR = Path(__file__).resolve().parents[1] / "build" / "ssi" / "base"
HASH_LENGTH = 12
MAX_TAG_LENGTH = 128


def base_image_tag(name: str, build_args: dict[str, str | None], build_dir: Path = BASE_IMAGE_BUILD_DIR) -> str:
    """Return '<name>-<hash>', where the hash covers build_args and every file directly under build_dir.

    Subfolders (like binaries/, filled by the wizard) and hidden files are not part of the hash.
    The name is cut if needed to fit the Docker tag limit. The hash keeps the tag unique.
    """
    digest = hashlib.sha256(json.dumps(build_args, sort_keys=True).encode())
    for file in sorted(build_dir.iterdir()):
        if file.is_file() and not file.name.startswith("."):
            digest.update(file.name.encode() + b"\0" + file.read_bytes() + b"\0")

    max_name_length = MAX_TAG_LENGTH - HASH_LENGTH - 1
    return f"{name[:max_name_length]}-{digest.hexdigest()[:HASH_LENGTH]}"

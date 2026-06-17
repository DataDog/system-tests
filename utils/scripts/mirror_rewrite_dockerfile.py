"""Rewrite a Dockerfile's `FROM` base images to the system-tests mirror.

Used by utils/build/build.sh when USE_IMAGE_MIRROR is enabled: it prints the
given Dockerfile to stdout with every `FROM <image>` whose image is in the
mirror (mirror_images.lock.yaml) replaced by its mirror target, so weblog builds
pull their base images from registry.ddbuild.io/system-tests/mirror instead of
docker.io / ghcr.io / etc.

Image references not present in the mirror mapping are left unchanged. This
matches multi-stage stage names (`FROM build`) too: they are never in the
mapping, so they pass through untouched.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from utils._context._image_mirror import mirror_image

# FROM [--platform=<p>] <image> [AS <name>]
_FROM_RE = re.compile(r"^(\s*FROM\s+)((?:--platform=\S+\s+)?)(\S+)(.*)$", re.IGNORECASE)


def rewrite(dockerfile: str) -> str:
    out: list[str] = []
    with open(dockerfile, encoding="utf-8") as f:
        for line in f:
            match = _FROM_RE.match(line.rstrip("\n"))
            if match:
                prefix, platform, image, rest = match.groups()
                out.append(f"{prefix}{platform}{mirror_image(image)}{rest}\n")
            else:
                out.append(line if line.endswith("\n") else line + "\n")
    return "".join(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="mirror_rewrite_dockerfile",
        description="Print a Dockerfile with FROM base images rewritten to the mirror",
    )
    parser.add_argument("dockerfile", help="Path to the Dockerfile to rewrite")
    args = parser.parse_args()
    sys.stdout.write(rewrite(args.dockerfile))

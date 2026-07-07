#!/usr/bin/env python3
"""Wait for a weblog's base image to be available on Docker Hub.

Weblog base images (e.g. `datadog/system-tests:express4.base-<tag>`) are built and
pushed by a dedicated GitLab CI job (see `utils/scripts/build_base_images.py`), not by
GitHub Actions. There is no direct dependency mechanism between the two CI systems, so
this script simply polls `docker manifest inspect` for the tag declared in the weblog's
Dockerfile until it appears, or a timeout is reached.

It never builds or pushes anything: updating the tag in the weblog's Dockerfile after a
base image dependency changes remains the contributor's responsibility (see
docs/edit/update-docker-images.md).

Deliberately depends only on the standard library (no `utils` package, no venv) so it
can run as a plain CI step before the runner virtualenv is built.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _base_image_tag(library: str, weblog: str) -> str | None:
    """system-tests base image tag read from the first FROM in the weblog Dockerfile."""
    dockerfile = Path(f"utils/build/docker/{library}/{weblog}.Dockerfile")
    if not dockerfile.exists():
        print(f"Error: no Dockerfile found for weblog '{weblog}' in library '{library}'")
        sys.exit(1)

    for line in dockerfile.read_text().splitlines():
        if line.startswith("FROM "):
            image_name = line.split()[1]
            return image_name if image_name.startswith("datadog/system-tests:") else None
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for a weblog's base image to exist on Docker Hub")
    parser.add_argument("library", help="Library name (e.g. nodejs, python)")
    parser.add_argument("weblog", help="Weblog name (e.g. express4, flask-poc)")
    parser.add_argument("--timeout", type=int, default=900, help="Max time to wait, in seconds (default: 900)")
    parser.add_argument("--poll-interval", type=int, default=30, help="Time between polls, in seconds (default: 30)")
    args = parser.parse_args()

    image_tag = _base_image_tag(args.library, args.weblog)

    if image_tag is None:
        print(f"{args.weblog} does not use a system-tests base image, nothing to wait for")
        return

    print(f"Waiting for {image_tag} to be available on Docker Hub (timeout: {args.timeout}s)")

    deadline = time.monotonic() + args.timeout
    while True:
        result = subprocess.run(
            ["docker", "manifest", "inspect", image_tag],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"{image_tag} is available")
            return

        if time.monotonic() >= deadline:
            print(f"Error: timed out waiting for {image_tag}")
            if result.stderr:
                print(result.stderr.strip())
            sys.exit(1)

        print(f"{image_tag} not found yet, retrying in {args.poll_interval}s...")
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Wait for a weblog's base image to be available on Docker Hub.

Weblog base images (e.g. `datadog/system-tests:express4.base-<tag>`) are built and
pushed by a dedicated GitLab CI job (see `utils/base_images/build_base_images.py`), not by
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
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path

# Import the sibling stdlib-only helper without importing the utils package,
# which would initialize unrelated scenarios before the runner venv exists.
_BASE_IMAGE_MODULE = Path(__file__).resolve().parent / "base_image.py"
_BASE_IMAGE_SPEC = importlib.util.spec_from_file_location("base_image", _BASE_IMAGE_MODULE)
if _BASE_IMAGE_SPEC is None or _BASE_IMAGE_SPEC.loader is None:
    raise ImportError(f"Could not load {_BASE_IMAGE_MODULE}")
_BASE_IMAGE = importlib.util.module_from_spec(_BASE_IMAGE_SPEC)
_BASE_IMAGE_SPEC.loader.exec_module(_BASE_IMAGE)

base_image_ref = _BASE_IMAGE.base_image_ref

_MISSING_MANIFEST_ERRORS = ("manifest unknown", "no such manifest")


def _metadata_weblogs(metadata_lines: list[str]) -> tuple[set[str], dict[str, set[str]]]:
    weblogs: set[str] = set()
    framework_versions: dict[str, set[str]] = {}
    current_weblog: str | None = None

    for line in metadata_lines:
        if not line or line.startswith("#"):
            continue

        if not line.startswith(" "):
            name = line.split(":", 1)[0]
            if f"{name}:" not in line:
                continue

            current_weblog = name
            weblogs.add(name)
            continue

        match = re.search(r"^\s+framework_versions:\s*\[([^]]*)\]", line)
        if match and current_weblog:
            versions = set(re.findall(r"[\"']([^\"']+)[\"']", match.group(1)))
            framework_versions[current_weblog] = versions

    return weblogs, framework_versions


def _base_image_tag(library: str, weblog: str) -> str | None:
    """system-tests base image the weblog Dockerfile builds FROM (see base_image.py)."""
    dockerfile = Path(f"utils/build/docker/{library}/{weblog}.Dockerfile")
    if not dockerfile.exists():
        metadata = Path(f"utils/build/docker/{library}/weblog_metadata.yml")
        if not metadata.exists():
            print(f"Error: no library found at utils/build/docker/{library}")
            sys.exit(1)

        weblogs, framework_versions = _metadata_weblogs(metadata.read_text().splitlines())
        weblog_name, separator, version = weblog.partition("@")
        is_known_weblog = weblog in weblogs or (
            separator and weblog_name in weblogs and version in framework_versions.get(weblog_name, set())
        )
        if not is_known_weblog:
            print(f"Error: no Dockerfile found for weblog '{weblog}' in library '{library}'")
            sys.exit(1)

        print(f"{weblog} has no Dockerfile, nothing to wait for")
        return None

    return base_image_ref(dockerfile.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for a weblog's base image to exist on Docker Hub")
    parser.add_argument("library", help="Library name (e.g. nodejs, python)")
    parser.add_argument("weblog", help="Weblog name (e.g. express4, flask-poc)")
    parser.add_argument("--timeout", type=int, default=900, help="Max time to wait, in seconds (default: 900)")
    parser.add_argument("--poll-interval", type=int, default=30, help="Time between polls, in seconds (default: 30)")
    args = parser.parse_args()

    image_tag = _base_image_tag(args.library, args.weblog)

    if image_tag is None:
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
        error = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if result.returncode == 0:
            print(f"{image_tag} is available")
            return

        if not any(missing_manifest_error in error.lower() for missing_manifest_error in _MISSING_MANIFEST_ERRORS):
            print(f"Error: failed to inspect {image_tag}")
            if error:
                print(error)
            sys.exit(1)

        if time.monotonic() >= deadline:
            print(f"Error: timed out waiting for {image_tag}")
            if error:
                print(error)
            sys.exit(1)

        print(f"{image_tag} not found yet, retrying in {args.poll_interval}s...")
        if error:
            print(error)
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()

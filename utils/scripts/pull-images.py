import argparse
import concurrent.futures
import json
import multiprocessing
import random
import subprocess
import time

from utils.const import COMPONENT_GROUPS
from utils._context._scenarios import get_all_scenarios, DockerScenario
from utils._context.docker import get_docker_client


def get_registry(image: str) -> str:
    """Return the registry hostname for a given image name.

    Docker Hub images in all their forms return ``"docker.io"``:
    - ``<name>:<tag>``                        (e.g. ``cassandra:latest``)
    - ``<org>/<name>:<tag>``                  (e.g. ``apache/kafka:3.7.1``)
    - ``docker.io/<name>:<tag>``
    - ``docker.io/<org>/<name>:<tag>``

    Everything else has an explicit registry as the first ``/``-separated
    component (e.g. ``ghcr.io``, ``mcr.microsoft.com``).
    """
    parts = image.split("/")
    # <name>:<tag> with no slash at all → Docker Hub
    # <org>/<name>:<tag> with exactly one slash and no dot in the first part → Docker Hub
    # docker.io/<…> → Docker Hub (first part is "docker.io", caught by the dot check below)
    # Anything where the first part contains a dot is an explicit registry hostname.
    if "." not in parts[0]:
        return "docker.io"
    return parts[0]


def get_images_to_pull(scenarios: list[str], library: str, weblog: str) -> set[str]:
    """Return the set of images that need to be pulled for the given scenarios."""
    images: set[str] = set()

    existing_tags: list[str] = []
    for image in get_docker_client().images.list():
        existing_tags.extend(image.tags)

    for scenario in get_all_scenarios():
        if scenario.name in scenarios and isinstance(scenario, DockerScenario):
            images.update(scenario.get_image_list(library, weblog))

    # remove images that will be built locally, then remove images that already
    # exist locally (they may not exist in the registry, e.g. buddies)
    return {image for image in images if not image.startswith("system_tests/") and image not in existing_tags}


MAX_PARALLEL_PER_REGISTRY = 4


def _pull_single(image: str) -> str | None:
    """Pull a single image, retrying on failure.

    Returns ``None`` on success, or the image name if it could not be pulled
    after all retry attempts.
    """
    retry_delays = [
        (5, 5),  # base=5s, jitter range=5s
        (10, 10),  # base=10s, jitter range=10s
        (20, 20),  # base=20s, jitter range=20s
    ]

    for attempt in range(1 + len(retry_delays)):
        attempt_suffix = f" (attempt {attempt + 1})" if attempt > 0 else ""
        print(f"[start] {image}{attempt_suffix}", flush=True)
        result = subprocess.run(["docker", "pull", image], check=False, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"[success] {image}", flush=True)
            return None

        print(f"[failed] {image}\n{result.stdout}{result.stderr}", flush=True)

        if attempt < len(retry_delays):
            base, jitter_range = retry_delays[attempt]
            delay = base + random.uniform(0, jitter_range)
            time.sleep(delay)

    return image


def _pull_registry_images(registry_images: list[str]) -> list[str]:
    """Pull all images for one registry with up to MAX_PARALLEL_PER_REGISTRY workers.

    Returns the list of images that could not be pulled after all retry attempts.
    """
    workers = min(MAX_PARALLEL_PER_REGISTRY, len(registry_images))
    with multiprocessing.Pool(processes=workers) as pool:
        results = pool.map(_pull_single, registry_images)
    return [image for image in results if image is not None]


def pull_images(images: set[str]) -> None:
    """Pull *images* in parallel, grouped by registry.

    Up to ``MAX_PARALLEL_PER_REGISTRY`` images are pulled concurrently within
    each registry.  Different registries are also handled concurrently.

    Each pull is retried up to three times with exponential-ish back-off plus
    random jitter:

    * attempt 1 failure → wait 5 s + U(0, 5) s jitter
    * attempt 2 failure → wait 10 s + U(0, 10) s jitter
    * attempt 3 failure → wait 20 s + U(0, 20) s jitter

    Raises :class:`RuntimeError` if any image could not be pulled after all
    retry attempts.
    """
    if not images:
        return

    # Group images by registry
    registry_groups: dict[str, list[str]] = {}
    for image in sorted(images):
        registry = get_registry(image)
        registry_groups.setdefault(registry, []).append(image)

    print(f"Pulling {len(images)} images across {len(registry_groups)} registries", flush=True)

    # Run one task per registry concurrently; each task uses its own sub-pool
    # of up to MAX_PARALLEL_PER_REGISTRY processes.
    all_failed: list[str] = []
    pulled = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(registry_groups)) as executor:
        futures = {executor.submit(_pull_registry_images, imgs): registry for registry, imgs in registry_groups.items()}
        for future in concurrent.futures.as_completed(futures):
            failed = future.result()
            all_failed.extend(failed)
            pulled += len(registry_groups[futures[future]]) - len(failed)

    print(f"Done: {pulled}/{len(images)} images pulled successfully", flush=True)

    if all_failed:
        raise RuntimeError("Failed to pull the following images after all retry attempts:\n" + "\n".join(all_failed))


def main(scenarios: list[str], library: str, weblog: str) -> None:
    images = get_images_to_pull(scenarios, library, weblog)
    pull_images(images)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="pull-images", description="Pull all Docker images required to run the given scenarios"
    )
    parser.add_argument("scenarios", type=str, help="Scenarios to run. JSON array, or comma separated string")
    parser.add_argument(
        "--library",
        "-l",
        type=str,
        default="",
        help="One of the supported Datadog library",
        choices=[*sorted(COMPONENT_GROUPS.all), ""],
    )

    parser.add_argument("--weblog", "-w", type=str, help="End-to-end weblog", default="")

    args = parser.parse_args()

    if args.weblog and not args.library:
        parser.error("--weblog requires --library")
    if not args.weblog and args.library:
        parser.error("--library requires --weblog")

    main(
        json.loads(args.scenarios) if args.scenarios.startswith("[") else args.scenarios.split(","),
        library=args.library,
        weblog=args.weblog,
    )

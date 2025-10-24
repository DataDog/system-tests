import contextlib
from collections.abc import Generator
from typing import TextIO

from docker.models.containers import Container
import pytest

from utils._logger import logger
from utils._context.docker import get_docker_client


def get_host_port(worker_id: str, base_port: int) -> int:
    """Deterministic port allocation for each worker"""

    if worker_id == "master":  # xdist disabled
        return base_port

    if worker_id.startswith("gw"):
        return base_port + int(worker_id[2:])

    raise ValueError(f"Unexpected worker_id: {worker_id}")


def _compute_volumes(volumes: dict[str, str]) -> dict[str, dict]:
    """Convert volumes to the format expected by the docker-py API"""
    fixed_volumes: dict[str, dict] = {}
    for key, value in volumes.items():
        if isinstance(value, dict):
            fixed_volumes[key] = value
        elif isinstance(value, str):
            fixed_volumes[key] = {"bind": value, "mode": "rw"}
        else:
            raise TypeError(f"Unexpected type for volume {key}: {type(value)}")

    return fixed_volumes


@contextlib.contextmanager
def docker_run(
    image: str,
    name: str,
    env: dict[str, str],
    volumes: dict[str, str],
    network: str,
    ports: dict[str, int],
    log_file: TextIO,
    command: list[str] | None = None,
) -> Generator[Container, None, None]:
    logger.info(f"Run container {name} from image {image} with ports {ports}")

    try:
        container: Container = get_docker_client().containers.run(
            image,
            name=name,
            environment=env,
            volumes=_compute_volumes(volumes),
            network=network,
            ports=ports,
            command=command,
            detach=True,
        )
        logger.debug(f"Container {name} successfully started")
    except Exception as e:
        # at this point, even if it failed to start, the container may exists!
        for container in get_docker_client().containers.list(filters={"name": name}, all=True):
            container.remove(force=True)

        pytest.fail(f"Failed to run container {name}: {e}")

    try:
        yield container
    finally:
        logger.info(f"Stopping {name}")
        container.stop(timeout=1)
        logs = container.logs()
        log_file.write(logs.decode("utf-8"))
        log_file.flush()
        container.remove(force=True)

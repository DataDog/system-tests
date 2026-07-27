import contextlib
from collections.abc import Generator
from pathlib import Path
from typing import TextIO
from urllib.parse import urlparse

from docker.models.containers import Container
import pytest

from utils._logger import logger
from utils._context.docker import get_docker_client


HOST_DOCKER_INTERNAL = "host.docker.internal"
HOST_GATEWAY_EXTRA_HOSTS = {HOST_DOCKER_INTERNAL: "host-gateway"}


def get_host_port(worker_id: str, base_port: int) -> int:
    """Deterministic port allocation for each worker"""

    if worker_id == "master":  # xdist disabled
        return base_port

    if worker_id.startswith("gw"):
        return base_port + int(worker_id[2:])

    raise ValueError(f"Unexpected worker_id: {worker_id}")


def compute_volumes(volumes: dict[str, str]) -> dict[str, dict]:
    """Convert volumes to the format expected by the docker-py API"""
    fixed_volumes: dict[str, dict] = {}
    for key, value in volumes.items():
        # when host path starts with ./, resolve it from cwd()
        fixed_key = str(Path.cwd().joinpath(key)) if key.startswith("./") else key

        if isinstance(value, dict):
            fixed_volumes[fixed_key] = value
        elif isinstance(value, str):
            fixed_volumes[fixed_key] = {"bind": value, "mode": "rw"}
        else:
            raise TypeError(f"Unexpected type for volume {key}: {type(value)}")

    return fixed_volumes


def extra_hosts_for_environment(env: dict[str, str]) -> dict[str, str] | None:
    for value in env.values():
        if urlparse(str(value)).hostname == HOST_DOCKER_INTERNAL:
            return dict(HOST_GATEWAY_EXTRA_HOSTS)
    return None


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
    extra_hosts: dict[str, str] | None = None,
    stop_timeout: int = 1,
) -> Generator[Container, None, None]:
    """Run a docker container in detached mode and stop it on teardown.

    ``stop_timeout`` is the SIGTERM grace period (seconds) before SIGKILL. The default of 1s
    keeps cheap shutdown for fixtures that hold no state (e.g. the test agent). Containers that
    run user code with background threads holding host ports (e.g. parametric library clients
    with gRPC/OTLP exporters) should pass a larger value so those threads can drain cleanly;
    SIGKILLing mid-shutdown can leave host ports in TIME_WAIT and cause rare startup flakes for
    the next test on the same xdist worker.
    """
    logger.info(f"Run container {name} from image {image} with ports {ports}")

    try:
        container: Container = get_docker_client().containers.run(
            image,
            name=name,
            environment=env,
            volumes=compute_volumes(volumes),
            network=network,
            ports=ports,
            command=command,
            extra_hosts=extra_hosts,
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
        container.stop(timeout=stop_timeout)
        logs = container.logs()
        log_file.write(logs.decode("utf-8"))
        log_file.flush()
        container.remove(force=True)

from functools import lru_cache
import subprocess

import docker
from docker.errors import DockerException
import pytest
from requests.exceptions import RequestException

from utils._logger import logger


@lru_cache
def get_docker_client() -> docker.DockerClient:
    try:
        return docker.DockerClient.from_env()
    except DockerException as e:
        # Failed to start the default Docker client... Let's see if we have
        # better luck with docker contexts...
        try:
            ctx_name = subprocess.run(
                ["docker", "context", "show"], capture_output=True, check=True, text=True
            ).stdout.strip()
            endpoint = subprocess.run(
                ["docker", "context", "inspect", ctx_name, "-f", "{{ .Endpoints.docker.Host }}"],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            return docker.DockerClient(base_url=endpoint)
        except (subprocess.CalledProcessError, DockerException, RequestException, ValueError):
            logger.exception("No more success with docker contexts")

        if "Error while fetching server API version: ('Connection aborted.'" in str(e):
            pytest.exit("Connection refused to docker daemon, is it running?", 1)

        raise


# (command, keep the last lines instead of the first ones)
_HOST_DIAGNOSTIC_COMMANDS: list[tuple[list[str], bool]] = [
    (["uptime"], False),
    (["free", "-m"], False),
    (["df", "-h", "/"], False),
    (["ps", "aux", "--sort=-%mem"], False),
    (["sudo", "-n", "dmesg", "-T"], True),
    (["docker", "ps", "-a"], False),
]


def log_host_diagnostics(reason: str) -> None:
    """Log the host state when the docker daemon is slow, to tell memory/CPU starvation from a daemon issue."""
    logger.warning(f"Host diagnostics ({reason}):")
    for command, keep_last in _HOST_DIAGNOSTIC_COMMANDS:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
            output = (result.stdout + result.stderr).splitlines()
        except (OSError, subprocess.TimeoutExpired) as e:
            output = [f"failed: {e}"]

        lines = output[-40:] if keep_last else output[:40]
        logger.warning(f"$ {' '.join(command)}\n" + "\n".join(lines))

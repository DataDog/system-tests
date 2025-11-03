from functools import lru_cache
import subprocess

import docker
from docker.errors import DockerException
import pytest

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
        except:
            logger.exception("No more success with docker contexts")

        if "Error while fetching server API version: ('Connection aborted.'" in str(e):
            pytest.exit("Connection refused to docker daemon, is it running?", 1)

        raise

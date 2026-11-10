from functools import lru_cache
import subprocess

import docker
from docker.errors import DockerException
import pytest
from requests.exceptions import RequestException

from utils._logger import logger

# docker-py's default is 60s. A busy daemon (e.g. right after `docker load` of a big image on a GitHub
# runner) can take longer to answer `containers/create`, while still creating the container: the client
# fails, and the next scenario then fails with a 409 name conflict.
_DOCKER_CLIENT_TIMEOUT = 300


@lru_cache
def get_docker_client() -> docker.DockerClient:
    try:
        return docker.DockerClient.from_env(timeout=_DOCKER_CLIENT_TIMEOUT)
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
            return docker.DockerClient(base_url=endpoint, timeout=_DOCKER_CLIENT_TIMEOUT)
        except (subprocess.CalledProcessError, DockerException, RequestException, ValueError):
            logger.exception("No more success with docker contexts")

        if "Error while fetching server API version: ('Connection aborted.'" in str(e):
            pytest.exit("Connection refused to docker daemon, is it running?", 1)

        raise

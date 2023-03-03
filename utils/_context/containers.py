import os
from pathlib import Path

import docker
from docker.models.containers import Container
from utils.tools import logger

_client = docker.DockerClient()


class TestedContainer:

    # https://docker-py.readthedocs.io/en/stable/containers.html
    def __init__(self, name, image_name, allow_old_container=False, **kwargs) -> None:
        self.name = name
        self.container_name = f"system-tests-{name}"
        self.image_name = image_name
        self.allow_old_container = allow_old_container
        self.kwargs = kwargs

        self._container = None

    @property
    def log_folder_path(self):
        return f"/app/logs/docker/{self.name}"

    def get_existing_container(self) -> Container:
        for container in _client.containers.list():
            if container.name == self.container_name:
                logger.debug(f"Container {self.container_name} found")
                return container

    def start(self) -> Container:
        Path(self.log_folder_path).mkdir(exist_ok=True)

        if old_container := self.get_existing_container():
            if self.allow_old_container:
                self._container = old_container
                logger.debug(f"Use old container {self.container_name}")
                return

            logger.debug(f"Kill old container {self.container_name}")
            old_container.remove(force=True)

        self._fix_host_pwd_in_volumes()

        logger.info(f"Start container {self.container_name}")

        self._container = _client.containers.run(
            image=self.image_name,
            name=self.container_name,
            auto_remove=True,
            detach=True,
            hostname=self.name,
            network="system-tests_default",
            **self.kwargs,
        )

    def _fix_host_pwd_in_volumes(self):
        # on docker compose, volume host path can starts with a "."
        # it means the current path on host machine. It's not supported in bare docker
        # replicate this behavior here
        if "volumes" not in self.kwargs:
            return

        host_pwd = os.environ["HOST_PWD"]

        result = {}
        for k, v in self.kwargs["volumes"].items():
            if k.startswith("./"):
                k = f"{host_pwd}{k[1:]}"
            result[k] = v

        self.kwargs["volumes"] = result

    def save_logs(self):
        if not self._container:
            return

        with open(f"{self.log_folder_path}/stdout.log", "wb") as f:
            f.write(self._container.logs(stdout=True, stderr=False))

        with open(f"{self.log_folder_path}/stderr.log", "wb") as f:
            f.write(self._container.logs(stdout=False, stderr=True))

    def remove(self):
        if not self._container:
            return

        try:
            self._container.remove(force=True)
        except:
            # Sometimes, the container does not exists.
            # We can safely ignore this, because if it's another issue
            # it will be killed at startup

            pass

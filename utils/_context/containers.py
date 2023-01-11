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
        if old_container := self.get_existing_container():
            if self.allow_old_container:
                self._container = old_container
                logger.debug(f"Use old container {self.container_name}")
                return

            logger.debug(f"Kill old container {self.container_name}")
            old_container.kill()

        Path(self.log_folder_path).mkdir(exist_ok=True)

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

        self._container.remove(force=True)


agent_container = TestedContainer(
    image_name="system_tests/agent",
    name="agent",
    environment={
        "DD_API_KEY": os.environ["DD_API_KEY"],
        "DD_ENV": "system-tests",
        "DD_HOSTNAME": "test",
        "DD_SITE": os.environ.get("DD_SITE", "datad0g.com"),
        "DD_APM_RECEIVER_PORT": "8126",
        "DD_DOGSTATSD_PORT": "8125",  # TODO : move this in agent build ?
    },
)


def get_weblog_env():

    result = {
        "DD_AGENT_HOST": os.environ["DD_AGENT_HOST"],
        "DD_TRACE_AGENT_PORT": os.environ["DD_TRACE_AGENT_PORT"],
        "SYSTEMTESTS_SCENARIO": os.environ.get("SYSTEMTESTS_SCENARIO", "DEFAULT"),
    }

    with open("logs/.weblog.env", "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if len(line):
                name, value = line.split("=")
                result[name] = value

    return result


weblog_container = TestedContainer(
    image_name="system_tests/weblog",
    name="weblog",
    environment=get_weblog_env(),
    volumes={f"{os.environ['HOST_PWD']}/logs/docker/weblog/logs/": {"bind": "/var/log/system-tests", "mode": "rw"},},
)

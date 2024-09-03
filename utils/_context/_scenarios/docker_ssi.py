import os
from utils._context.library_version import LibraryVersion

from utils._context.containers import (
    create_network,
    DockerSSIContainer,
    APMTestAgentContainer,
    TestedContainer,
)
from utils.tools import logger

from .core import Scenario


class DockerSSIScenario(Scenario):
    """Scenario test the ssi installer on a docker environment and runs APM test agent """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self._weblog_injection = DockerSSIContainer(host_log_folder=self.host_log_folder)

        self._required_containers: list(TestedContainer) = []
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder))
        self._required_containers.append(self._weblog_injection)
        self.weblog_url = "http://localhost:18080"

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"
        super().configure(config)

        for container in self._required_containers:
            container.configure(self.replay)

    def session_start(self):
        """called at the very begning of the process"""
        super().session_start()
        container_weblog_url = self._weblog_injection.get_env("WEBLOG_URL")
        if container_weblog_url:
            self.weblog_url = container_weblog_url
        logger.info(f"Weblog URL: {self.weblog_url}")

    def _get_warmups(self):
        warmups = super()._get_warmups()

        warmups.append(create_network)

        for container in self._required_containers:
            warmups.append(container.start)

        return warmups

    def pytest_sessionfinish(self, session):
        self.close_targets()

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
                logger.info(f"Removing container {container}")
            except:
                logger.exception(f"Failed to remove container {container}")

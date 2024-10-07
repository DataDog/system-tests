import pytest

from utils._context.containers import DummyServerContainer, ExternalProcessingContainer, EnvoyContainer, AgentContainer
from utils.tools import logger

from .endtoend import DockerScenario, ScenarioGroup


class ExternalProcessingScenario(DockerScenario):
    def __init__(self, name):
        super().__init__(
            name,
            doc="Envoy + external processing",
            github_workflow="externalprocessing",
            scenario_groups=[ScenarioGroup.END_TO_END, ScenarioGroup.EXTERNAL_PROCESSING],
            use_proxy=True,
        )

        self._agent_container = AgentContainer(self.host_log_folder)
        self._external_processing_container = ExternalProcessingContainer(self.host_log_folder)
        self._envoy_container = EnvoyContainer(self.host_log_folder)
        self._http_app_container = DummyServerContainer(self.host_log_folder)

        self._agent_container.depends_on.append(self.proxy_container)
        self._external_processing_container.depends_on.append(self.proxy_container)

        self._required_containers.append(self._agent_container)
        self._required_containers.append(self._external_processing_container)
        self._required_containers.append(self._envoy_container)
        self._required_containers.append(self._http_app_container)

        # start envoyproxy/envoy:v1.31-latest⁠
        # -> envoy.yaml configuration in tests/external_processing/envoy.yaml

        # start dummy http app on weblog port
        # -> server.py in tests/external_processing/server.py

        # start system-tests proxy
        # start agent
        # start service extension
        #    with agent url threw system-tests proxy

        # service extension image:
        # https://github.com/DataDog/dd-trace-go/pkgs/container/dd-trace-go%2Fservice-extensions-callout
        # Version:
        # tag: dev
        # base: latest/v*.*.*

    def configure(self, config):
        from utils import interfaces

        super().configure(config)

        interfaces.library.configure(self.replay)
        interfaces.agent.configure(self.replay)

    def _start_interfaces_watchdog(self, _=None):
        from utils import interfaces

        super()._start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def _wait_for_app_readiness(self):
        from utils import interfaces  # import here to avoid circular import

        logger.debug("Wait for app readiness")

        if not interfaces.library.ready.wait(40):
            pytest.exit("Nothing received from external processing", 1)
        logger.debug("Library ready")

        if not interfaces.agent.ready.wait(40):
            pytest.exit("Datadog agent not ready", 1)
        logger.debug("Agent ready")

    def get_warmups(self) -> list:
        warmups = super().get_warmups()

        if not self.replay:
            warmups.insert(1, self._start_interfaces_watchdog)
            warmups.append(self._wait_for_app_readiness)

        return warmups

    def post_setup(self):
        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

    def _wait_and_stop_containers(self):
        from utils import interfaces

        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.library.load_data_from_logs()
            interfaces.library.check_deserialization_errors()

            interfaces.agent.load_data_from_logs()
            interfaces.agent.check_deserialization_errors()

        else:
            self._wait_interface(interfaces.library, 5)

            self._http_app_container.stop()
            self._envoy_container.stop()
            self._external_processing_container.stop()

            interfaces.library.check_deserialization_errors()

            self._agent_container.stop()
            interfaces.agent.check_deserialization_errors()

    def _wait_interface(self, interface, timeout):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    @property
    def weblog_variant(self):
        return "external-processing"

    @property
    def library(self):
        return self._external_processing_container.library

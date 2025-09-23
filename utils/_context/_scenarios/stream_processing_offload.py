import pytest

from utils._context.containers import (
    DummyServerContainer,
    StreamProcessingOffloadContainer,
    HAProxyContainer,
    AgentContainer,
)
from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator

from utils._logger import logger

from .core import scenario_groups
from .endtoend import DockerScenario


class StreamProcessingOffloadScenario(DockerScenario):
    def __init__(
        self,
        name: str,
        doc: str,
        *,
        stream_processing_offload_env: dict[str, str | None] | None = None,
        stream_processing_offload_volumes: dict[str, dict[str, str]] | None = None,
        rc_api_enabled: bool = False,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="streamprocessingoffload",
            scenario_groups=[
                scenario_groups.end_to_end,
                scenario_groups.stream_processing_offload,
                scenario_groups.all,
            ],
            use_proxy=True,
            rc_api_enabled=rc_api_enabled,
        )

        self._agent_container = AgentContainer()
        self._stream_processing_offload_container = StreamProcessingOffloadContainer(
            env=stream_processing_offload_env,
            volumes=stream_processing_offload_volumes,
        )
        self._haproxy_container = HAProxyContainer()
        self._http_app_container = DummyServerContainer()

        self._agent_container.depends_on.append(self.proxy_container)
        self._stream_processing_offload_container.depends_on.append(self.proxy_container)
        # Ensure HAProxy starts after SPOE agent and the HTTP app so DNS resolves
        self._haproxy_container.depends_on.append(self._stream_processing_offload_container)
        self._haproxy_container.depends_on.append(self._http_app_container)

        self._required_containers.append(self._agent_container)
        self._required_containers.append(self._stream_processing_offload_container)
        self._required_containers.append(self._haproxy_container)
        self._required_containers.append(self._http_app_container)

    def configure(self, config: pytest.Config):
        super().configure(config)

        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent.configure(self.host_log_folder, replay=self.replay)

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def _wait_for_app_readiness(self):
        logger.debug("Wait for app readiness")

        if not interfaces.library.ready.wait(40):
            pytest.exit("Nothing received from the SPOE Agent", 1)
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

    def post_setup(self, session: pytest.Session):  # noqa: ARG002
        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

    def _wait_and_stop_containers(self):
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
            self._haproxy_container.stop()
            self._stream_processing_offload_container.stop()

            interfaces.library.check_deserialization_errors()

            self._agent_container.stop()
            interfaces.agent.check_deserialization_errors()

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    @property
    def weblog_variant(self):
        return "haproxy-spoe"

    @property
    def library(self):
        return self._stream_processing_offload_container.library

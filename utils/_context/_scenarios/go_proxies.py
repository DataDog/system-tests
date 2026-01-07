import os
from typing import Optional, Union

import pytest

from utils._context.containers import (
    AgentContainer,
    DummyServerContainer,
    EnvoyContainer,
    ExternalProcessingContainer,
    HAProxyContainer,
    StreamProcessingOffloadContainer,
)
from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils._logger import logger

from .core import scenario_groups
from .endtoend import DockerScenario

ProcessorContainer = Union[ExternalProcessingContainer, StreamProcessingOffloadContainer]
ProxyRuntimeContainer = Union[EnvoyContainer, HAProxyContainer]


class GoProxiesScenario(DockerScenario):
    def __init__(
        self,
        name: str,
        doc: str,
        *,
        processor_env: Optional[dict[str, Optional[str]]] = None,
        processor_volumes: Optional[dict[str, dict[str, str]]] = None,
        rc_api_enabled: bool = False,
    ) -> None:
        self._weblog_variant = os.environ.get("WEBLOG_VARIANT", "envoy")
        self._processor_env = processor_env
        self._processor_volumes = processor_volumes

        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.end_to_end, scenario_groups.go_proxies, scenario_groups.all],
            use_proxy=True,
            rc_api_enabled=rc_api_enabled,
        )

        self._agent_container = AgentContainer()
        self._processor_container: ProcessorContainer = self._build_processor_container()
        self._proxy_runtime_container: ProxyRuntimeContainer = self._build_proxy_runtime_container()
        self._http_app_container = DummyServerContainer()

        self._agent_container.depends_on.append(self.proxy_container)
        self._processor_container.depends_on.append(self.proxy_container)

        self._proxy_runtime_container.depends_on.append(self._processor_container)
        self._proxy_runtime_container.depends_on.append(self._http_app_container)

        self._required_containers.append(self._agent_container)
        self._required_containers.append(self._processor_container)
        self._required_containers.append(self._proxy_runtime_container)
        self._required_containers.append(self._http_app_container)


    def _build_processor_container(self) -> ProcessorContainer:
        env = dict(self._processor_env or {})
        volumes = dict(self._processor_volumes or {})

        if self._weblog_variant == "envoy":
            return ExternalProcessingContainer(env=env, volumes=volumes)

        return StreamProcessingOffloadContainer(env=env, volumes=volumes)

    def _build_proxy_runtime_container(self) -> ProxyRuntimeContainer:
        if self._weblog_variant == "envoy":
            return EnvoyContainer()

        return HAProxyContainer()

    def configure(self, config: pytest.Config):
        super().configure(config)

        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent.configure(self.host_log_folder, replay=self.replay)

        if not self.replay:
            self.warmups.insert(1, self._start_interfaces_watchdog)
            self.warmups.append(self._wait_for_app_readiness)
            self.warmups.append(lambda: logger.stdout(f"Weblog variant: {self._weblog_variant}"))

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def _wait_for_app_readiness(self):
        logger.debug("Wait for app readiness (%s)", self._weblog_variant)

        if not interfaces.library.ready.wait(40):
            pytest.exit("Nothing received from the security processor", 1)
        logger.debug("Library ready")

        if not interfaces.agent.ready.wait(40):
            pytest.exit("Datadog agent not ready", 1)
        logger.debug("Agent ready")

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
            self._proxy_runtime_container.stop()
            self._processor_container.stop()

            interfaces.library.check_deserialization_errors()

            self._agent_container.stop()
            interfaces.agent.check_deserialization_errors()

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    @property
    def weblog_variant(self):
        return self._weblog_variant

    @property
    def library(self):
        return self._processor_container.library

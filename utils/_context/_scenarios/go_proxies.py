import os
from pathlib import Path

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

from .core import scenario_groups as all_scenario_groups, ScenarioGroup
from .endtoend import DockerScenario

ProcessorContainer = ExternalProcessingContainer | StreamProcessingOffloadContainer
ProxyRuntimeContainer = EnvoyContainer | HAProxyContainer

GO_PROXIES_WEBLOGS: dict[str, list[str]] = {
    "envoy": ["envoyproxy"],
    "haproxy": ["haproxy-spoa"],
}


class GoProxiesScenario(DockerScenario):
    def __init__(
        self,
        name: str,
        doc: str,
        *,
        processor_env: dict[str, str | None] | None = None,
        processor_volumes: dict[str, dict[str, str]] | None = None,
        proxy_component: str | None = None,
        weblog_variant: str | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        rc_api_enabled: bool = False,
    ) -> None:
        self._processor_env = processor_env
        self._processor_volumes = processor_volumes
        self._scenario_groups = (scenario_groups or []) + [
            all_scenario_groups.appsec,
            all_scenario_groups.end_to_end,
            all_scenario_groups.all,
        ]

        if proxy_component is None:
            pytest.skip("No proxy component specified")

        assert proxy_component is not None  # linter fix
        self._proxy_component = proxy_component
        if weblog_variant:
            self._weblog_variant_is_default = False
        else:
            weblog_variant = GO_PROXIES_WEBLOGS.get(self._proxy_component, [None])[0]
            self._weblog_variant_is_default = True

        if not weblog_variant:
            pytest.skip("No weblog variant specified", 1)

        assert weblog_variant is not None  # linter fix
        self._weblog_variant = weblog_variant

        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            scenario_groups=self._scenario_groups,
            use_proxy=True,
            rc_api_enabled=rc_api_enabled,
        )

        self._base_required_containers = list(self._required_containers)
        self._init_containers()

    def _build_processor_container(self) -> ProcessorContainer:
        env = dict(self._processor_env or {})
        volumes = dict(self._processor_volumes or {})

        if self._proxy_component == "envoy":
            return ExternalProcessingContainer(env=env, volumes=volumes)

        return StreamProcessingOffloadContainer(env=env, volumes=volumes)

    def _build_proxy_runtime_container(self) -> ProxyRuntimeContainer:
        if self._proxy_component == "envoy":
            return EnvoyContainer()

        return HAProxyContainer()

    def configure(self, config: pytest.Config) -> None:
        if self.replay:
            component_from_logs = self._discover_proxy_component_from_logs()

            if component_from_logs and component_from_logs != self._proxy_component:
                logger.stdout(f"Replay detected proxy component from logs: {component_from_logs}")
                self._set_proxy_component(component_from_logs)

        super().configure(config)

        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent.configure(self.host_log_folder, replay=self.replay)

        if not self.replay:
            self.warmups.insert(1, self._start_interfaces_watchdog)
            self.warmups.append(self._wait_for_app_readiness)
            self.warmups.append(lambda: logger.stdout(f"Weblog variant: {self._weblog_variant}"))
            self.warmups.append(lambda: logger.stdout(f"Proxy component: {self._proxy_component}"))
            self.warmups.append(self._set_components)

    def _start_interfaces_watchdog(self) -> None:
        super().start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def _wait_for_app_readiness(self) -> None:
        logger.debug("Wait for app readiness (%s)", self._weblog_variant)

        if not interfaces.library.ready.wait(40):
            pytest.exit("Nothing received from the security processor", 1)
        logger.debug("Library ready")

        if not interfaces.agent.ready.wait(40):
            pytest.exit("Datadog agent not ready", 1)
        logger.debug("Agent ready")

    def _set_components(self) -> None:
        self.components["agent"] = self._agent_container.agent_version
        lib = self.library
        self.components["library"] = lib.version
        self.components[lib.name] = lib.version

    def post_setup(self, session: pytest.Session) -> None:  # noqa: ARG002
        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

    def _wait_and_stop_containers(self) -> None:
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

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int) -> None:
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    def _init_containers(self) -> None:
        self._agent_container = AgentContainer()
        self._processor_container = self._build_processor_container()
        self._proxy_runtime_container = self._build_proxy_runtime_container()
        self._http_app_container = DummyServerContainer()

        self._agent_container.depends_on = [self.proxy_container]
        self._processor_container.depends_on = [self.proxy_container]
        self._proxy_runtime_container.depends_on = [self._processor_container, self._http_app_container]

        self._required_containers = [
            *self._base_required_containers,
            self._agent_container,
            self._processor_container,
            self._proxy_runtime_container,
            self._http_app_container,
        ]

    def _set_proxy_component(self, proxy_component: str) -> None:
        if self._proxy_component == proxy_component:
            return

        self._proxy_component = proxy_component
        if self._weblog_variant_is_default:
            self._weblog_variant = GO_PROXIES_WEBLOGS[self._proxy_component][0]
        self._init_containers()

    def _discover_proxy_component_from_logs(self) -> str | None:
        docker_logs_dir = Path(os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", Path.cwd()))
        docker_logs_dir = docker_logs_dir / self.host_log_folder / "docker"

        for component in ("haproxy", "envoy"):
            if (docker_logs_dir / component).is_dir():
                return component

        return None

    @property
    def weblog_variant(self) -> str:
        return self._weblog_variant

    @property
    def proxy_component(self) -> str:
        return self._proxy_component

    @property
    def library(self):
        return self._processor_container.library

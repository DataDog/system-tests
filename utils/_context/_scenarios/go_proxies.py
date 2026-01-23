import json
import os
from pathlib import Path

import pytest

from utils import interfaces
from utils._context.component_version import Version
from utils._context.containers import (
    AgentContainer,
    DummyServerContainer,
    EnvoyContainer,
    ExternalProcessingContainer,
    HAProxyContainer,
    StreamProcessingOffloadContainer,
)
from utils._logger import logger
from utils.interfaces._core import ProxyBasedInterfaceValidator

from .core import ScenarioGroup, scenario_groups as all_scenario_groups
from .endtoend import DockerScenario


ProcessorContainer = ExternalProcessingContainer | StreamProcessingOffloadContainer
ProxyRuntimeContainer = EnvoyContainer | HAProxyContainer

# Link each weblog variant to the proxy component it uses
GO_PROXIES_WEBLOGS: dict[str, str] = {
    "envoy": "envoy",
    "haproxy-spoa": "haproxy",
}


class GoProxiesScenario(DockerScenario):
    def __init__(
        self,
        name: str,
        doc: str,
        *,
        processor_env: dict[str, str | None] | None = None,
        processor_volumes: dict[str, dict[str, str]] | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        rc_api_enabled: bool = False,
    ) -> None:
        self._processor_env = processor_env
        self._processor_volumes = processor_volumes
        self._scenario_groups = (scenario_groups or []) + [
            all_scenario_groups.go_proxies,
            all_scenario_groups.appsec,
            all_scenario_groups.end_to_end,
            all_scenario_groups.all,
        ]

        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            scenario_groups=self._scenario_groups,
            use_proxy=True,
            rc_api_enabled=rc_api_enabled,
        )

        self._base_required_containers = list(self._required_containers)

    def _build_processor_container(self) -> ProcessorContainer:
        if self.proxy_component == "envoy":
            return ExternalProcessingContainer(env=self._processor_env, volumes=self._processor_volumes)
        return StreamProcessingOffloadContainer(env=self._processor_env, volumes=self._processor_volumes)

    def _build_proxy_runtime_container(self) -> ProxyRuntimeContainer:
        if self.proxy_component == "envoy":
            return EnvoyContainer()
        return HAProxyContainer()

    def configure(self, config: pytest.Config) -> None:
        self._set_information(config)
        self._init_containers()

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

    def _set_information(self, config: pytest.Config) -> None:
        requested_weblog_variant = config.option.weblog
        version: Version | None = None

        if self.replay:
            requested_weblog_variant, version = self._discover_weblog_and_version_from_logs()

        if requested_weblog_variant not in GO_PROXIES_WEBLOGS:
            pytest.exit(
                f"Unsupported Go proxies weblog variant '{requested_weblog_variant}'. "
                "Please set with --weblog. "
                f"Supported variants: {', '.join(sorted(GO_PROXIES_WEBLOGS))}",
                1,
            )

        self._weblog_variant = requested_weblog_variant
        self._proxy_component = GO_PROXIES_WEBLOGS[self._weblog_variant]

        if version:
            self.components["library"] = version
            self.components[self._proxy_component] = version

    def _discover_weblog_and_version_from_logs(self) -> tuple[str | None, Version | None]:
        weblog_variant = None
        version = None

        docker_logs_dir = Path(os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", Path.cwd())) / self.host_log_folder
        fp = docker_logs_dir / "feature_parity.json"

        try:
            with fp.open(encoding="utf-8") as f:
                feature_parity = json.load(f)
        except Exception as e:
            logger.warning("Replay mode error: %s", e)
            return None, None

        weblog_variant = feature_parity.get("variant")
        deps = feature_parity.get("testedDependencies") or []

        for dep in deps:
            if isinstance(dep, dict) and dep.get("name") == "library":
                version = dep.get("version")
                break

        return weblog_variant, Version(version) if version else None

    @property
    def weblog_variant(self) -> str:
        return self._weblog_variant

    @property
    def proxy_component(self) -> str:
        return self._proxy_component

    @property
    def library(self):
        return self._processor_container.library

import json
from pathlib import Path
from typing import Literal, Protocol

import pytest

from utils import interfaces
from utils._context.containers import ServerlessInitContainer, TestedContainer
from utils.docker_fixtures._core import extra_hosts_for_environment
from utils.mocked_backend.ffe import EXPECTED_API_KEY, MockFFEAgentlessBackendServer
from utils.proxy.ports import ProxyPorts
from utils.proxy.tuf import get_tuf_root_json

from .core import ScenarioGroup, scenario_groups as all_scenario_groups
from .endtoend import DdTraceEndToEndScenario

# Reused as the mock DD_API_KEY for agentless scenarios that don't need FFE's own mock backend.
AGENTLESS_MOCK_API_KEY = EXPECTED_API_KEY


class AgentlessBackendServer(Protocol):
    """Structural type for the mock backend servers plugged into `AgentlessEndToEndScenario`."""

    def reset(self) -> None: ...
    def status(self) -> object: ...
    def close(self) -> None: ...


class AgentlessEndToEndScenario(DdTraceEndToEndScenario):
    """End-to-end scenario without a Datadog Agent, using agentless delivery mechanisms."""

    _default_scenario_groups: tuple[ScenarioGroup, ...] = ()  # exclude those scenario from tracer_release
    _mock_backend_status_filename = "mock_agentless_backend_status.json"

    _mock_backend: AgentlessBackendServer | None = None
    _last_mock_backend_status: object | None = None

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        weblog_env: dict[str, str | None] | None = None,
        other_weblog_containers: tuple[type[TestedContainer], ...] = (),
        scenario_groups: tuple[ScenarioGroup, ...] = (),
        capture_direct_egress: bool = True,
        rc_api_enabled: bool = False,
        rc_backend_enabled: bool = False,
        library_interface_timeout: int = 0,
    ) -> None:
        self.capture_direct_egress = capture_direct_egress

        environment: dict[str, str | None] = dict(weblog_env or {})
        if capture_direct_egress:
            environment.setdefault(
                # The reserved .invalid domain fails closed if a request bypasses the proxy.
                "DD_SITE",
                "mock-intake.invalid",
            )
            environment.setdefault("DD_PROXY_HTTPS", f"http://proxy:{ProxyPorts.datadog_direct}")
            environment.setdefault("HTTPS_PROXY", f"http://proxy:{ProxyPorts.datadog_direct}")

        weblog_volumes: dict | None = None
        if capture_direct_egress:
            # The weblog talks HTTPS directly to the proxy (CONNECT tunnel), which
            # terminates TLS with the mitmproxy CA -- same trust anchor already
            # mounted into AgentContainer (utils/_context/containers.py) for its
            # own HTTP_PROXY-based backend traffic.
            weblog_volumes = {
                "./utils/build/docker/agent/ca-certificates.crt": {
                    "bind": "/etc/ssl/certs/ca-certificates.crt",
                    "mode": "ro",
                },
            }

        if rc_backend_enabled:
            # The native agentless RC client only trusts Datadog's real embedded
            # production/staging/gov TUF roots by default, so it would never trust the
            # mocked backend's test-signed response without this override -- mirrors the
            # same env vars/root JSON already used to make the real Agent trust the test
            # TUF key (utils/_context/containers.py::AgentContainer.__init__).
            tuf_root_json = get_tuf_root_json()
            environment.setdefault("DD_REMOTE_CONFIGURATION_ENABLED", "true")
            environment.setdefault("DD_REMOTE_CONFIGURATION_CONFIG_ROOT", tuf_root_json)
            environment.setdefault("DD_REMOTE_CONFIGURATION_DIRECTOR_ROOT", tuf_root_json)

        super().__init__(
            name,
            doc=doc,
            include_agent=False,
            library_interface_timeout=library_interface_timeout,
            other_weblog_containers=other_weblog_containers,
            scenario_groups=[*scenario_groups, all_scenario_groups.agentless],
            use_proxy_for_agent=False,
            use_proxy_for_weblog=capture_direct_egress,
            rc_api_enabled=rc_api_enabled,
            rc_backend_enabled=rc_backend_enabled,
            weblog_env=environment,
            weblog_volumes=weblog_volumes,
        )

    def configure(self, config: pytest.Config) -> None:
        try:
            if self.replay:
                self._load_mock_backend_status()
            else:
                self._last_mock_backend_status = None
                self._start_mock_backend()

            super().configure(config)

            if self.capture_direct_egress:
                interfaces.datadog_direct.configure(self.host_log_folder, replay=self.replay)
        except BaseException:
            self._stop_mock_backend(persist_status=False)
            raise

    def _wait_for_app_readiness(self) -> None:
        if self.capture_direct_egress:
            # Agentless mode never sends agent-facing traffic (/v0.4/traces, etc.), so
            # interfaces.library.ready (set only by such traffic) would never fire here.
            # The weblog container's own healthcheck already confirms it's up.
            return
        super()._wait_for_app_readiness()

    def _create_mock_backend(self) -> AgentlessBackendServer | None:
        """Override in subclasses that need a mock agentless config/data backend."""
        return None

    def _start_mock_backend(self) -> None:
        assert self._mock_backend is None, "mock agentless backend is already running"

        backend = self._create_mock_backend()
        if backend is None:
            return

        self._mock_backend = backend
        backend.reset()

    def mock_backend_status(self) -> object | None:
        if self._mock_backend is not None:
            return self._mock_backend.status()
        return self._last_mock_backend_status

    @property
    def _mock_backend_status_path(self) -> Path:
        return Path(self.host_log_folder) / self._mock_backend_status_filename

    def _load_mock_backend_status(self) -> None:
        self._last_mock_backend_status = json.loads(self._mock_backend_status_path.read_text(encoding="utf-8"))

    def _stop_mock_backend(self, *, persist_status: bool = True) -> None:
        backend = self._mock_backend
        if backend is None:
            return

        self._mock_backend = None
        try:
            if persist_status:
                self._last_mock_backend_status = backend.status()
                self._mock_backend_status_path.parent.mkdir(parents=True, exist_ok=True)
                self._mock_backend_status_path.write_text(
                    json.dumps(self._last_mock_backend_status, indent=2) + "\n",
                    encoding="utf-8",
                )
        finally:
            backend.close()

    def close_targets(self) -> None:
        try:
            super().close_targets()
        finally:
            self._stop_mock_backend()

    def _start_interfaces_watchdog(self) -> None:
        super()._start_interfaces_watchdog()
        if self.capture_direct_egress:
            self.start_interfaces_watchdog([interfaces.datadog_direct])

    def _wait_and_stop_containers(self, *, is_empty_test_run: bool) -> None:
        super()._wait_and_stop_containers(is_empty_test_run=is_empty_test_run)
        if not self.capture_direct_egress:
            return

        if self.replay:
            interfaces.datadog_direct.load_data_from_logs()

        interfaces.datadog_direct.check_deserialization_errors()


class FeatureFlaggingAgentlessEndToEndScenario(AgentlessEndToEndScenario):
    """FFE end-to-end scenario with UFC available before the weblog starts."""

    def __init__(
        self,
        name: str,
        *,
        doc: str = "Validate default agentless UFC delivery and evaluation without a Datadog Agent.",
        exposure_egress: Literal["sidecar", "direct"] | None = None,
        weblog_env: dict[str, str | None] | None = None,
    ) -> None:
        self.exposure_egress = exposure_egress
        environment: dict[str, str | None] = {
            # Both variables are integer seconds across the SDKs: Java parses them with
            # getInteger, and the shared configuration registry declares them "int" with an
            # allowed pattern of [1-9]\d*. A fractional value only ever worked on Node, which
            # has a single numeric type and does not enforce that pattern; it is a hard parse
            # error in the strictly-typed libraries. 1s is the smallest legal interval.
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "1",
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS": "2",
            "DD_REMOTE_CONFIGURATION_ENABLED": "false",
        }
        environment.update(weblog_env or {})

        other_weblog_containers: tuple[type[TestedContainer], ...] = ()
        if exposure_egress == "sidecar":
            serverless_init_port = str(ServerlessInitContainer.apm_receiver_port)
            environment |= {
                "DD_AGENT_HOST": "ffe-serverless-init",
                "DD_TRACE_AGENT_PORT": serverless_init_port,
                "DD_TRACE_AGENT_URL": f"http://ffe-serverless-init:{serverless_init_port}",
            }
            other_weblog_containers = (ServerlessInitContainer,)

        super().__init__(
            name,
            doc=doc,
            other_weblog_containers=other_weblog_containers,
            scenario_groups=(all_scenario_groups.ffe,),
            capture_direct_egress=exposure_egress is not None,
            weblog_env=environment,
        )

        if exposure_egress == "direct":
            # Direct mode uses the proxy only to capture HTTPS intake requests.
            # Do not advertise the proxy as a local Agent endpoint.
            for env_name in ("DD_AGENT_HOST", "DD_DOGSTATSD_HOST", "DD_TRACE_AGENT_PORT", "DD_TRACE_AGENT_URL"):
                self.weblog_infra.library_container.environment.pop(env_name, None)

    def _create_mock_backend(self) -> MockFFEAgentlessBackendServer:
        return MockFFEAgentlessBackendServer()

    def _start_mock_backend(self) -> None:
        super()._start_mock_backend()
        backend = self._mock_backend
        assert isinstance(backend, MockFFEAgentlessBackendServer)

        environment = self.weblog_infra.library_container.environment
        environment |= {
            "DD_API_KEY": EXPECTED_API_KEY,
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": backend.library_config_url,
        }
        self.weblog_infra.library_container.extra_hosts = extra_hosts_for_environment(environment)

    def configure(self, config: pytest.Config) -> None:
        try:
            super().configure(config)
            if self.exposure_egress is not None:
                interfaces.datadog_sidecar.configure(self.host_log_folder, replay=self.replay)
        except BaseException:
            self._stop_mock_backend(persist_status=False)
            raise

    @property
    def serverless_init_container(self) -> ServerlessInitContainer:
        for container in self.weblog_infra.get_containers():
            if isinstance(container, ServerlessInitContainer):
                return container
        raise ValueError("This scenario has no serverless-init container")

    def _set_containers_dependancies(self) -> None:
        super()._set_containers_dependancies()
        if self.exposure_egress == "sidecar":
            self.serverless_init_container.depends_on.append(self.proxy_container)

    def _start_interfaces_watchdog(self) -> None:
        super()._start_interfaces_watchdog()
        if self.exposure_egress is not None:
            self.start_interfaces_watchdog([interfaces.datadog_sidecar])

    def _wait_for_app_readiness(self) -> None:
        if self.exposure_egress is not None:
            return
        super()._wait_for_app_readiness()

    def _set_components(self) -> None:
        super()._set_components()
        if self.exposure_egress == "sidecar":
            self.components["serverless-init"] = self.serverless_init_container.serverless_init_version

    def _wait_and_stop_containers(self, *, is_empty_test_run: bool) -> None:
        super()._wait_and_stop_containers(is_empty_test_run=is_empty_test_run)
        if self.exposure_egress is None:
            return

        if self.replay:
            interfaces.datadog_sidecar.load_data_from_logs()
        elif self.exposure_egress == "sidecar":
            self.serverless_init_container.stop()

        interfaces.datadog_sidecar.check_deserialization_errors()

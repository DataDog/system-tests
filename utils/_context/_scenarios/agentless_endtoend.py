import json
from pathlib import Path
from typing import cast

import pytest

from utils.docker_fixtures._core import extra_hosts_for_environment
from utils.mocked_backend.ffe import (
    EXPECTED_API_KEY,
    MockFFEAgentlessBackendServer,
    MockFFEAgentlessBackendStatus,
)

from .core import ScenarioGroup, scenario_groups as all_scenario_groups
from .endtoend import DdTraceEndToEndScenario


class AgentlessEndToEndScenario(DdTraceEndToEndScenario):
    """End-to-end scenario without a Datadog Agent, using agentless delivery mechanisms."""

    _default_scenario_groups:tuple[ScenarioGroup,...] = ()  # exclude those scenario from tracer_release
    _mock_backend_status_filename = "mock_agentless_backend_status.json"

    _mock_backend: MockFFEAgentlessBackendServer | None = None
    _last_mock_backend_status: MockFFEAgentlessBackendStatus | None = None

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        weblog_env: dict[str, str | None] | None = None,
        scenario_groups: tuple[ScenarioGroup, ...] = (),
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            include_agent=False,
            library_interface_timeout=0,
            scenario_groups=[*scenario_groups, all_scenario_groups.agentless],
            use_proxy_for_agent=False,
            use_proxy_for_weblog=False,
            weblog_env=weblog_env,
        )

    def configure(self, config: pytest.Config) -> None:
        try:
            if self.replay:
                self._load_mock_backend_status()
            else:
                self._last_mock_backend_status = None
                self._start_mock_backend()

            super().configure(config)
        except BaseException:
            self._stop_mock_backend(persist_status=False)
            raise

    def _start_mock_backend(self) -> None:
        assert self._mock_backend is None, "mock FFE agentless backend is already running"

        self._mock_backend = MockFFEAgentlessBackendServer()
        self._mock_backend.reset()

        environment = self.weblog_infra.library_container.environment
        environment |= {
            "DD_API_KEY": EXPECTED_API_KEY,
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": self._mock_backend.library_config_url,
        }
        self.weblog_infra.library_container.extra_hosts = extra_hosts_for_environment(environment)

    def mock_backend_status(self) -> MockFFEAgentlessBackendStatus | None:
        if self._mock_backend is not None:
            return self._mock_backend.status()
        return self._last_mock_backend_status

    @property
    def _mock_backend_status_path(self) -> Path:
        return Path(self.host_log_folder) / self._mock_backend_status_filename

    def _load_mock_backend_status(self) -> None:
        self._last_mock_backend_status = cast(
            "MockFFEAgentlessBackendStatus",
            json.loads(self._mock_backend_status_path.read_text(encoding="utf-8")),
        )

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


class FeatureFlaggingAgentlessEndToEndScenario(AgentlessEndToEndScenario):
    """FFE end-to-end scenario with UFC available before the weblog starts."""

    def __init__(
        self,
        name: str,
        *,
        doc: str = "Validate default agentless UFC delivery and evaluation without a Datadog Agent.",
        weblog_env: dict[str, str | None] | None = None,
    ) -> None:
        environment: dict[str, str | None] = {
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_POLL_INTERVAL_SECONDS": "0.2",
            "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_REQUEST_TIMEOUT_SECONDS": "2",
            "DD_REMOTE_CONFIGURATION_ENABLED": "false",
        }
        environment.update(weblog_env or {})

        super().__init__(
            name,
            doc=doc,
            scenario_groups=(all_scenario_groups.ffe,),
            weblog_env=environment,
        )

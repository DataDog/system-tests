"""Unit coverage for the mock FFE agentless backend test fixture."""

from unittest.mock import MagicMock

import requests
import pytest

from utils import features, interfaces, scenarios
from utils._context._scenarios import endtoend as endtoend_scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.docker_fixtures._mock_ffe_agentless_backend import (
    CONFIG_PATH,
    EXPECTED_API_KEY,
    MockFFEAgentlessBackendServer,
)
from utils._context._scenarios.endtoend import FeatureFlaggingAgentlessEndToEndScenario
from utils._context.containers import ServerlessSidecarContainer
from utils.proxy.ports import ProxyPorts


@scenarios.test_the_test
@features.not_reported
def test_mock_ffe_agentless_backend_serves_fixture_and_tracks_metadata(worker_id: str) -> None:
    server = MockFFEAgentlessBackendServer(worker_id)
    try:
        response = requests.get(server.base_url + CONFIG_PATH, headers={"dd-api-key": EXPECTED_API_KEY}, timeout=5)
        response.raise_for_status()

        status = server.status()
        assert status["requests_total"] == 1
        assert status["last_auth_present"] is True
        assert status["last_path"] == CONFIG_PATH
        assert status["last_status_code"] == 200
    finally:
        server.close()


@scenarios.test_the_test
@features.not_reported
def test_mock_ffe_agentless_backend_host_gateway_mapping(monkeypatch: pytest.MonkeyPatch, worker_id: str) -> None:
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_HOST", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_HOST", raising=False)

    server = MockFFEAgentlessBackendServer(worker_id)
    try:
        env = {"DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": server.library_config_url}
        assert extra_hosts_for_environment(env) == HOST_GATEWAY_EXTRA_HOSTS
    finally:
        server.close()


@scenarios.test_the_test
@features.not_reported
def test_mock_ffe_agentless_backend_status_is_metadata_only(worker_id: str) -> None:
    server = MockFFEAgentlessBackendServer(worker_id)
    try:
        status = server.status()
        assert set(status) == {
            "requests_total",
            "in_flight",
            "max_in_flight",
            "last_path",
            "last_if_none_match",
            "last_auth_present",
            "last_status_code",
            "status_codes",
        }
        assert "ufc" not in status
        assert "payload" not in status
        assert "body" not in status
    finally:
        server.close()


@scenarios.test_the_test
@features.not_reported
def test_agentless_end_to_end_scenario_starts_backend_before_weblog(worker_id: str) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_E2E",
        doc="test",
        include_agent=False,
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )

    try:
        assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
        scenario._start_mock_backend(worker_id)  # noqa: SLF001 - focused lifecycle test

        environment = scenario.weblog_infra.library_container.environment
        assert "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE" not in environment
        assert "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT" not in environment
        base_url = environment["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL"]
        assert isinstance(base_url, str)
        assert base_url.endswith(CONFIG_PATH)
        assert scenario.weblog_infra.library_container.extra_hosts == HOST_GATEWAY_EXTRA_HOSTS

        status = scenario.mock_backend_status()
        assert status is not None
        assert status["requests_total"] == 0
    finally:
        scenario._stop_mock_backend()  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
@features.not_reported
def test_agentless_end_to_end_scenario_stops_without_tracer_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_NO_FLUSH",
        doc="test",
        flush_weblog_on_stop=False,
        include_agent=False,
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )
    flushed = False
    stopped = False

    def flush() -> None:
        nonlocal flushed
        flushed = True

    def stop() -> None:
        nonlocal stopped
        stopped = True

    monkeypatch.setattr(scenario, "_wait_interface", lambda *_: None)
    monkeypatch.setattr(scenario.weblog_infra.http_container, "flush", flush)
    monkeypatch.setattr(scenario.weblog_infra.http_container, "stop", stop)
    monkeypatch.setattr(interfaces.library, "check_deserialization_errors", lambda: None)

    scenario._wait_and_stop_containers(force_interface_timout_to_zero=True)  # noqa: SLF001

    assert stopped is True
    assert flushed is False


@scenarios.test_the_test
@features.not_reported
def test_agentless_sidecar_scenario_prefers_serverless_sidecar() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_SIDECAR",
        doc="test",
        include_agent=False,
        telemetry_route="sidecar",
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )

    environment = scenario.weblog_infra.library_container.environment
    assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
    assert scenario.proxy_container in scenario._containers  # noqa: SLF001 - focused topology test
    other_containers = scenario.weblog_infra._other_containers  # noqa: SLF001 - focused topology test
    assert any(isinstance(container, ServerlessSidecarContainer) for container in other_containers)
    assert environment["DD_FEATURE_FLAGS_TELEMETRY_TRANSPORT"] == "auto"
    assert environment["DD_TRACE_AGENT_URL"] == "http://ffe-serverless-sidecar:8126"
    assert environment["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] == "http://ffe-serverless-sidecar:4318/v1/metrics"
    assert environment["DD_PROXY_HTTPS"] == f"http://proxy:{ProxyPorts.ffe_direct}"


@scenarios.test_the_test
@features.not_reported
def test_agentless_end_to_end_scenario_closes_backend_when_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_STARTUP_FAILURE",
        doc="test",
        include_agent=False,
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )
    backend = MagicMock(spec=MockFFEAgentlessBackendServer)
    backend.reset.side_effect = RuntimeError("reset failed")

    def create_backend(_worker_id: str) -> MagicMock:
        return backend

    monkeypatch.setattr(endtoend_scenarios, "MockFFEAgentlessBackendServer", create_backend)

    with pytest.raises(RuntimeError, match="reset failed"):
        scenario.configure(MagicMock(spec=pytest.Config))

    backend.close.assert_called_once_with()
    assert scenario._mock_backend is None  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
@features.not_reported
def test_agentless_end_to_end_scenario_closes_backend_when_status_fails() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_STATUS_FAILURE",
        doc="test",
        include_agent=False,
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )
    backend = MagicMock(spec=MockFFEAgentlessBackendServer)
    backend.status.side_effect = RuntimeError("status failed")
    scenario._mock_backend = backend  # noqa: SLF001 - focused lifecycle test

    with pytest.raises(RuntimeError, match="status failed"):
        scenario._stop_mock_backend()  # noqa: SLF001 - focused lifecycle test

    backend.close.assert_called_once_with()
    assert scenario._mock_backend is None  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
@features.not_reported
def test_agentless_direct_scenario_uses_authenticated_fallback() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT",
        doc="test",
        include_agent=False,
        telemetry_route="direct",
        use_proxy_for_agent=False,
        use_proxy_for_weblog=False,
    )

    environment = scenario.weblog_infra.library_container.environment
    assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
    assert scenario.proxy_container in scenario._containers  # noqa: SLF001 - focused topology test
    assert not scenario.weblog_infra._other_containers  # noqa: SLF001 - focused topology test
    assert environment["DD_FEATURE_FLAGS_TELEMETRY_TRANSPORT"] == "auto"
    assert "DD_TRACE_AGENT_URL" not in environment
    assert environment["DD_API_KEY"] == EXPECTED_API_KEY
    assert environment["DD_PROXY_HTTPS"] == f"http://proxy:{ProxyPorts.ffe_direct}"
    assert environment["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] == f"http://proxy:{ProxyPorts.ffe_direct}/v1/metrics"
    assert environment["OTEL_EXPORTER_OTLP_METRICS_HEADERS"] == (f"dd-api-key={EXPECTED_API_KEY},dd-protocol=otlp")

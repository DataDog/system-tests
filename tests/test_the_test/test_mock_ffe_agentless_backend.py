"""Unit coverage for the mock FFE agentless backend test fixture."""

import requests
import pytest

from utils import features, scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.docker_fixtures._mock_ffe_agentless_backend import (
    CONFIG_PATH,
    EXPECTED_API_KEY,
    MockFFEAgentlessBackendServer,
)
from utils._context._scenarios.endtoend import FeatureFlaggingAgentlessEndToEndScenario


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

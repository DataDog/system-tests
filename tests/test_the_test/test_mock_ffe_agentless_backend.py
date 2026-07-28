"""Unit coverage for the mock FFE agentless backend test fixture."""

from pathlib import Path
from unittest.mock import MagicMock

import requests
from utils import pytest

from utils import scenarios
from utils._context._scenarios import agentless_endtoend as agentless_endtoend_scenarios
from utils._context._scenarios import endtoend as endtoend_scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.mocked_backend.ffe import (
    CONFIG_PATH,
    CONFIG_QUERY,
    EXPECTED_DD_ENV,
    MockFFEAgentlessBackendServer,
    UFC_RESPONSE_TYPE,
)
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingAgentlessEndToEndScenario


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_serves_fixture_and_tracks_metadata(worker_id: str) -> None:
    server = MockFFEAgentlessBackendServer(worker_id, port=0)
    try:
        for invalid_query in ("", "?dd_env=", "?dd_env=wrong", f"?dd_env={EXPECTED_DD_ENV}&dd_env=wrong"):
            response = requests.get(
                server.base_url + CONFIG_PATH + invalid_query,
                timeout=5,
            )
            assert response.status_code == 404

        response = requests.get(
            f"{server.base_url}{CONFIG_PATH}?{CONFIG_QUERY}",
            timeout=5,
        )
        response.raise_for_status()
        assert response.headers["Content-Length"] == str(len(response.content))

        payload = response.json()
        assert payload["data"]["type"] == UFC_RESPONSE_TYPE
        assert payload["data"]["attributes"]["environment"]["name"] == "Test"
        assert "new-user-onboarding" in payload["data"]["attributes"]["flags"]

        status = server.status()
        assert status["requests_total"] == 1
        assert status["last_auth_present"] is False
        assert status["last_path"] == CONFIG_PATH
        assert status["last_status_code"] == 200

        server.set_response("unauthorized")
        response = requests.get(
            f"{server.base_url}{CONFIG_PATH}?{CONFIG_QUERY}",
            timeout=5,
        )
        assert response.status_code == 401

        status = server.status()
        assert status["requests_total"] == 2
        assert status["last_auth_present"] is False
        assert status["last_status_code"] == 401
    finally:
        server.close()


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_host_gateway_mapping(monkeypatch: pytest.MonkeyPatch, worker_id: str) -> None:
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_HOST", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_HOST", raising=False)

    server = MockFFEAgentlessBackendServer(worker_id, port=0)
    try:
        assert server.library_config_url.endswith(f"{CONFIG_PATH}?{CONFIG_QUERY}")
        env = {"DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": server.library_config_url}
        assert extra_hosts_for_environment(env) == HOST_GATEWAY_EXTRA_HOSTS
    finally:
        server.close()


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_status_is_metadata_only(worker_id: str) -> None:
    server = MockFFEAgentlessBackendServer(worker_id, port=0)
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
def test_agentless_end_to_end_scenario_starts_backend_before_weblog() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_E2E", doc="test")

    try:
        assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
        scenario._start_mock_backend()  # noqa: SLF001 - focused lifecycle test

        environment = scenario.weblog_infra.library_container.environment
        assert "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE" not in environment
        assert "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT" not in environment
        base_url = environment["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL"]
        assert isinstance(base_url, str)
        assert base_url.endswith(f"{CONFIG_PATH}?{CONFIG_QUERY}")
        assert scenario.weblog_infra.library_container.extra_hosts == HOST_GATEWAY_EXTRA_HOSTS

        status = scenario.mock_backend_status()
        assert status is not None
        assert status["requests_total"] == 0
    finally:
        scenario._stop_mock_backend()  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_closes_backend_when_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_STARTUP_FAILURE", doc="test")
    backend = MagicMock(spec=MockFFEAgentlessBackendServer)
    backend.reset.side_effect = RuntimeError("reset failed")

    def create_backend() -> MagicMock:
        return backend

    monkeypatch.setattr(agentless_endtoend_scenarios, "MockFFEAgentlessBackendServer", create_backend)

    with pytest.raises(RuntimeError, match="reset failed"):
        scenario.configure(MagicMock(spec=pytest.Config))

    backend.close.assert_called_once_with()
    assert scenario._mock_backend is None  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_closes_backend_when_status_fails() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_STATUS_FAILURE", doc="test")
    backend = MagicMock(spec=MockFFEAgentlessBackendServer)
    backend.status.side_effect = RuntimeError("status failed")
    scenario._mock_backend = backend  # noqa: SLF001 - focused lifecycle test

    with pytest.raises(RuntimeError, match="status failed"):
        scenario._stop_mock_backend()  # noqa: SLF001 - focused lifecycle test

    backend.close.assert_called_once_with()
    assert scenario._mock_backend is None  # noqa: SLF001 - focused lifecycle test


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_persists_backend_status_for_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    recording_scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_REPLAY", doc="test")
    recording_scenario._mock_backend_status_path.parent.mkdir()  # noqa: SLF001 - focused lifecycle test

    expected_status = {
        "requests_total": 1,
        "in_flight": 0,
        "max_in_flight": 1,
        "last_path": CONFIG_PATH,
        "last_if_none_match": None,
        "last_auth_present": True,
        "last_status_code": 200,
        "status_codes": [200],
    }
    backend = MagicMock(spec=MockFFEAgentlessBackendServer)
    backend.status.return_value = expected_status
    recording_scenario._mock_backend = backend  # noqa: SLF001 - focused lifecycle test

    recording_scenario._stop_mock_backend()  # noqa: SLF001 - focused lifecycle test

    replay_scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_REPLAY", doc="test")
    replay_scenario.replay = True
    base_configure = MagicMock()
    monkeypatch.setattr(endtoend_scenarios.DdTraceEndToEndScenario, "configure", base_configure)
    config = MagicMock(spec=pytest.Config)
    replay_scenario.configure(config)

    backend.close.assert_called_once_with()
    base_configure.assert_called_once_with(config)
    assert replay_scenario.mock_backend_status() == expected_status

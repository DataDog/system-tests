"""Unit coverage for the mock FFE agentless backend test fixture."""

from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import requests
import pytest

from utils import features, scenarios
from utils._context.containers import ServerlessInitContainer
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
from utils.proxy.ports import ProxyPorts


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


@pytest.mark.parametrize("exposure_egress", ["direct", "sidecar"])
@scenarios.test_the_test
@features.not_reported
def test_agentless_exposure_scenario_has_no_agent_and_two_capture_routes(
    exposure_egress: Literal["direct", "sidecar"],
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_EXPOSURES",
        doc="test",
        exposure_egress=exposure_egress,
    )

    environment = scenario.weblog_infra.library_container.environment
    serverless_init_containers = tuple(
        container
        for container in scenario.weblog_infra.get_containers()
        if isinstance(container, ServerlessInitContainer)
    )
    assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
    assert scenario.proxy_container in scenario._containers  # noqa: SLF001 - focused topology test
    assert scenario.get_libraries() is None
    assert environment["DD_SITE"] == "mock-intake.invalid"
    assert environment["DD_PROXY_HTTPS"] == f"http://proxy:{ProxyPorts.datadog_direct}"
    assert environment["HTTPS_PROXY"] == f"http://proxy:{ProxyPorts.datadog_direct}"

    if exposure_egress == "direct":
        for name in ("DD_AGENT_HOST", "DD_DOGSTATSD_HOST", "DD_TRACE_AGENT_PORT", "DD_TRACE_AGENT_URL"):
            assert name not in environment
        assert not serverless_init_containers
        return

    serverless_init = scenario.serverless_init_container
    assert serverless_init_containers == (serverless_init,)
    assert isinstance(serverless_init, ServerlessInitContainer)
    assert environment["DD_TRACE_AGENT_PORT"] == str(serverless_init.apm_receiver_port)
    assert environment["DD_TRACE_AGENT_URL"] == f"http://ffe-serverless-init:{serverless_init.apm_receiver_port}"
    assert serverless_init.healthcheck is not None
    assert serverless_init.environment["DD_SITE"] == "mock-intake.invalid"
    assert serverless_init.environment["DD_PROXY_HTTPS"] == f"http://proxy:{ProxyPorts.datadog_sidecar}"
    assert serverless_init.environment["DD_PROXY_HTTP"] == f"http://proxy:{ProxyPorts.datadog_sidecar}"


@pytest.mark.parametrize(
    ("library", "weblog_variant", "expected_result"),
    [
        ("java", "spring-boot", "configured"),
        ("java", "spring-boot-3-native", "unchanged"),
        ("java", "spring-boot-payara", "unchanged"),
        ("java", "play", "unchanged"),
        ("nodejs", "express4", "unchanged"),
    ],
)
@scenarios.test_the_test
def test_agentless_exposure_proxy_ca_wrapper_only_replaces_standard_spring_boot_startup(
    library: str,
    weblog_variant: str,
    expected_result: Literal["configured", "unchanged"],
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_EXPOSURES",
        doc="test",
        exposure_egress="direct",
    )
    library_container = scenario.weblog_infra.http_container
    library_container.image.labels["system-tests-library"] = library
    library_container.weblog_variant = weblog_variant

    scenario._configure_java_proxy_ca()  # noqa: SLF001 - focused startup wrapper test

    wrapper_path = "./utils/build/docker/java/app-with-proxy-ca.sh"
    certificate_path = "./utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer"
    expected_wrapper = expected_result == "configured"
    assert ("JAVA_OPTS" in library_container.environment) is expected_wrapper
    assert (wrapper_path in library_container.volumes) is expected_wrapper
    assert (certificate_path in library_container.volumes) is expected_wrapper


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

"""Unit coverage for the mock FFE agentless backend test fixture."""

from collections.abc import Callable
import hashlib
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock

import requests
from utils import pytest

from utils import features, interfaces, scenarios
from utils._context.containers import MockedBackendContainer, ProxyContainer, ServerlessInitContainer
from utils._context._scenarios import agentless_endtoend as agentless_endtoend_scenarios
from utils._context._scenarios._core import endtoend as endtoend_scenarios
from utils.docker_fixtures._core import HOST_GATEWAY_EXTRA_HOSTS, extra_hosts_for_environment
from utils.mocked_backend import MockedBackendServer

from utils.mocked_backend.ffe import (
    CONFIG_PATH,
    CONFIG_QUERY,
    EXPECTED_DD_ENV,
    UFC_RESPONSE_TYPE,
)
from utils._context._scenarios.agentless_endtoend import (
    DIRECT_EVP_AGENT_VARIABLES,
    DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
    DIRECT_EVP_CA_BUNDLE_SOURCE,
    DIRECT_EVP_CAPTURE_SETTLE_SECONDS,
    DIRECT_EVP_CAPTURE_WAIT_SECONDS,
    JAVA_TRUSTSTORE_CONTAINER_PATH,
    JAVA_TRUSTSTORE_SOURCE,
    FeatureFlaggingAgentlessEndToEndScenario,
)

from .utils import extra_hosts_at_start


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_serves_fixture_and_tracks_metadata() -> None:
    server = MockedBackendServer()
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

        status = server.client.ffe_get_status()
        assert status["requests_total"] == 1
        assert status["observed_dd_api_key"] is None
        assert status["last_path"] == CONFIG_PATH
        assert status["last_status_code"] == 200

        server.client.ffe_set_response("unauthorized")
        response = requests.get(
            f"{server.base_url}{CONFIG_PATH}?{CONFIG_QUERY}",
            timeout=5,
        )
        assert response.status_code == 401

        status = server.client.ffe_get_status()
        assert status["requests_total"] == 2
        assert status["observed_dd_api_key"] is None
        assert status["last_status_code"] == 401
    finally:
        server.close()


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_host_gateway_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_HOST", raising=False)
    monkeypatch.delenv("SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_HOST", raising=False)

    server = MockedBackendServer()
    try:
        assert server.ffe_library_config_url.endswith(f"{CONFIG_PATH}?{CONFIG_QUERY}")
        env = {"DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL": server.ffe_library_config_url}
        assert extra_hosts_for_environment(env) == HOST_GATEWAY_EXTRA_HOSTS
    finally:
        server.close()


@scenarios.test_the_test
def test_mock_ffe_agentless_backend_status_is_metadata_only() -> None:
    server = MockedBackendServer()
    try:
        status = server.client.ffe_get_status()
        assert set(status) == {
            "requests_total",
            "in_flight",
            "max_in_flight",
            "last_path",
            "last_if_none_match",
            "observed_dd_api_key",
            "last_status_code",
            "status_codes",
        }
        assert "ufc" not in status
        assert "payload" not in status
        assert "body" not in status
    finally:
        server.close()


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_points_weblog_to_mocked_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_E2E", doc="test")

    assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
    assert scenario.mocked_backend_container in scenario._containers  # noqa: SLF001 - focused topology test

    library_container = scenario.weblog_infra.library_container
    environment = library_container.environment
    assert "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED" not in environment
    assert "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE" not in environment
    assert "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT" not in environment
    assert environment["DD_API_KEY"] == scenario.weblog_api_key
    assert environment["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE_AGENTLESS_BASE_URL"] == (
        f"https://mocked-backend.invalid{CONFIG_PATH}?{CONFIG_QUERY}"
    )
    # it serves HTTPS, with a certificate signed by the CA of the mounted bundle
    assert environment["NODE_EXTRA_CA_CERTS"] == DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH
    assert library_container.volumes[DIRECT_EVP_CA_BUNDLE_SOURCE] == {
        "bind": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
        "mode": "ro",
    }
    # the JVM gets the CA in its own trust store
    assert library_container.volumes[JAVA_TRUSTSTORE_SOURCE] == {"bind": JAVA_TRUSTSTORE_CONTAINER_PATH, "mode": "ro"}
    assert f"-Djavax.net.ssl.trustStore={JAVA_TRUSTSTORE_CONTAINER_PATH}" in str(environment["JDK_JAVA_OPTIONS"])
    # reached by its name on the scenario network: no mapping to the docker host
    assert extra_hosts_at_start(monkeypatch, library_container) is None


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_reads_live_backend_status(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_LIVE_STATUS", doc="test")
    container = MagicMock(spec=MockedBackendContainer)
    container.client.ffe_get_status.return_value = {"requests_total": 0}
    monkeypatch.setattr(scenario, "mocked_backend_container", container)

    assert scenario.mock_backend_status() == {"requests_total": 0}


@scenarios.test_the_test
@features.not_reported
def test_default_agentless_scenario_leaves_source_selection_implicit() -> None:
    scenario = scenarios.feature_flagging_and_experimentation_agentless
    environment = scenario.weblog_infra.library_container.environment

    # The legacy enable switch selects Remote Config when the source is unset. The
    # default-agentless scenario must model a new customer without either input.
    assert "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED" not in environment
    assert "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE" not in environment
    assert "DD_FEATURE_FLAGS_ENABLED" not in environment
    assert environment["DD_REMOTE_CONFIGURATION_ENABLED"] == "false"


@pytest.mark.parametrize("exposure_egress", ["direct", "sidecar"])
@scenarios.test_the_test
@features.not_reported
def test_agentless_exposure_scenario_sends_events_to_the_mocked_backend(
    exposure_egress: Literal["direct", "sidecar"],
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_EXPOSURES",
        doc="test",
        exposure_egress=exposure_egress,
    )

    environment = scenario.weblog_infra.library_container.environment
    assert scenario.agent_container not in scenario._containers  # noqa: SLF001 - focused topology test
    # the intake hostnames derived from DD_SITE are network aliases of the mocked backend: no proxy in between
    assert not any(isinstance(container, ProxyContainer) for container in scenario._containers)  # noqa: SLF001
    assert scenario.mocked_backend_container.tls
    assert scenario.get_libraries() is None
    assert environment["DD_SITE"] == "mocked-backend.invalid"
    assert "DD_PROXY_HTTPS" not in environment
    assert "HTTPS_PROXY" not in environment
    assert environment["DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"] == "true"
    assert environment["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE"] == "agentless"

    if exposure_egress == "direct":
        assert environment["SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED"] == "true"
        assert scenario.weblog_infra.library_container.volumes[DIRECT_EVP_CA_BUNDLE_SOURCE] == {
            "bind": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
            "mode": "ro",
        }
        for name in DIRECT_EVP_AGENT_VARIABLES:
            assert name not in environment
        assert scenario.serverless_init_container is None
        return

    serverless_init = scenario.serverless_init_container
    assert isinstance(serverless_init, ServerlessInitContainer)
    assert serverless_init in scenario._containers  # noqa: SLF001 - focused topology test
    assert serverless_init.image.original_name == "datadog/serverless-init:1.10.4"
    assert environment["DD_TRACE_AGENT_PORT"] == str(serverless_init.apm_receiver_port)
    assert environment["DD_TRACE_AGENT_URL"] == f"http://ffe-serverless-init:{serverless_init.apm_receiver_port}"
    assert serverless_init.healthcheck is not None
    assert serverless_init.environment["DD_SITE"] == "mocked-backend.invalid"
    assert serverless_init.environment["DD_API_KEY"] == scenario.sidecar_api_key
    assert "DD_PROXY_HTTPS" not in serverless_init.environment
    assert serverless_init.environment["DD_DD_URL"] == "https://mocked-backend.invalid"
    assert serverless_init.environment["DD_APM_DD_URL"] == "https://mocked-backend.invalid"


@scenarios.test_the_test
@features.not_reported
def test_agentless_evp_capture_registry_allows_unregistered_and_rejects_unknown_paths() -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT_CAPTURE_REGISTRY",
        doc="test",
        exposure_egress="direct",
    )

    # Manifest-deactivated items are still collected without --skip-empty-scenario, but their
    # setup methods do not run and therefore register no capture expectations.
    scenario._wait_for_expected_evp_captures(is_empty_test_run=False)  # noqa: SLF001

    # Empty selections and replay runs have no live setup phase and therefore need no registration.
    scenario._wait_for_expected_evp_captures(is_empty_test_run=True)  # noqa: SLF001
    scenario.replay = True
    scenario._wait_for_expected_evp_captures(is_empty_test_run=False)  # noqa: SLF001

    with pytest.raises(ValueError, match="Unsupported Feature Flags EVP path"):
        scenario.register_expected_evp_capture("/api/v2/not-a-signal")


@pytest.mark.parametrize(
    "captured_targeting_key",
    [
        "shutdown-user",
        f"sha256_{hashlib.sha256(b'shutdown-user').hexdigest()}",
    ],
)
@scenarios.test_the_test
@features.not_reported
def test_direct_evp_shutdown_matcher_supports_flagevaluation_targeting_keys(
    captured_targeting_key: str,
) -> None:
    evaluation = agentless_endtoend_scenarios.DirectEVPShutdownEvaluation(
        signal_path="/api/v2/flagevaluation",
        request_path="/ffe",
        body={},
        flag_key="shutdown-flag",
        subject_id="shutdown-user",
    )
    capture = {
        "path": "/api/v2/flagevaluation",
        "request": {
            "content": {
                "flagEvaluations": [
                    {
                        "flag": {"key": "shutdown-flag"},
                        "targeting_key": captured_targeting_key,
                    }
                ]
            }
        },
    }

    assert FeatureFlaggingAgentlessEndToEndScenario._capture_has_shutdown_evaluation(capture, evaluation)  # noqa: SLF001


@scenarios.test_the_test
@features.not_reported
def test_agentless_evp_capture_registry_waits_for_each_path_before_settling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT_CAPTURE_WAIT",
        doc="test",
        exposure_egress="direct",
    )
    expected_paths = ("/api/v2/exposures", "/api/v2/flagevaluation")
    for path in expected_paths:
        scenario.register_expected_evp_capture(path)

    captures = iter(
        {"path": path, "request": {"headers": [("DD-API-KEY", scenario.weblog_api_key)]}} for path in expected_paths
    )
    wait_timeouts: list[int] = []

    def wait_for(matcher: Callable[[dict[str, Any]], bool], *, timeout: int) -> bool:
        wait_timeouts.append(timeout)
        return matcher(next(captures))

    wait = MagicMock()
    monkeypatch.setattr(interfaces.mocked_backend, "wait_for", wait_for)
    monkeypatch.setattr(interfaces.mocked_backend, "wait", wait)

    scenario._wait_for_expected_evp_captures(is_empty_test_run=False)  # noqa: SLF001

    assert wait_timeouts == [DIRECT_EVP_CAPTURE_WAIT_SECONDS, DIRECT_EVP_CAPTURE_WAIT_SECONDS]
    wait.assert_called_once_with(DIRECT_EVP_CAPTURE_SETTLE_SECONDS)


@scenarios.test_the_test
@features.not_reported
def test_sidecar_stops_right_after_the_weblog(monkeypatch: pytest.MonkeyPatch) -> None:
    """serverless-init must flush to the mocked backend before it is stopped by the base scenario"""
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_SIDECAR_STOP_ORDER",
        doc="test",
        exposure_egress="sidecar",
    )
    lifecycle: list[str] = []

    def stop_weblog(self: object, *, is_empty_test_run: bool) -> None:
        assert self is scenario
        assert is_empty_test_run is False
        lifecycle.append("weblog")

    monkeypatch.setattr(endtoend_scenarios.DdTraceEndToEndScenario, "_stop_weblog", stop_weblog)
    assert scenario.serverless_init_container is not None
    monkeypatch.setattr(scenario.serverless_init_container, "stop", lambda: lifecycle.append("serverless-init"))

    scenario._stop_weblog(is_empty_test_run=False)  # noqa: SLF001

    assert lifecycle == ["weblog", "serverless-init"]


@scenarios.test_the_test
@features.not_reported
def test_agentless_evp_capture_wait_happens_before_container_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT_CAPTURE_ORDER",
        doc="test",
        exposure_egress="direct",
    )
    lifecycle: list[str] = []

    def wait_for_captures(*, is_empty_test_run: bool) -> None:
        assert is_empty_test_run is False
        lifecycle.append("capture")

    def stop_containers(self: object, *, is_empty_test_run: bool) -> None:
        assert self is scenario
        assert is_empty_test_run is False
        lifecycle.append("stop")

    monkeypatch.setattr(scenario, "_wait_for_expected_evp_captures", wait_for_captures)
    monkeypatch.setattr(endtoend_scenarios.DdTraceEndToEndScenario, "_wait_and_stop_containers", stop_containers)

    scenario._wait_and_stop_containers(is_empty_test_run=False)  # noqa: SLF001

    assert lifecycle == ["capture", "stop"]


@scenarios.test_the_test
@features.not_reported
@pytest.mark.parametrize("run_selection", ["manifest-deactivated", "empty"])
def test_direct_evp_replay_skips_missing_runtime_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run_selection: Literal["manifest-deactivated", "empty"],
) -> None:
    monkeypatch.chdir(tmp_path)
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT_EMPTY_REPLAY",
        doc="test",
        exposure_egress="direct",
    )
    Path(scenario.host_log_folder).mkdir()
    scenario.replay = True
    is_empty_test_run = run_selection == "empty"

    stop_containers = MagicMock()
    monkeypatch.setattr(endtoend_scenarios.DdTraceEndToEndScenario, "_wait_and_stop_containers", stop_containers)

    scenario._wait_and_stop_containers(is_empty_test_run=is_empty_test_run)  # noqa: SLF001

    assert scenario._last_direct_evp_runtime_evidence is None  # noqa: SLF001
    stop_containers.assert_called_once_with(is_empty_test_run=is_empty_test_run)


@scenarios.test_the_test
@features.not_reported
def test_direct_evp_shutdown_probe_uses_sigterm_without_explicit_flush(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_AGENTLESS_DIRECT_SHUTDOWN",
        doc="test",
        exposure_egress="direct",
    )
    Path(scenario.host_log_folder).mkdir()
    scenario.register_shutdown_evp_evaluation(
        signal_path="/api/v2/exposures",
        request_path="/ffe",
        body={
            "flag": "empty-targeting-key-flag",
            "variationType": "STRING",
            "defaultValue": "default",
            "targetingKey": "shutdown-user",
            "attributes": {},
        },
        flag_key="empty-targeting-key-flag",
        subject_id="shutdown-user",
    )

    lifecycle: list[str] = []
    monkeypatch.setattr(
        scenario,
        "_capture_direct_evp_runtime_evidence",
        lambda: lifecycle.append("runtime-evidence"),
    )

    response = MagicMock()
    response.status_code = 200

    def evaluate(*_args: object, **_kwargs: object) -> MagicMock:
        lifecycle.append("evaluate")
        return response

    monkeypatch.setattr(agentless_endtoend_scenarios.weblog, "post", evaluate)

    priming_capture = {
        "path": "/api/v2/exposures",
        "log_filename": "direct-0000.json",
        "request": {
            "timestamp_start": "2099-09-09T11:59:59+00:00",
            "headers": [("DD-API-KEY", scenario.weblog_api_key)],
            "content": {
                "exposures": [
                    {
                        "flag": {"key": "empty-targeting-key-flag"},
                        "subject": {"id": "shutdown-user-flush-window-prime"},
                    }
                ]
            },
        },
    }
    capture = {
        "path": "/api/v2/exposures",
        "log_filename": "direct-0001.json",
        "request": {
            "timestamp_start": "2099-09-09T12:00:01+00:00",
            "headers": [("DD-API-KEY", scenario.weblog_api_key)],
            "content": {
                "exposures": [
                    {
                        "flag": {"key": "empty-targeting-key-flag"},
                        "subject": {"id": "shutdown-user"},
                    }
                ]
            },
        },
    }
    snapshots = iter(
        (
            [priming_capture],
            [priming_capture],
            [priming_capture],
            [priming_capture],
            [priming_capture, capture],
        )
    )

    def get_data(*, with_api_key: str) -> list[dict[str, Any]]:
        assert with_api_key == scenario.weblog_api_key
        lifecycle.append("capture-snapshot")
        return next(snapshots)

    def wait_for(matcher: Callable[[dict[str, Any]], bool], *, timeout: int) -> bool:
        lifecycle.append("capture-wait")
        assert timeout == DIRECT_EVP_CAPTURE_WAIT_SECONDS
        return any(matcher(candidate) for candidate in (priming_capture, capture))

    settle = MagicMock(side_effect=lambda _: lifecycle.append("settle"))
    monkeypatch.setattr(interfaces.mocked_backend, "get_data", get_data)
    monkeypatch.setattr(interfaces.mocked_backend, "wait_for", wait_for)
    monkeypatch.setattr(interfaces.mocked_backend, "wait", settle)
    # the priming capture is polled from the recorded files, without the watchdog latency
    monkeypatch.setattr(interfaces.mocked_backend, "ingest_all_files", lambda: lifecycle.append("capture-ingest"))

    runtime_container = MagicMock()
    runtime_container.status = "exited"
    runtime_container.attrs = {
        "State": {
            "Error": "",
            "ExitCode": 0,
            "FinishedAt": "2099-09-09T12:00:02Z",
            "OOMKilled": False,
            "Running": False,
        }
    }
    runtime_container.logs.side_effect = lambda *, stdout, stderr: (
        b'{"event":"system_tests.ffe.shutdown.server_closed","timestamp":"2099-09-09T12:00:00Z"}\n'
        if stdout and not stderr
        else b""
    )
    scenario.weblog_infra.library_container._container = runtime_container  # noqa: SLF001
    stop = MagicMock(side_effect=lambda **_: lifecycle.append("docker-stop"))
    monkeypatch.setattr(scenario.weblog_infra, "stop", stop)

    scenario._stop_weblog(is_empty_test_run=False)  # noqa: SLF001

    stop.assert_called_once_with(flush=False, stop_timeout=10)
    settle.assert_called_once_with(DIRECT_EVP_CAPTURE_SETTLE_SECONDS)
    assert lifecycle == [
        "runtime-evidence",
        "evaluate",
        "capture-ingest",
        "capture-snapshot",
        "capture-snapshot",
        "capture-snapshot",
        "evaluate",
        "capture-snapshot",
        "docker-stop",
        "capture-wait",
        "settle",
        "capture-snapshot",
    ]
    evidence = scenario.direct_evp_shutdown_evidence()
    assert evidence["explicit_flush"] is False
    assert evidence["captures_before_evaluation"] == 0
    assert evidence["captures_before_stop"] == 0
    assert evidence["captures_after_settle"] == 1
    assert evidence["flush_window_primed"] is True
    assert evidence["priming_subject_id"] == "shutdown-user-flush-window-prime"
    assert evidence["priming_capture_files"] == ["direct-0000.json"]
    assert evidence["priming_capture_request_started_at"] == ["2099-09-09T11:59:59+00:00"]
    assert evidence["priming_evaluation_status_code"] == 200
    assert evidence["shutdown_marker_errors"] == []
    assert len(evidence["shutdown_markers"]) == 1
    assert evidence["stopped_container"]["exit_code"] == 0


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_stops_backend_when_status_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_STATUS_FAILURE", doc="test")
    container = MagicMock(spec=MockedBackendContainer)
    container.client.ffe_get_status.side_effect = RuntimeError("status failed")
    monkeypatch.setattr(scenario, "mocked_backend_container", container)

    with pytest.raises(RuntimeError, match="status failed"):
        scenario._stop_mocked_backend()  # noqa: SLF001 - focused lifecycle test

    container.stop.assert_called_once_with()


@scenarios.test_the_test
def test_agentless_end_to_end_scenario_persists_backend_status_for_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    recording_scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_REPLAY", doc="test")

    expected_status = {
        "requests_total": 1,
        "in_flight": 0,
        "max_in_flight": 1,
        "last_path": CONFIG_PATH,
        "last_if_none_match": None,
        "observed_dd_api_key": recording_scenario.dd_api_key,
        "last_status_code": 200,
        "status_codes": [200],
    }
    container = MagicMock(spec=MockedBackendContainer)
    container.client.ffe_get_status.return_value = expected_status
    monkeypatch.setattr(recording_scenario, "mocked_backend_container", container)

    recording_scenario._stop_mocked_backend()  # noqa: SLF001 - focused lifecycle test

    container.stop.assert_called_once_with()
    assert recording_scenario.mock_backend_status() == expected_status

    replay_scenario = FeatureFlaggingAgentlessEndToEndScenario("MOCK_FFE_AGENTLESS_REPLAY", doc="test")
    replay_scenario.replay = True
    base_configure = MagicMock()
    monkeypatch.setattr(endtoend_scenarios.DdTraceEndToEndScenario, "configure", base_configure)
    config = MagicMock(spec=pytest.Config)
    replay_scenario.configure(config)

    base_configure.assert_called_once_with(config)
    assert replay_scenario.mock_backend_status() == expected_status

"""Unit coverage for the shared Feature Flags EVP wire contract."""

from copy import deepcopy
from typing import Any, Literal

import pytest

from tests.ffe.utils.evp import (
    EVP_ORIGINS,
    FeatureFlaggingEVPEgress,
    assert_agentless_evp_intake_request,
    assert_agentless_evp_topology,
    assert_direct_evp_runtime_evidence,
    assert_direct_evp_shutdown_evidence,
    assert_no_evp_proxy_requests,
    expected_evp_origin,
)
from utils import context, features, interfaces, scenarios
from utils._context.component_version import ComponentVersion, Version
from utils._context._scenarios.agentless_endtoend import (
    DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
    DIRECT_EVP_CA_BUNDLE_SOURCE,
    FeatureFlaggingAgentlessEndToEndScenario,
)


def _direct_runtime_evidence(library_name: str = "nodejs") -> dict[str, Any]:
    executable = {
        "dotnet": "dotnet",
        "golang": "weblog",
        "java": "java",
        "nodejs": "node",
        "python": "python",
        "ruby": "ruby",
    }[library_name]
    network_name = "system-tests-network"
    return {
        "captured_at": "2026-09-09T12:00:00+00:00",
        "network": {
            "id": "network-id",
            "name": network_name,
            "container_ids": ["proxy-id", "weblog-id"],
            "container_names": ["system-tests-proxy", "system-tests-weblog"],
        },
        "containers": [
            {
                "id": "proxy-id",
                "name": "system-tests-proxy",
                "image": "system-tests/proxy",
                "image_id": "sha256:proxy",
                "library": None,
                "weblog_variant": None,
                "status": "running",
                "running": True,
                "state_pid": 101,
                "pid1_command": "python3 -m utils.proxy.core",
                "pid1_error": None,
                "processes": [{"pid": "101", "ppid": "0", "command": "python3 -m utils.proxy.core"}],
                "top_error": None,
                "networks": [network_name],
                "mounts": [],
            },
            {
                "id": "weblog-id",
                "name": "system-tests-weblog",
                "image": "system-tests/weblog",
                "image_id": "sha256:weblog",
                "library": library_name,
                "weblog_variant": "express4",
                "status": "running",
                "running": True,
                "state_pid": 202,
                "pid1_command": f"{executable} app",
                "pid1_error": None,
                "processes": [{"pid": "202", "ppid": "0", "command": f"{executable} app"}],
                "top_error": None,
                "networks": [network_name],
                "mounts": [
                    {
                        "destination": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
                        "read_write": False,
                        "source": "/system-tests/utils/build/docker/agent/ca-certificates.crt",
                        "type": "bind",
                    }
                ],
            },
        ],
        "weblog_environment": {
            "agent_variables_present": [],
            "api_key_matches_expected": True,
            "api_key_present": True,
            "configuration_source": "agentless",
            "custom_configuration_url_present": True,
            "provider_enabled": "true",
            "shutdown_flush_enabled": "true",
            "site": "mock-intake.invalid",
            "tls_ca_bundle": None,
        },
    }


def _direct_shutdown_evidence() -> dict[str, Any]:
    return {
        "capture_files": ["direct-0001.json"],
        "capture_observed_after_stop": True,
        "capture_request_started_at": ["2026-09-09T12:00:01.200000+00:00"],
        "captures_after_settle": 1,
        "captures_before_evaluation": 0,
        "captures_before_stop": 0,
        "evaluation_finished_at": "2026-09-09T12:00:01+00:00",
        "evaluation_started_at": "2026-09-09T12:00:00+00:00",
        "evaluation_status_code": 200,
        "explicit_flush": False,
        "flag_key": "empty-targeting-key-flag",
        "flush_window_primed": True,
        "priming_capture_files": ["direct-prime-0001.json"],
        "priming_capture_request_started_at": ["2026-09-09T11:59:59.800000+00:00"],
        "priming_evaluation_finished_at": "2026-09-09T11:59:59.900000+00:00",
        "priming_evaluation_started_at": "2026-09-09T11:59:59.700000+00:00",
        "priming_evaluation_status_code": 200,
        "priming_subject_id": "exposure-shutdown-user-flush-window-prime",
        "shutdown_bound_seconds": 12,
        "shutdown_duration_seconds": 0.5,
        "shutdown_marker_errors": [],
        "shutdown_markers": [
            {
                "event": "system_tests.ffe.shutdown.server_closed",
                "stream": "stdout",
                "timestamp": "2026-09-09T12:00:01.150000+00:00",
            }
        ],
        "signal_path": "/api/v2/exposures",
        "stop_error": None,
        "stop_started_at": "2026-09-09T12:00:01.100000+00:00",
        "stop_timeout_seconds": 10,
        "stopped_at": "2026-09-09T12:00:01.600000+00:00",
        "stopped_container": {
            "error": "",
            "exit_code": 0,
            "finished_at": "2026-09-09T12:00:01.500000000Z",
            "oom_killed": False,
            "running": False,
            "status": "exited",
        },
        "subject_id": "exposure-shutdown-user",
    }


def _direct_capture(*, path: str = "/api/v2/exposures", headers: list[list[str]] | None = None) -> dict[str, Any]:
    return {
        "method": "POST",
        "path": path,
        "host": "event-platform-intake.mock-intake.invalid",
        "port": 443,
        "request": {
            "headers": headers
            or [
                ["DD-API-KEY", "system-tests-mock-api-key"],
                ["DD-EVP-ORIGIN", "dd-trace-js"],
                ["DD-EVP-ORIGIN-VERSION", "7.0.0-pre"],
                ["Content-Type", "application/json; charset=utf-8"],
            ],
            "content": {"exposures": []},
        },
        "response": {"status_code": 202, "content": "Ok"},
    }


@pytest.mark.parametrize(("library_name", "origin"), sorted(EVP_ORIGINS.items()))
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_evp_origin_contract(library_name: str, origin: str) -> None:
    assert expected_evp_origin(library_name) == origin


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_wire_contract_accepts_exact_identity() -> None:
    assert_agentless_evp_intake_request(
        _direct_capture(),
        route="direct",
        path="/api/v2/exposures",
        expected_api_key="system-tests-mock-api-key",
        library_name="nodejs",
        library_version="7.0.0-pre",
    )


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_wire_contract_accepts_canonical_go_version() -> None:
    capture = _direct_capture(
        headers=[
            ["DD-API-KEY", "system-tests-mock-api-key"],
            ["DD-EVP-ORIGIN", "dd-trace-go"],
            ["DD-EVP-ORIGIN-VERSION", "v2.11.0-dev.1"],
            ["Content-Type", "application/json"],
        ]
    )

    assert_agentless_evp_intake_request(
        capture,
        route="direct",
        path="/api/v2/exposures",
        expected_api_key="system-tests-mock-api-key",
        library_name="golang",
        library_version="2.11.0-dev.1",
    )

    capture["request"]["headers"][2][1] = "2.11.0-dev.1"
    with pytest.raises(AssertionError, match="DD-EVP-ORIGIN-VERSION"):
        assert_agentless_evp_intake_request(
            capture,
            route="direct",
            path="/api/v2/exposures",
            expected_api_key="system-tests-mock-api-key",
            library_name="golang",
            library_version="2.11.0-dev.1",
        )


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_wire_contract_rejects_missing_identity() -> None:
    capture = _direct_capture(
        headers=[
            ["DD-API-KEY", "system-tests-mock-api-key"],
            ["Content-Type", "application/json"],
        ]
    )

    with pytest.raises(AssertionError, match="DD-EVP-ORIGIN"):
        assert_agentless_evp_intake_request(
            capture,
            route="direct",
            path="/api/v2/exposures",
            expected_api_key="system-tests-mock-api-key",
            library_name="nodejs",
            library_version="7.0.0-pre",
        )


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_wire_contract_rejects_proxy_header() -> None:
    capture = _direct_capture()
    capture["request"]["headers"].append(["X-Datadog-EVP-Subdomain", "event-platform-intake"])

    with pytest.raises(AssertionError, match="must not send X-Datadog-EVP-Subdomain"):
        assert_agentless_evp_intake_request(
            capture,
            route="direct",
            path="/api/v2/exposures",
            expected_api_key="system-tests-mock-api-key",
            library_name="nodejs",
            library_version="7.0.0-pre",
        )


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_wire_contract_scopes_producer_identity_to_direct_route() -> None:
    capture = _direct_capture(
        headers=[
            ["DD-API-KEY", "--redacted--"],
            ["Content-Type", "application/json"],
            ["Via", "trace-agent 7.81.2"],
        ]
    )

    assert_agentless_evp_intake_request(
        capture,
        route="sidecar",
        path="/api/v2/exposures",
        expected_api_key="system-tests-mock-api-key",
        library_name="nodejs",
        library_version="7.0.0-pre",
    )

    with pytest.raises(AssertionError, match="DD-EVP-ORIGIN"):
        assert_agentless_evp_intake_request(
            capture,
            route="direct",
            path="/api/v2/exposures",
            expected_api_key="system-tests-mock-api-key",
            library_name="nodejs",
            library_version="7.0.0-pre",
        )


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_capture_rejects_local_proxy_routes() -> None:
    with pytest.raises(AssertionError, match="local EVP proxy requests"):
        assert_no_evp_proxy_requests(
            [
                _direct_capture(),
                _direct_capture(path="/evp_proxy/v4/api/v2/exposures"),
            ]
        )


@pytest.mark.parametrize("route", ["direct", "sidecar"])
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_agentless_evp_topology_supports_both_routes(
    route: Literal["direct", "sidecar"],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        f"MOCK_FFE_AGENTLESS_{route.upper()}_TOPOLOGY",
        doc="test",
        exposure_egress=route,
    )
    scenario.weblog_infra.library_container.environment["DD_API_KEY"] = "system-tests-mock-api-key"
    if route == "sidecar":
        scenario.components["serverless-init"] = Version("0.0.0")
    else:
        scenario.weblog_infra.http_container._library = ComponentVersion("java", "0.66.0")  # noqa: SLF001
        scenario._last_direct_evp_runtime_evidence = _direct_runtime_evidence("java")  # noqa: SLF001
    monkeypatch.setattr(context, "scenario", scenario)
    monkeypatch.setattr(interfaces.datadog_direct, "get_data", list)

    selected_interface = interfaces.datadog_direct if route == "direct" else interfaces.datadog_sidecar
    assert_agentless_evp_topology(FeatureFlaggingEVPEgress(selected_interface, route))

    environment = scenario.weblog_infra.library_container.environment
    for runtime_trust_variable in ("NODE_EXTRA_CA_CERTS", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        assert runtime_trust_variable not in environment

    if route == "direct":
        library_container = scenario.weblog_infra.library_container
        expected_mount = {
            "bind": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
            "mode": "ro",
        }
        assert library_container.volumes[DIRECT_EVP_CA_BUNDLE_SOURCE] == expected_mount

        library_container._fix_host_pwd_in_volumes()  # noqa: SLF001 - reproduce container start normalization
        normalized_source = f"{library_container.host_project_dir}{DIRECT_EVP_CA_BUNDLE_SOURCE[1:]}"
        assert library_container.volumes[normalized_source] == expected_mount
        assert_agentless_evp_topology(FeatureFlaggingEVPEgress(selected_interface, route))
    else:
        assert DIRECT_EVP_CA_BUNDLE_SOURCE not in scenario.weblog_infra.library_container.volumes


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_runtime_evidence_accepts_live_minimal_topology() -> None:
    assert_direct_evp_runtime_evidence(_direct_runtime_evidence(), library_name="nodejs")


@pytest.mark.parametrize("executable", ["python3.11", "python3.12"])
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_runtime_evidence_accepts_versioned_python(executable: str) -> None:
    evidence = _direct_runtime_evidence("python")
    evidence["containers"][1]["pid1_command"] = f"/usr/local/bin/{executable} -m gunicorn app:app"
    evidence["containers"][1]["processes"][0]["command"] = f"{executable} -m gunicorn app:app"

    assert_direct_evp_runtime_evidence(evidence, library_name="python")


@pytest.mark.parametrize("executable", ["python3.x", "python3.11-wrapper"])
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_runtime_evidence_rejects_python_prefix_wrappers(executable: str) -> None:
    evidence = _direct_runtime_evidence("python")
    evidence["containers"][1]["pid1_command"] = f"{executable} app"
    evidence["containers"][1]["processes"][0]["command"] = f"{executable} app"

    with pytest.raises(AssertionError, match="versioned python3 interpreter"):
        assert_direct_evp_runtime_evidence(evidence, library_name="python")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("agent_container", "only TLS proxy and weblog"),
        ("agent_variable", "Agent connection variables"),
        ("init_wrapper", "Forbidden direct-scenario runtime components"),
        ("shell_pid1", "expected one of"),
        ("shell_process", "docker top reports PID 1"),
        ("missing_process_command", "PID 1 row has no command"),
        ("failed_top", "docker top failed"),
    ],
)
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_runtime_evidence_rejects_false_proofs(
    mutation: str,
    message: str,
) -> None:
    evidence = _direct_runtime_evidence()
    if mutation == "agent_container":
        agent = deepcopy(evidence["containers"][0])
        agent |= {"id": "agent-id", "name": "system-tests-agent", "image": "datadog/agent"}
        evidence["containers"].append(agent)
        evidence["network"]["container_ids"].append("agent-id")
        evidence["network"]["container_names"].append("system-tests-agent")
    elif mutation == "agent_variable":
        evidence["weblog_environment"]["agent_variables_present"] = ["DD_AGENT_HOST"]
    elif mutation == "init_wrapper":
        evidence["containers"][1]["pid1_command"] = "datadog-init node app"
    elif mutation == "shell_pid1":
        evidence["containers"][1]["pid1_command"] = "/bin/sh ./app.sh"
    elif mutation == "shell_process":
        evidence["containers"][1]["processes"][0]["command"] = "/bin/sh ./app.sh"
    elif mutation == "missing_process_command":
        del evidence["containers"][1]["processes"][0]["command"]
    elif mutation == "failed_top":
        evidence["containers"][1]["top_error"] = "APIError: top failed"
    else:
        raise AssertionError(f"Unhandled mutation {mutation}")

    with pytest.raises(AssertionError, match=message):
        assert_direct_evp_runtime_evidence(evidence, library_name="nodejs")


@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_shutdown_evidence_accepts_bounded_post_stop_delivery() -> None:
    assert_direct_evp_shutdown_evidence(_direct_shutdown_evidence())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("explicit_flush", "must not call"),
        ("request_before_marker", "before server close"),
        ("duplicate_capture", "exactly one event"),
        ("over_bound", "exceeding the"),
        ("stop_error", "Shutdown returned an error"),
        ("still_running", "remained running"),
        ("oom_killed", "OOM-killed"),
        ("signal_exit", "graceful shutdown path"),
        ("missing_marker", "exactly one structured server-close marker"),
        ("duplicate_marker", "exactly one structured server-close marker"),
        ("missing_prime", "fresh flush window"),
        ("duplicate_prime", "exactly one capture"),
        ("same_prime_subject", "subject distinct"),
    ],
)
@scenarios.test_the_test
@features.not_reported
def test_feature_flagging_direct_shutdown_evidence_rejects_false_proofs(
    mutation: str,
    message: str,
) -> None:
    evidence = _direct_shutdown_evidence()
    if mutation == "explicit_flush":
        evidence["explicit_flush"] = True
    elif mutation == "request_before_marker":
        evidence["capture_request_started_at"] = ["2026-09-09T12:00:01.125000+00:00"]
    elif mutation == "duplicate_capture":
        evidence["captures_after_settle"] = 2
    elif mutation == "over_bound":
        evidence["shutdown_duration_seconds"] = 12.1
    elif mutation == "stop_error":
        evidence["stop_error"] = "RuntimeError: stop failed"
    elif mutation == "still_running":
        evidence["stopped_container"]["running"] = True
    elif mutation == "oom_killed":
        evidence["stopped_container"]["oom_killed"] = True
    elif mutation == "signal_exit":
        evidence["stopped_container"]["exit_code"] = 143
    elif mutation == "missing_marker":
        evidence["shutdown_markers"] = []
    elif mutation == "duplicate_marker":
        evidence["shutdown_markers"].append(deepcopy(evidence["shutdown_markers"][0]))
    elif mutation == "missing_prime":
        evidence["flush_window_primed"] = False
    elif mutation == "duplicate_prime":
        evidence["priming_capture_files"].append("direct-prime-0002.json")
    elif mutation == "same_prime_subject":
        evidence["priming_subject_id"] = evidence["subject_id"]
    else:
        raise AssertionError(f"Unhandled mutation {mutation}")

    with pytest.raises(AssertionError, match=message):
        assert_direct_evp_shutdown_evidence(evidence)

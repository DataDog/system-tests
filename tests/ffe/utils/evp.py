"""Shared Feature Flags EVP route, wire, identity, and topology assertions."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from utils import context, interfaces
from utils._context._scenarios.agentless_endtoend import (
    DIRECT_EVP_AGENT_VARIABLES,
    DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
    DIRECT_EVP_CA_BUNDLE_SOURCE,
    DIRECT_EVP_SHUTDOWN_MARKER_EVENT,
    DIRECT_EVP_SIGNAL_PATHS,
    DIRECT_EVP_STOP_TIMEOUT_SECONDS,
    FeatureFlaggingAgentlessEndToEndScenario,
)
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.mocked_backend.ffe import EXPECTED_API_KEY


EVP_DIRECT_HOST = "event-platform-intake.mock-intake.invalid"
EVP_DIRECT_PORT = 443
EVP_PROXY_PATH_PREFIXES = ("/evp_proxy/v2/", "/evp_proxy/v4/")
EVP_FORBIDDEN_RUNTIME_COMPONENTS = (
    "datadog-agent",
    "datadog-init",
    "process-agent",
    "serverless-init",
    "telemetry-sidecar",
    "trace-agent",
)
EVP_LANGUAGE_PID1_EXECUTABLES = {
    "dotnet": {"dotnet"},
    "golang": {"weblog"},
    "java": {"java"},
    "nodejs": {"node"},
    "python": {"gunicorn", "python", "python3", "uwsgi"},
    "ruby": {"puma", "ruby"},
}

EVP_ORIGINS = {
    "dotnet": "dd-trace-dotnet",
    "golang": "dd-trace-go",
    "java": "dd-trace-java",
    "nodejs": "dd-trace-js",
    "python": "dd-trace-py",
    "ruby": "dd-trace-rb",
}

EVPRoute = Literal["agent", "sidecar", "direct"]


def _is_expected_pid1_executable(library_name: str, executable: str, expected: set[str]) -> bool:
    """Accept ordinary language launchers without accepting wrappers by prefix."""
    if executable in expected:
        return True
    if library_name != "python" or not executable.startswith("python3."):
        return False
    return executable.removeprefix("python3.").isdigit()


@dataclass(frozen=True)
class FeatureFlaggingEVPEgress:
    """The capture interface and routing expectations for one FFE topology."""

    interface: ProxyBasedInterfaceValidator
    route: EVPRoute
    excluded_interfaces: tuple[ProxyBasedInterfaceValidator, ...] = ()
    expected_api_key: str | None = None


def feature_flagging_evp_egress() -> FeatureFlaggingEVPEgress:
    """Return the EVP capture route selected by the current FFE scenario."""
    scenario = context.scenario
    if not isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario):
        assert scenario.name == "FEATURE_FLAGGING_AND_EXPERIMENTATION"
        return FeatureFlaggingEVPEgress(interfaces.agent, "agent")

    if scenario.exposure_egress == "sidecar":
        assert "serverless-init" in scenario.components
        expected_api_key = scenario.serverless_init_container.environment["DD_API_KEY"]
        assert expected_api_key is not None
        return FeatureFlaggingEVPEgress(
            interfaces.datadog_sidecar,
            "sidecar",
            (interfaces.datadog_direct,),
            expected_api_key,
        )

    assert scenario.exposure_egress == "direct"
    assert "serverless-init" not in scenario.components
    return FeatureFlaggingEVPEgress(
        interfaces.datadog_direct,
        "direct",
        (interfaces.datadog_sidecar,),
        EXPECTED_API_KEY,
    )


def register_expected_evp_capture(path: str) -> None:
    """Register a signal for scenario-owned capture waiting before shutdown."""
    scenario = context.scenario
    if isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario) and scenario.exposure_egress is not None:
        scenario.register_expected_evp_capture(path)


def register_shutdown_evp_evaluation(
    *,
    signal_path: str,
    request_path: str,
    body: dict[str, Any],
    flag_key: str,
    subject_id: str,
) -> None:
    """Register one evaluation for the scenario-owned shutdown-flush phase."""
    scenario = context.scenario
    if isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario):
        scenario.register_shutdown_evp_evaluation(
            signal_path=signal_path,
            request_path=request_path,
            body=body,
            flag_key=flag_key,
            subject_id=subject_id,
        )


def expected_evp_origin(library_name: str) -> str:
    """Return the logical EVP producer identity for a system-tests library."""
    try:
        return EVP_ORIGINS[library_name]
    except KeyError as error:
        raise AssertionError(f"No EVP origin is defined for system-tests library {library_name!r}") from error


def expected_evp_origin_version(library_name: str, library_version: str) -> str:
    """Return the tracer's canonical wire version for direct EVP identity.

    System-tests deliberately removes Go's leading ``v`` when it parses the
    component version for manifest comparisons. dd-trace-go's public version
    tag and existing EVP producer identity retain that prefix, so restore it
    only for the wire assertion instead of weakening identity checks globally.
    """
    if library_name == "golang" and not library_version.startswith("v"):
        return f"v{library_version}"
    return library_version


def _header_values(data: dict[str, Any], name: str) -> list[str]:
    headers = data.get("request", {}).get("headers")
    assert isinstance(headers, list), f"request headers must be a list: {data}"
    return [
        value for header_name, value in headers if isinstance(header_name, str) and header_name.lower() == name.lower()
    ]


def _assert_single_header(data: dict[str, Any], name: str, expected: str | set[str]) -> None:
    values = _header_values(data, name)
    assert len(values) == 1, f"expected exactly one {name} header, got {values!r}"
    allowed = {expected} if isinstance(expected, str) else expected
    assert values[0] in allowed, f"expected {name} in {sorted(allowed)!r}, got {values[0]!r}"


def assert_agentless_evp_intake_request(
    data: dict[str, Any],
    *,
    route: EVPRoute,
    path: str,
    expected_api_key: str,
    library_name: str,
    library_version: str,
) -> None:
    """Assert one captured Agentless EVP request against the shared wire contract."""
    assert path in DIRECT_EVP_SIGNAL_PATHS, f"unsupported EVP signal path {path!r}"
    assert data.get("method") == "POST", f"EVP request must use POST: {data}"
    assert data.get("path") == path, f"EVP request must use canonical path {path!r}: {data}"
    assert data.get("host") == EVP_DIRECT_HOST, f"unexpected EVP intake host: {data}"
    assert data.get("port") == EVP_DIRECT_PORT, f"EVP direct request must use HTTPS port 443: {data}"

    response = data.get("response")
    assert isinstance(response, dict), f"EVP capture must include a response: {data}"
    assert response.get("status_code") == 202, f"EVP intake must return 202: {data}"

    _assert_single_header(data, "DD-API-KEY", {expected_api_key, "--redacted--"})

    content_types = _header_values(data, "Content-Type")
    assert len(content_types) == 1, f"expected exactly one Content-Type header, got {content_types!r}"
    assert content_types[0].split(";", 1)[0].strip().lower() == "application/json"
    assert not _header_values(data, "X-Datadog-EVP-Subdomain"), (
        "direct-intake requests must not send X-Datadog-EVP-Subdomain"
    )

    assert route in ("direct", "sidecar")
    if route == "sidecar":
        # datadog_sidecar captures relay-to-intake traffic, not the SDK-to-relay request. Relayed
        # producer identity requires Agent 7.84+, while the default fixture may still be earlier;
        # SDK local-route identity and credential omission remain covered by SDK unit tests.
        return

    _assert_single_header(data, "DD-EVP-ORIGIN", expected_evp_origin(library_name))
    _assert_single_header(
        data,
        "DD-EVP-ORIGIN-VERSION",
        expected_evp_origin_version(library_name, library_version),
    )


def assert_no_evp_proxy_requests(captures: Iterable[dict[str, Any]]) -> None:
    """Reject local relay paths in a direct-intake capture stream."""
    proxy_paths = [
        path
        for data in captures
        if isinstance((path := data.get("path")), str) and path.startswith(EVP_PROXY_PATH_PREFIXES)
    ]
    assert not proxy_paths, f"direct capture unexpectedly contains local EVP proxy requests: {proxy_paths}"


def _runtime_text(container: dict[str, Any]) -> str:
    process_text = "\n".join(
        " ".join(str(value) for value in process.values()) for process in container.get("processes", [])
    )
    return "\n".join(
        (
            str(container.get("name", "")),
            str(container.get("image", "")),
            str(container.get("pid1_command", "")),
            process_text,
        )
    ).lower()


def assert_direct_evp_runtime_evidence(evidence: dict[str, Any], *, library_name: str) -> None:
    """Assert preserved Docker inspect/top evidence for the live direct scenario."""
    containers = evidence.get("containers")
    assert isinstance(containers, list), "Direct EVP runtime evidence has no live container list"
    containers_by_name: dict[str, dict[str, Any]] = {}
    for container in containers:
        assert isinstance(container, dict), f"Malformed live container evidence: {container!r}"
        name = container.get("name")
        assert isinstance(name, str), f"Live container evidence has no name: {container}"
        assert name not in containers_by_name, f"Duplicate live container evidence for {name!r}"
        containers_by_name[name] = container
    expected_names = {"system-tests-proxy", "system-tests-weblog"}
    assert set(containers_by_name) == expected_names, (
        f"Direct EVP runtime network must contain only TLS proxy and weblog, got {sorted(containers_by_name)}"
    )

    network = evidence.get("network")
    assert isinstance(network, dict), "Direct EVP runtime evidence has no network inspection"
    assert network.get("id"), "Direct EVP runtime network has no Docker ID"
    assert network.get("name"), "Direct EVP runtime network has no name"
    observed_ids = {container.get("id") for container in containers_by_name.values()}
    assert set(network.get("container_ids", [])) == observed_ids, "Network membership and inspected containers disagree"
    assert set(network.get("container_names", [])) == expected_names, "Docker network inspection has unexpected members"

    for container in containers_by_name.values():
        assert container.get("running") is True, f"Runtime container was not running: {container}"
        assert container.get("status") == "running", f"Unexpected live container status: {container}"
        assert container.get("top_error") is None, f"docker top failed: {container.get('top_error')}"
        assert container.get("pid1_error") is None, f"PID 1 inspection failed: {container.get('pid1_error')}"
        assert container.get("pid1_command"), f"Runtime container has no PID 1 command: {container}"
        assert container.get("networks") == [network["name"]], f"Unexpected runtime networks: {container}"
        processes = container.get("processes")
        assert isinstance(processes, list), f"Runtime process tree is malformed: {container}"
        assert processes, f"Runtime process tree is empty: {container}"
        assert all(isinstance(process, dict) for process in processes), f"Malformed runtime process rows: {container}"
        state_pid = str(container.get("state_pid"))
        pid1_processes = [process for process in processes if process.get("pid") == state_pid]
        assert len(pid1_processes) == 1, (
            f"docker top must contain exactly one inspected container PID {state_pid}: {container}"
        )
        forbidden = [name for name in EVP_FORBIDDEN_RUNTIME_COMPONENTS if name in _runtime_text(container)]
        assert not forbidden, f"Forbidden direct-scenario runtime components found: {forbidden}"

    proxy = containers_by_name["system-tests-proxy"]
    proxy_runtime = _runtime_text(proxy)
    assert "proxy.core" in proxy_runtime or "proxy/core.py" in proxy_runtime, (
        f"The only allowed helper must be the system-tests TLS capture proxy: {proxy}"
    )

    weblog = containers_by_name["system-tests-weblog"]
    assert weblog.get("library") == library_name, (
        f"Live weblog library label is {weblog.get('library')!r}, expected {library_name!r}"
    )
    expected_executables = EVP_LANGUAGE_PID1_EXECUTABLES.get(library_name)
    assert expected_executables, f"No ordinary PID 1 contract is defined for {library_name!r}"
    pid1_executable = Path(str(weblog["pid1_command"]).split()[0]).name
    assert _is_expected_pid1_executable(library_name, pid1_executable, expected_executables), (
        f"Live weblog PID 1 is {weblog['pid1_command']!r}, expected one of "
        f"{sorted(expected_executables)} or a versioned python3 interpreter"
    )
    weblog_state_pid = str(weblog.get("state_pid"))
    pid1_process = next(process for process in weblog["processes"] if process.get("pid") == weblog_state_pid)
    pid1_process_command = pid1_process.get("command")
    assert pid1_process_command is not None, f"docker top PID 1 row has no command: {pid1_process}"
    assert isinstance(pid1_process_command, str), f"docker top PID 1 command is malformed: {pid1_process}"
    assert pid1_process_command, f"docker top PID 1 row has no command: {pid1_process}"
    pid1_process_executable = Path(pid1_process_command.split()[0]).name
    assert _is_expected_pid1_executable(library_name, pid1_process_executable, expected_executables), (
        f"docker top reports PID 1 as {pid1_process_command!r}, expected one of "
        f"{sorted(expected_executables)} or a versioned python3 interpreter"
    )

    environment = evidence.get("weblog_environment")
    assert isinstance(environment, dict), "Live weblog environment was not captured"
    assert environment.get("agent_variables_present") == [], (
        f"Live direct weblog contains Agent connection variables: {environment.get('agent_variables_present')}"
    )
    assert environment.get("api_key_present") is True
    assert environment.get("api_key_matches_expected") is True
    assert environment.get("configuration_source") == "agentless"
    assert environment.get("provider_enabled") == "true"
    assert environment.get("shutdown_flush_enabled") == "true"
    assert environment.get("site") == "mock-intake.invalid"

    expected_mounts = [
        mount for mount in weblog.get("mounts", []) if mount.get("destination") == DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH
    ]
    assert len(expected_mounts) == 1, (
        f"Live weblog must have one {DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH} mount: {weblog.get('mounts')}"
    )
    assert expected_mounts[0].get("read_write") is False, "Direct EVP CA bundle must be mounted read-only"


def assert_direct_evp_shutdown_evidence(evidence: dict[str, Any]) -> None:
    """Assert a late evaluation was delivered by the bounded shutdown-flush phase."""
    assert evidence.get("flush_window_primed") is True, "Shutdown target was not placed in a fresh flush window"
    assert evidence.get("priming_evaluation_status_code") == 200, "Flush-window priming evaluation did not succeed"
    priming_files = evidence.get("priming_capture_files")
    assert isinstance(priming_files, list), f"Priming capture files are malformed: {priming_files}"
    assert len(priming_files) == 1, f"Flush-window priming must produce exactly one capture: {priming_files}"
    priming_request_started = evidence.get("priming_capture_request_started_at")
    assert isinstance(priming_request_started, list), (
        f"Priming capture request timestamps are malformed: {priming_request_started}"
    )
    assert len(priming_request_started) == 1, (
        f"Flush-window priming must identify exactly one request timestamp: {priming_request_started}"
    )
    assert evidence.get("priming_subject_id") != evidence.get("subject_id"), (
        "Flush-window priming must use a subject distinct from the shutdown target"
    )
    assert evidence.get("evaluation_status_code") == 200, "Shutdown evaluation did not succeed"
    assert evidence.get("explicit_flush") is False, "Shutdown proof must not call the weblog /flush endpoint"
    assert evidence.get("captures_before_evaluation") == 0, "Shutdown probe was already captured before evaluation"
    assert evidence.get("captures_before_stop") == 0, "Shutdown probe escaped before Docker sent SIGTERM"
    assert evidence.get("capture_observed_after_stop") is True, "Shutdown-flushed event was not observed after stop"
    assert evidence.get("captures_after_settle") == 1, "Shutdown flush did not deliver exactly one event"
    capture_files = evidence.get("capture_files")
    assert isinstance(capture_files, list), f"Shutdown capture files are malformed: {capture_files}"
    assert len(capture_files) == 1, f"Shutdown evidence must identify exactly one capture file: {capture_files}"
    assert capture_files[0], f"Shutdown capture filename is empty: {capture_files}"

    duration = evidence.get("shutdown_duration_seconds")
    bound = evidence.get("shutdown_bound_seconds")
    assert isinstance(duration, (int, float))
    assert isinstance(bound, (int, float))
    assert duration <= bound, f"Shutdown flush took {duration}s, exceeding the {bound}s bound"
    assert evidence.get("stop_timeout_seconds") == DIRECT_EVP_STOP_TIMEOUT_SECONDS
    assert evidence.get("stop_error") is None, f"Shutdown returned an error: {evidence.get('stop_error')}"

    stopped = evidence.get("stopped_container")
    assert isinstance(stopped, dict), "Post-stop Docker inspection is absent"
    assert "inspection_error" not in stopped, f"Post-stop Docker inspection failed: {stopped}"
    assert stopped.get("running") is False, "Weblog remained running after bounded stop"
    assert stopped.get("status") == "exited", f"Unexpected post-stop state: {stopped}"
    assert stopped.get("oom_killed") is False, f"Weblog was OOM-killed: {stopped}"
    assert stopped.get("error") in (None, ""), f"Docker reported a stop error: {stopped}"
    assert stopped.get("exit_code") == 0, f"Weblog did not complete its graceful shutdown path: {stopped}"
    assert stopped.get("finished_at"), f"Post-stop finish timestamp is absent: {stopped}"

    marker_errors = evidence.get("shutdown_marker_errors")
    assert marker_errors == [], f"Could not read shutdown markers from post-stop Docker logs: {marker_errors}"
    markers = evidence.get("shutdown_markers")
    assert isinstance(markers, list), f"Shutdown markers are malformed: {markers}"
    assert len(markers) == 1, f"Expected exactly one structured server-close marker, got {markers}"
    marker = markers[0]
    assert isinstance(marker, dict), f"Shutdown marker is malformed: {marker}"
    assert marker.get("event") == DIRECT_EVP_SHUTDOWN_MARKER_EVENT
    assert marker.get("stream") == "stdout", f"Server-close marker must be written to stdout: {marker}"

    priming_finished = datetime.fromisoformat(str(evidence.get("priming_evaluation_finished_at")))
    priming_capture_started = datetime.fromisoformat(str(priming_request_started[0]))
    evaluation_finished = datetime.fromisoformat(str(evidence.get("evaluation_finished_at")))
    stop_started = datetime.fromisoformat(str(evidence.get("stop_started_at")))
    server_closed = datetime.fromisoformat(str(marker.get("timestamp")))
    stopped_at = datetime.fromisoformat(str(evidence.get("stopped_at")))
    assert priming_finished <= evaluation_finished <= stop_started <= server_closed <= stopped_at, (
        "Shutdown lifecycle timestamps are out of order"
    )
    assert priming_capture_started <= evaluation_finished, "Priming flush did not begin before the shutdown target"
    capture_started_values = evidence.get("capture_request_started_at")
    assert isinstance(capture_started_values, list)
    assert len(capture_started_values) == 1
    capture_started = datetime.fromisoformat(str(capture_started_values[0]))
    assert capture_started >= server_closed, (
        f"Event request started at {capture_started.isoformat()} before server close at {server_closed.isoformat()}"
    )


def assert_agentless_evp_topology(egress: FeatureFlaggingEVPEgress) -> None:
    """Assert the effective scenario topology for an Agentless EVP route."""
    if egress.route == "agent":
        return

    scenario = context.scenario
    assert isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario)
    assert scenario.include_agent is False
    assert scenario.get_libraries() is None

    environment = scenario.weblog_infra.library_container.environment
    assert environment["DD_FEATURE_FLAGS_CONFIGURATION_SOURCE"] == "agentless"
    assert environment["DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED"] == "true"
    assert environment["DD_SITE"] == "mock-intake.invalid"
    if not scenario.replay:
        assert environment["DD_API_KEY"] == EXPECTED_API_KEY
    if egress.route == "direct":
        assert_direct_evp_runtime_evidence(
            scenario.direct_evp_runtime_evidence(),
            library_name=context.library.name,
        )
        library_container = scenario.weblog_infra.library_container
        expected_mount = {
            "bind": DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH,
            "mode": "ro",
        }
        mounted_sources = [
            Path(source) for source, mount in library_container.volumes.items() if mount == expected_mount
        ]
        assert len(mounted_sources) == 1, (
            f"expected exactly one read-only {DIRECT_EVP_CA_BUNDLE_CONTAINER_PATH} mount, "
            f"got {library_container.volumes!r}"
        )
        mounted_source = mounted_sources[0]
        if not mounted_source.is_absolute():
            mounted_source = Path(library_container.host_project_dir) / mounted_source
        expected_source = Path(library_container.host_project_dir) / DIRECT_EVP_CA_BUNDLE_SOURCE
        assert mounted_source.resolve() == expected_source.resolve()
        for name in DIRECT_EVP_AGENT_VARIABLES:
            assert name not in environment
        assert "serverless-init" not in scenario.components
        assert not any(container.name == "ffe-serverless-init" for container in scenario.weblog_infra.get_containers())
        assert_no_evp_proxy_requests(interfaces.datadog_direct.get_data())
        return

    assert egress.route == "sidecar"
    assert "serverless-init" in scenario.components

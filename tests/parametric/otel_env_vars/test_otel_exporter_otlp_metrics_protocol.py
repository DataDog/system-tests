"""OTLP protocol selection, observed at the exporter boundary.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specify-protocol
"""

import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from google.protobuf.json_format import MessageToDict, ParseDict

from utils import context, features, scenarios
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_metrics import generate_default_counter_data_point

VARIABLE = "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL"


def _non_default_protocol(signal: str) -> str:
    """An uppercase transport distinguishable from this SDK's default."""
    if context.library == "nodejs" or (context.library == "php" and signal == "logs"):
        return "HTTP/JSON"
    if context.library in ("python", "dotnet", "rust"):
        return "HTTP/PROTOBUF"
    return "GRPC"


def _default_protocol(signal: str) -> str:
    if context.library in ("python", "dotnet", "rust"):
        return "grpc"
    if context.library == "golang" and signal == "logs":
        return "http/json"
    return "http/protobuf"


@pytest.fixture
def protocol(request: pytest.FixtureRequest, signal: str) -> str:
    value = _non_default_protocol(signal)
    return value.lower() if getattr(request, "param", None) == "nondefault" else value


@pytest.fixture
def generic_protocol(request: pytest.FixtureRequest, signal: str) -> str | None:
    selection = getattr(request, "param", None)
    if selection == "nondefault":
        return _non_default_protocol(signal).lower()
    if selection == "default":
        return _default_protocol(signal)
    return None


@pytest.fixture
def expected_protocol(generic_protocol: str | None, protocol: str | None, signal: str) -> str:
    if generic_protocol and not protocol:
        return generic_protocol
    if protocol and protocol != "unsupported":
        return protocol.lower()
    return _default_protocol(signal)


@pytest.fixture
def library_env(
    generic_protocol: str | None,
    protocol: str | None,
    signal: str,
    expected_protocol: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> dict[str, str | None]:
    port = test_agent_otlp_grpc_port if expected_protocol == "grpc" else test_agent_otlp_http_port
    path = "" if expected_protocol == "grpc" else f"/v1/{signal}"
    env: dict[str, str | None] = {
        "DD_TRACE_DEBUG": None,
        "DD_TRACE_OTEL_ENABLED": "true",
        "DD_LOGS_OTEL_ENABLED": "true" if signal == "logs" else "false",
        "DD_METRICS_OTEL_ENABLED": "true" if signal == "metrics" else "false",
        "DD_RUNTIME_METRICS_ENABLED": "false",
        "CORECLR_ENABLE_PROFILING": "1",
        "OTEL_TRACES_EXPORTER": None,
        "OTEL_LOGS_EXPORTER": "otlp" if signal == "logs" else "none",
        "OTEL_METRICS_EXPORTER": "otlp" if signal == "metrics" else "none",
        "OTEL_METRIC_EXPORT_INTERVAL": "60000",
        "OTEL_EXPORTER_OTLP_PROTOCOL": generic_protocol,
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": None,
        "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": None,
        "OTEL_EXPORTER_OTLP_ENDPOINT": None,
        f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT": f"http://{test_agent.container_name}:{port}{path}",
    }
    env[VARIABLE] = protocol
    return env


def _assert_export(test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str) -> None:
    with test_library as library:
        generate_default_counter_data_point(library, "selected_protocol_counter")

    payloads = [
        MessageToDict(ParseDict(payload, ExportMetricsServiceRequest()), preserving_proto_field_name=True)
        for payload in test_agent.wait_for_num_otlp_metrics(1)
    ]
    assert any(
        metric["name"] == "selected_protocol_counter"
        for payload in payloads
        for resource in payload["resource_metrics"]
        for scope in resource["scope_metrics"]
        for metric in scope["metrics"]
    ), payloads

    # The gRPC listener forwards decoded payloads internally over HTTP. A
    # successful export to its dedicated port proves gRPC; forwarded headers do
    # not represent the original gRPC wire format.
    if expected_protocol != "grpc":
        requests = [request for request in test_agent.requests() if request["url"].endswith(f"/v1/{signal}")]
        assert requests, f"No OTLP {signal} request captured"
        content_type = "application/json" if expected_protocol == "http/json" else "application/x-protobuf"
        for request in requests:
            headers = {name.lower(): value for name, value in request["headers"].items()}
            assert headers.get("content-type", "").split(";")[0] == content_type, headers


@features.otel_exporter_otlp_metrics_protocol
@scenarios.parametric
@pytest.mark.parametrize("signal", ["metrics"])
class Test_OTEL_EXPORTER_OTLP_METRICS_PROTOCOL:
    """All specified transports, with separate declarations for optional protocols."""

    @pytest.mark.parametrize("protocol", [pytest.param("http/protobuf", id="http-protobuf")])
    def test_http_protobuf(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("protocol", [pytest.param("grpc", id="grpc")])
    def test_grpc(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("protocol", [pytest.param("http/json", id="http-json")])
    def test_http_json(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("protocol", [pytest.param(None, id="unset")])
    def test_default(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        assert expected_protocol in ("http/protobuf", "grpc")
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("protocol", [pytest.param("", id="empty")])
    def test_empty(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("protocol", [pytest.param("unsupported", id="invalid")])
    def test_invalid(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    def test_case_insensitive(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("generic_protocol", [pytest.param("default", id="generic-default")], indirect=True)
    @pytest.mark.parametrize("protocol", [pytest.param("nondefault", id="signal-nondefault")], indirect=True)
    def test_signal_precedence(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize("generic_protocol", [pytest.param("nondefault", id="generic-nondefault")], indirect=True)
    @pytest.mark.parametrize("protocol", [pytest.param(None, id="unset"), pytest.param("", id="empty")])
    def test_generic_fallback(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

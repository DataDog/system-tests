"""OTLP protocol selection, observed at the exporter boundary.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specify-protocol
"""

import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from google.protobuf.json_format import MessageToDict, ParseDict

from utils import context, features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_logs import find_log_record
from tests.parametric.test_otel_metrics import generate_default_counter_data_point

VARIABLE = "OTEL_EXPORTER_OTLP_PROTOCOL"


@pytest.fixture
def protocol(signal: str) -> str:
    """An uppercase transport distinguishable from this SDK's default."""
    if context.library == "nodejs" or (context.library == "php" and signal == "logs"):
        return "HTTP/JSON"
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "HTTP/PROTOBUF"
    return "GRPC"


@pytest.fixture
def expected_protocol(protocol: str | None, signal: str) -> str:
    if protocol and protocol != "unsupported":
        return protocol.lower()
    # OTel permits retaining a historical gRPC default. These defaults are
    # published by the SDKs; never derive the expectation from the tested input.
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "grpc"
    if context.library == "golang" and signal == "logs":
        return "http/json"
    return "http/protobuf"


# The test matrix supplies the protocol value to exercise protocol selection.
# Default cases leave it unset; the endpoint selects the expected HTTP/gRPC
# listener so delivery proves the transport, including SDKs that default to gRPC.
# Use the generic endpoint so each SDK derives its HTTP or gRPC signal path.
@pytest.fixture
def library_env(
    protocol: str | None,
    signal: str,
    expected_protocol: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> dict[str, str | None]:
    port = test_agent_otlp_grpc_port if expected_protocol == "grpc" else test_agent_otlp_http_port
    return {
        f"DD_{signal.upper()}_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{test_agent.container_name}:{port}",
        VARIABLE: protocol,
    }


def _assert_export(test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str) -> None:
    with test_library as library:
        if signal == "logs":
            library.create_logger("protocol-test", LogLevel.INFO)
            library.write_log("protocol-test", LogLevel.INFO, "selected-protocol")
        else:
            generate_default_counter_data_point(library, "selected_protocol_counter")

    if signal == "logs":
        payloads = [
            MessageToDict(ParseDict(payload, ExportLogsServiceRequest()), preserving_proto_field_name=True)
            for payload in test_agent.wait_for_num_log_payloads(1)
        ]
        assert find_log_record(payloads, "protocol-test", "selected-protocol") is not None
    else:
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


@features.otel_exporter_otlp_protocol
@scenarios.parametric
@pytest.mark.parametrize("signal", ["metrics"])
class Test_OTEL_EXPORTER_OTLP_PROTOCOL:
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


@features.otel_exporter_otlp_protocol
@scenarios.parametric
@pytest.mark.parametrize("signal", ["logs"])
class Test_OTEL_EXPORTER_OTLP_PROTOCOL_Logs:
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

    @pytest.mark.parametrize("protocol", [pytest.param(None, id="unset")])
    def test_documented_json_default(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        """Go documents HTTP/JSON as its logs default, independently of the OTel recommendation."""
        assert expected_protocol == "http/json"
        _assert_export(test_library, test_agent, signal, expected_protocol)

"""OTLP protocol selection, observed at the exporter boundary.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specify-protocol
"""

import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from google.protobuf.json_format import MessageToDict, ParseDict

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel
from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars import otlp_protocol_fixtures
from tests.parametric.test_otel_logs import find_log_record

VARIABLE = "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"

protocol = otlp_protocol_fixtures.protocol
generic_protocol = otlp_protocol_fixtures.generic_protocol
expected_protocol = otlp_protocol_fixtures.expected_protocol
library_env = otlp_protocol_fixtures.library_env


@pytest.fixture
def protocol_variable() -> str:
    return VARIABLE


def _assert_export(test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str) -> None:
    with test_library as library:
        library.create_logger("protocol-test", LogLevel.INFO)
        library.write_log("protocol-test", LogLevel.INFO, "selected-protocol")

    payloads = [
        MessageToDict(ParseDict(payload, ExportLogsServiceRequest()), preserving_proto_field_name=True)
        for payload in test_agent.wait_for_num_log_payloads(1)
    ]
    assert find_log_record(payloads, "protocol-test", "selected-protocol") is not None

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


@features.otel_exporter_otlp_logs_protocol
@scenarios.parametric
@pytest.mark.parametrize("signal", ["logs"])
class Test_OTEL_EXPORTER_OTLP_LOGS_PROTOCOL:
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

    @pytest.mark.parametrize("protocol", [pytest.param(None, id="unset")])
    def test_documented_json_default(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        """Go documents HTTP/JSON as its logs default, independently of the OTel recommendation."""
        assert expected_protocol == "http/json"
        _assert_export(test_library, test_agent, signal, expected_protocol)

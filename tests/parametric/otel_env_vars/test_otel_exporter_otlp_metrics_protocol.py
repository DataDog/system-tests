"""OTLP protocol selection, observed at the exporter boundary.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specify-protocol
"""

import pytest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from google.protobuf.json_format import MessageToDict, ParseDict

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars import otlp_protocol_fixtures
from tests.parametric.test_otel_metrics import generate_default_counter_data_point

VARIABLE = "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL"


# The test matrix supplies the protocol value to exercise protocol selection.
# Default cases leave it unset; the endpoint selects the expected HTTP/gRPC
# listener so delivery proves the transport, including SDKs that default to gRPC.
# Use the generic endpoint so each SDK derives its HTTP or gRPC signal path.
@pytest.fixture
def library_env(
    generic_protocol: str | None,
    protocol: str | None,
    signal: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> dict[str, str | None]:
    expected_protocol = otlp_protocol_fixtures.expected_protocol(generic_protocol, protocol, signal)
    port = test_agent_otlp_grpc_port if expected_protocol == "grpc" else test_agent_otlp_http_port
    env: dict[str, str | None] = {
        f"DD_{signal.upper()}_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{test_agent.container_name}:{port}",
        VARIABLE: protocol,
    }
    if generic_protocol is not None:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = generic_protocol
    return env


def _assert_export(
    test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, protocol: str | None, generic_protocol: str | None
) -> None:
    expected_protocol = otlp_protocol_fixtures.expected_protocol(generic_protocol, protocol, signal)
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

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"), [pytest.param("http/protobuf", None, id="http-protobuf")]
    )
    def test_http_protobuf(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("grpc", None, id="grpc")])
    def test_grpc(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("http/json", None, id="http-json")])
    def test_http_json(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param(None, None, id="unset")])
    def test_default(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        assert otlp_protocol_fixtures.default_protocol(signal) in ("http/protobuf", "grpc")
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("", None, id="empty")])
    def test_empty(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("unsupported", None, id="invalid")])
    def test_invalid(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [pytest.param(otlp_protocol_fixtures.non_default_protocol("metrics"), None, id="uppercase")],
    )
    def test_case_insensitive(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(
                otlp_protocol_fixtures.non_default_protocol("metrics").lower(),
                otlp_protocol_fixtures.default_protocol("metrics"),
                id="signal-nondefault-generic-default",
            )
        ],
    )
    def test_signal_precedence(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(
                None, otlp_protocol_fixtures.non_default_protocol("metrics").lower(), id="unset-generic-nondefault"
            )
        ],
    )
    def test_generic_fallback(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(
                "", otlp_protocol_fixtures.non_default_protocol("metrics").lower(), id="empty-generic-nondefault"
            )
        ],
    )
    def test_empty_generic_fallback(
        self,
        test_library: APMLibrary,
        test_agent: TestAgentAPI,
        signal: str,
        protocol: str | None,
        generic_protocol: str | None,
    ) -> None:
        _assert_export(test_library, test_agent, signal, protocol, generic_protocol)

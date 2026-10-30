"""OTLP protocol selection, observed at the exporter boundary.

https://opentelemetry.io/docs/specs/otel/protocol/exporter/#specify-protocol
"""

from utils import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from google.protobuf.json_format import MessageToDict, ParseDict

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel
from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars import utils as otel_env_var_utils
from tests.parametric.otel_env_vars.conftest import DefaultProtocol
from tests.parametric.utils import find_log_record

VARIABLE = "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"


# default_protocol is the fixture from otel_env_vars/conftest.py that observes the SDK's default.
@pytest.fixture
def expected_protocol(
    generic_protocol: otel_env_var_utils.ProtocolInput,
    protocol: otel_env_var_utils.ProtocolInput,
    signal: str,
    default_protocol: DefaultProtocol,
) -> str:
    return otel_env_var_utils.expected_protocol(generic_protocol, protocol, signal, default_protocol)


# The test matrix supplies the protocol value to exercise protocol selection.
# Default cases leave it unset; the endpoint selects the expected HTTP/gRPC
# listener so delivery proves the transport, including SDKs that default to gRPC.
# Use the generic endpoint so each SDK derives its HTTP or gRPC signal path.
@pytest.fixture
def library_env(
    generic_protocol: otel_env_var_utils.ProtocolInput,
    protocol: otel_env_var_utils.ProtocolInput,
    signal: str,
    default_protocol: DefaultProtocol,
    expected_protocol: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> dict[str, str | None]:
    port = test_agent_otlp_grpc_port if expected_protocol == "grpc" else test_agent_otlp_http_port
    env: dict[str, str | None] = {
        f"DD_{signal.upper()}_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{test_agent.container_name}:{port}",
        VARIABLE: otel_env_var_utils.resolve_protocol(protocol, signal, default_protocol),
    }
    if generic_protocol is not None:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = otel_env_var_utils.resolve_protocol(
            generic_protocol, signal, default_protocol
        )
    return env


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

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"), [pytest.param("http/protobuf", None, id="http-protobuf")]
    )
    def test_http_protobuf(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("grpc", None, id="grpc")])
    def test_grpc(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("http/json", None, id="http-json")])
    def test_http_json(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param(None, None, id="unset")])
    def test_default(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        # OTel recommends HTTP/protobuf and permits retaining a historical gRPC default.
        assert expected_protocol in ("http/protobuf", "grpc")
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("", None, id="empty")])
    def test_empty(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param("unsupported", None, id="invalid")])
    def test_invalid(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(
                lambda signal, default: otel_env_var_utils.sdk_non_default(signal, default).upper(),
                None,
                id="uppercase",
            )
        ],
    )
    def test_case_insensitive(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(
                otel_env_var_utils.sdk_non_default,
                otel_env_var_utils.sdk_default,
                id="signal-nondefault-generic-default",
            )
        ],
    )
    def test_signal_precedence(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(
        ("protocol", "generic_protocol"),
        [
            pytest.param(None, otel_env_var_utils.sdk_non_default, id="unset-generic-nondefault"),
            pytest.param("", otel_env_var_utils.sdk_non_default, id="empty-generic-nondefault"),
        ],
    )
    def test_generic_fallback(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        _assert_export(test_library, test_agent, signal, expected_protocol)

    @pytest.mark.parametrize(("protocol", "generic_protocol"), [pytest.param(None, None, id="unset")])
    def test_documented_json_default(
        self, test_library: APMLibrary, test_agent: TestAgentAPI, signal: str, expected_protocol: str
    ) -> None:
        """Go documents HTTP/JSON as its logs default, independently of the OTel recommendation."""
        assert expected_protocol == "http/json"
        _assert_export(test_library, test_agent, signal, expected_protocol)

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars import utils as otel_env_var_utils
from tests.parametric.otel_env_vars.conftest import DefaultProtocol
from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest


VARIABLE = "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"
OTLP_TRACE_PATH = "/v1/traces"
ROUTING_HEADERS = "dd-protocol=otlp,dd-otlp-path=agent"
SPECIFICATION_DEFAULT = "http/protobuf"

BASE_ENVIRONMENT = {
    "DD_TRACE_AGENT_PROTOCOL_VERSION": None,
    "DD_TRACE_ENABLED": None,
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS": ROUTING_HEADERS,
    "OTEL_TRACES_EXPORTER": "otlp",
}

CONTENT_TYPES = {
    "http/protobuf": "application/x-protobuf",
    "http/json": "application/json",
}

GRPC_PROTOCOL_VALUE = [
    pytest.param({**BASE_ENVIRONMENT, VARIABLE: "grpc"}, id="grpc"),
]

HTTP_PROTOCOL_VALUES = [
    pytest.param({**BASE_ENVIRONMENT, VARIABLE: "http/protobuf"}, id="http-protobuf"),
    pytest.param({**BASE_ENVIRONMENT, VARIABLE: "http/json"}, id="http-json"),
]

UNSET_VALUE = [pytest.param({**BASE_ENVIRONMENT}, id="unset")]
EMPTY_VALUE = [pytest.param({**BASE_ENVIRONMENT, VARIABLE: ""}, id="empty")]


# default_protocol is the fixture from otel_env_vars/conftest.py that observes the SDK's default.
@pytest.fixture
def expected_protocol(library_env: dict[str, str], default_protocol: DefaultProtocol) -> str:
    return otel_env_var_utils.expected_protocol(None, library_env.get(VARIABLE), "traces", default_protocol)


@pytest.fixture(autouse=True)
def _trace_export_endpoint(
    library_env: dict[str, str],
    expected_protocol: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> None:
    if expected_protocol == "grpc":
        library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
            f"http://{test_agent.container_name}:{test_agent_otlp_grpc_port}"
        )
        return

    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
        f"http://{test_agent.container_name}:{test_agent_otlp_http_port}{OTLP_TRACE_PATH}"
    )


def _trace_request(test_agent: TestAgentAPI, test_library: APMLibrary) -> AgentRequest:
    with test_library as library:
        with library.dd_start_span(name="otel-otlp-traces-protocol"):
            pass
        library.dd_flush()

    requests = [request for request in test_agent.requests() if request["url"].endswith(OTLP_TRACE_PATH)]
    assert requests, f"Expected OTLP trace request, got {test_agent.requests()}"
    return requests[0]


def _assert_protocol(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    expected_protocol: str,
) -> None:
    request = _trace_request(test_agent, test_library)

    # The gRPC listener forwards decoded payloads internally over HTTP. A
    # successful export to its dedicated port proves gRPC; forwarded headers do
    # not represent the original gRPC wire format.
    if expected_protocol == "grpc":
        return

    headers = {name.lower(): value for name, value in request["headers"].items()}
    assert headers.get("content-type", "").startswith(CONTENT_TYPES[expected_protocol])


@scenarios.parametric
@features.otel_exporter_otlp_traces_protocol
class Test_OTEL_EXPORTER_OTLP_TRACES_PROTOCOL:
    @pytest.mark.parametrize("library_env", GRPC_PROTOCOL_VALUE)
    def test_grpc_protocol_is_used_for_trace_export(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

    @pytest.mark.parametrize("library_env", HTTP_PROTOCOL_VALUES)
    def test_http_protocol_is_used_for_trace_export(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_unset_uses_specification_default(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        assert expected_protocol == SPECIFICATION_DEFAULT
        _assert_protocol(test_agent, test_library, expected_protocol)

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

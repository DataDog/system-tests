import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest


OTLP_TRACE_PATH = "/v1/traces"
ROUTING_HEADERS = "dd-protocol=otlp,dd-otlp-path=agent"
DEFAULT_PROTOCOL = "http/protobuf"

BASE_ENVIRONMENT = {
    "DD_TRACE_AGENT_PROTOCOL_VERSION": None,
    "DD_TRACE_ENABLED": None,
    "DD_TRACE_OTEL_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS": ROUTING_HEADERS,
    "OTEL_TRACES_EXPORTER": "otlp",
}

CONTENT_TYPES = {
    "grpc": "application/grpc",
    "http/protobuf": "application/x-protobuf",
    "http/json": "application/json",
}

PROTOCOL_VALUES = [
    pytest.param({**BASE_ENVIRONMENT, "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "grpc"}, "grpc", id="grpc"),
    pytest.param(
        {**BASE_ENVIRONMENT, "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf"},
        "http/protobuf",
        id="http-protobuf",
    ),
    pytest.param(
        {**BASE_ENVIRONMENT, "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/json"},
        "http/json",
        id="http-json",
    ),
]

UNSET_VALUE = [pytest.param({**BASE_ENVIRONMENT}, DEFAULT_PROTOCOL, id="unset")]
EMPTY_VALUE = [
    pytest.param(
        {**BASE_ENVIRONMENT, "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": ""},
        DEFAULT_PROTOCOL,
        id="empty",
    )
]


@pytest.fixture(autouse=True)
def _trace_export_endpoint(
    library_env: dict[str, str],
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> None:
    protocol = library_env.get("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL") or DEFAULT_PROTOCOL
    if protocol == "grpc":
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
    headers = {name.lower(): value for name, value in request["headers"].items()}
    assert headers.get("content-type", "").startswith(CONTENT_TYPES[expected_protocol])


@scenarios.parametric
@features.otel_exporter_otlp_traces_protocol
class Test_OTEL_EXPORTER_OTLP_TRACES_PROTOCOL:
    @pytest.mark.parametrize(("library_env", "expected_protocol"), PROTOCOL_VALUES)
    def test_protocol_is_used_for_trace_export(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

    @pytest.mark.parametrize(("library_env", "expected_protocol"), UNSET_VALUE)
    def test_unset_uses_specification_default(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

    @pytest.mark.parametrize(("library_env", "expected_protocol"), EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_protocol: str,
    ) -> None:
        _assert_protocol(test_agent, test_library, expected_protocol)

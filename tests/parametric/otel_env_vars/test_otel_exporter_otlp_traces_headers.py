from tests.parametric.conftest import APMLibrary
from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest


VARIABLE = "OTEL_EXPORTER_OTLP_TRACES_HEADERS"

BASE_ENVIRONMENT = {
    "DD_TRACE_AGENT_PROTOCOL_VERSION": None,
    "DD_TRACE_ENABLED": None,
    "DD_TRACE_OTEL_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
    "OTEL_TRACES_EXPORTER": "otlp",
}


@pytest.fixture(autouse=True)
def _trace_export_endpoint(
    library_env: dict[str, str],
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
) -> None:
    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
        f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/v1/traces"
    )


def _trace_request(test_agent: TestAgentAPI, test_library: APMLibrary) -> AgentRequest:
    with test_library as library:
        with library.dd_start_span(name="otel-otlp-traces-headers"):
            pass
        library.dd_flush()

    requests = [request for request in test_agent.requests() if request["url"].endswith("/v1/traces")]
    assert requests, f"Expected OTLP trace request, got {test_agent.requests()}"
    return requests[0]


def _request_headers(request: AgentRequest) -> dict[str, str]:
    return {name.lower(): value for name, value in request["headers"].items()}


def _assert_routing_headers(headers: dict[str, str]) -> None:
    assert headers.get("dd-protocol") == "otlp"
    assert headers.get("dd-otlp-path") == "agent"


@scenarios.parametric
@features.otel_exporter_otlp_traces_headers
class Test_OTEL_EXPORTER_OTLP_TRACES_HEADERS:
    @pytest.mark.parametrize(
        ("library_env", "expected_headers"),
        [
            pytest.param(
                {
                    **BASE_ENVIRONMENT,
                    VARIABLE: "dd-protocol=otlp,dd-otlp-path=agent,header-one=value-one,header-two=value-two",
                },
                {"header-one": "value-one", "header-two": "value-two"},
                id="two-header-pairs",
            ),
        ],
    )
    def test_header_pairs_are_sent_on_trace_export(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_headers: dict[str, str],
    ) -> None:
        headers = _request_headers(_trace_request(test_agent, test_library))
        _assert_routing_headers(headers)
        for name, value in expected_headers.items():
            assert headers.get(name) == value, f"Expected {name}={value}, got {headers}"

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENVIRONMENT}, id="unset")])
    def test_unset_uses_global_headers(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        headers = _request_headers(_trace_request(test_agent, test_library))
        _assert_routing_headers(headers)
        assert all(name not in headers for name in ("header-one", "header-two"))

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENVIRONMENT, VARIABLE: ""}, id="empty")])
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        headers = _request_headers(_trace_request(test_agent, test_library))
        _assert_routing_headers(headers)
        assert all(name not in headers for name in ("header-one", "header-two"))

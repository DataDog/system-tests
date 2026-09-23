from typing import Final

import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


VARIABLE_NAME: Final = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
ROUTED_PATH: Final = "/otel-traces-endpoint"
DEFAULT_PATH: Final = "/v1/traces"
SPAN_NAME: Final = "otel-exporter-otlp-traces-endpoint"

TRACES_ENVIRONMENT: Final = {
    "DD_TRACE_AGENT_PROTOCOL_VERSION": None,
    "DD_TRACE_DEBUG": "false",
    "DD_TRACE_ENABLED": None,
    "OTEL_EXPORTER_OTLP_ENDPOINT": None,
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
    "OTEL_TRACES_EXPORTER": "otlp",
}

ENDPOINT_VALUES: Final = [
    pytest.param("routed", ROUTED_PATH, id="routed-signal-url"),
    pytest.param("unset", DEFAULT_PATH, id="unset"),
    pytest.param("empty", DEFAULT_PATH, id="empty"),
]


@pytest.fixture(autouse=True)
def _configure_endpoint(
    library_env: dict[str, str | None],
    endpoint_value: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
) -> None:
    library_env.update(TRACES_ENVIRONMENT)

    if endpoint_value == "routed":
        library_env[VARIABLE_NAME] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}{ROUTED_PATH}"
    elif endpoint_value == "unset":
        library_env[VARIABLE_NAME] = None
    else:
        library_env[VARIABLE_NAME] = ""


@scenarios.parametric
@features.otel_exporter_otlp_traces_endpoint
class Test_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:
    @pytest.mark.parametrize(("endpoint_value", "expected_path"), ENDPOINT_VALUES)
    def test_endpoint_is_used_as_is(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            with library.dd_start_span(name=SPAN_NAME):
                pass
            library.dd_flush()

        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"
DEFAULT_PATH = "/v1/logs"
LOGGER_NAME = "otel-exporter-otlp-logs-endpoint"
LOG_MESSAGE = "otel-exporter-otlp-logs-endpoint"
ROUTED_OTLP_HTTP_PORT = 4320

LOGS_ENVIRONMENT = {
    "DD_LOGS_OTEL_ENABLED": "true",
    "DD_TRACE_DEBUG": "false",
    "OTEL_EXPORTER_OTLP_ENDPOINT": None,
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
}

ROUTED_VALUES = [
    pytest.param("routed", DEFAULT_PATH, id="routed-signal-url"),
]

UNSET_VALUES = [
    pytest.param("unset", DEFAULT_PATH, id="unset"),
]

EMPTY_VALUES = [
    pytest.param("empty", DEFAULT_PATH, id="empty"),
]


@pytest.fixture(autouse=True)
def _configure_endpoint(
    library_env: dict[str, str | None],
    endpoint_value: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
) -> None:
    library_env.update(LOGS_ENVIRONMENT)

    if endpoint_value == "routed":
        library_env[VARIABLE_NAME] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}{DEFAULT_PATH}"
    elif endpoint_value == "unset":
        library_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
        library_env[VARIABLE_NAME] = None
    elif endpoint_value == "empty":
        library_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
        library_env[VARIABLE_NAME] = ""
    else:
        raise ValueError(f"Unexpected endpoint value: {endpoint_value}")


@scenarios.parametric
@features.otel_exporter_otlp_logs_endpoint
class Test_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT:
    @pytest.mark.parametrize(("endpoint_value", "expected_path"), ROUTED_VALUES)
    @pytest.mark.parametrize("test_agent_otlp_http_port", [ROUTED_OTLP_HTTP_PORT])
    def test_endpoint_is_used_as_is(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_agent_otlp_http_port: int,  # noqa: ARG002
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            library.create_logger(LOGGER_NAME, LogLevel.INFO)
            library.write_log(LOGGER_NAME, LogLevel.INFO, LOG_MESSAGE)

        test_agent.wait_for_num_log_payloads(num=1)
        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

    @pytest.mark.parametrize(("endpoint_value", "expected_path"), UNSET_VALUES)
    def test_unset_falls_back_to_global_endpoint(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            library.create_logger(LOGGER_NAME, LogLevel.INFO)
            library.write_log(LOGGER_NAME, LogLevel.INFO, LOG_MESSAGE)

        test_agent.wait_for_num_log_payloads(num=1)
        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

    @pytest.mark.parametrize(("endpoint_value", "expected_path"), EMPTY_VALUES)
    def test_empty_falls_back_to_global_endpoint(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            library.create_logger(LOGGER_NAME, LogLevel.INFO)
            library.write_log(LOGGER_NAME, LogLevel.INFO, LOG_MESSAGE)

        test_agent.wait_for_num_log_payloads(num=1)
        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

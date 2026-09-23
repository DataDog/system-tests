from typing import Final

import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


VARIABLE_NAME: Final = "OTEL_EXPORTER_OTLP_ENDPOINT"
ROUTED_PATH: Final = "/otel-global-endpoint/v1/metrics"
DEFAULT_PATH: Final = "/v1/metrics"
GRPC_PROTOCOL: Final = "grpc"

METRICS_ENVIRONMENT: Final = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "DD_RUNTIME_METRICS_ENABLED": "false",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000",
    "CORECLR_ENABLE_PROFILING": "1",
}

ENDPOINT_VALUES: Final = [
    pytest.param("routed", ROUTED_PATH, id="routed-base-url"),
    pytest.param("unset", DEFAULT_PATH, id="unset"),
    pytest.param("empty", DEFAULT_PATH, id="empty"),
]


@pytest.fixture(autouse=True)
def _configure_endpoint(
    library_env: dict[str, str | None],
    endpoint_value: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> None:
    library_env.update(METRICS_ENVIRONMENT)
    library_env["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = None

    if endpoint_value == "routed":
        library_env[VARIABLE_NAME] = (
            f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/otel-global-endpoint"
        )
    elif endpoint_value == "unset":
        library_env[VARIABLE_NAME] = None
    elif endpoint_value == "empty":
        library_env[VARIABLE_NAME] = ""
    else:
        library_env["OTEL_EXPORTER_OTLP_METRICS_PROTOCOL"] = None
        library_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = GRPC_PROTOCOL
        library_env[VARIABLE_NAME] = f"http://{test_agent.container_name}:{test_agent_otlp_grpc_port}/"


def _emit_metric(library: APMLibrary) -> None:
    meter_name = "otel-exporter-otlp-endpoint"
    counter_name = "otel-exporter-otlp-endpoint-counter"
    library.otel_get_meter(meter_name, "1.0.0", "", {})
    library.otel_create_counter(meter_name, counter_name, "", "")
    library.otel_counter_add(meter_name, counter_name, "", "", 1, {})
    library.otel_metrics_force_flush()


@scenarios.parametric
@features.otel_logs_enabled
@features.otel_metrics_api
@features.otel_exporter_otlp_endpoint
class Test_OTEL_EXPORTER_OTLP_ENDPOINT:
    @pytest.mark.parametrize(("endpoint_value", "expected_path"), ENDPOINT_VALUES)
    def test_endpoint_is_used_as_a_base_url(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            _emit_metric(library)

        test_agent.wait_for_num_otlp_metrics(num=1)
        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

    @pytest.mark.parametrize("endpoint_value", [pytest.param("grpc", id="grpc")])
    def test_otlp_custom_endpoint_grpc(
        self,
        library_env: dict[str, str | None],
        test_agent: TestAgentAPI,
        test_agent_otlp_grpc_port: int,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            _emit_metric(library)

        assert library_env[VARIABLE_NAME] == f"http://{test_agent.container_name}:{test_agent_otlp_grpc_port}/"
        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

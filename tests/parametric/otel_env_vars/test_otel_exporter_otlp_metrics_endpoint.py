from tests.parametric.conftest import APMLibrary
from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"
DEFAULT_PATH = "/v1/metrics"

METRICS_ENVIRONMENT = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "DD_RUNTIME_METRICS_ENABLED": "false",
    "OTEL_EXPORTER_OTLP_ENDPOINT": None,
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000",
    "CORECLR_ENABLE_PROFILING": "1",
}


@pytest.fixture(autouse=True)
def _configure_endpoint(
    library_env: dict[str, str | None],
    endpoint_value: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> None:
    library_env.update(METRICS_ENVIRONMENT)

    if endpoint_value == "routed":
        library_env[VARIABLE_NAME] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}{DEFAULT_PATH}"
    elif endpoint_value == "unset":
        library_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
        library_env[VARIABLE_NAME] = None
    elif endpoint_value == "empty":
        library_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
        library_env[VARIABLE_NAME] = ""
    elif endpoint_value == "grpc":
        library_env["OTEL_EXPORTER_OTLP_METRICS_PROTOCOL"] = None
        library_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "grpc"
        library_env[VARIABLE_NAME] = f"http://{test_agent.container_name}:{test_agent_otlp_grpc_port}/"
    else:
        raise ValueError(f"Unexpected endpoint value: {endpoint_value}")


def _emit_metric(library: APMLibrary) -> None:
    meter_name = "otel-exporter-otlp-metrics-endpoint"
    counter_name = "otel-exporter-otlp-metrics-endpoint-counter"
    library.otel_get_meter(meter_name, "1.0.0", "", {})
    library.otel_create_counter(meter_name, counter_name, "", "")
    library.otel_counter_add(meter_name, counter_name, "", "", 1, {})
    library.otel_metrics_force_flush()


@scenarios.parametric
@features.otel_exporter_otlp_metrics_endpoint
class Test_OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:
    @pytest.mark.parametrize(
        ("endpoint_value", "expected_path"), [pytest.param("routed", DEFAULT_PATH, id="routed-signal-url")]
    )
    @pytest.mark.parametrize("test_agent_otlp_http_port", [4320])
    def test_endpoint_is_used_as_is(
        self,
        endpoint_value: str,  # noqa: ARG002
        expected_path: str,
        test_agent: TestAgentAPI,
        test_agent_otlp_http_port: int,  # noqa: ARG002
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            _emit_metric(library)

        test_agent.wait_for_num_otlp_metrics(num=1)
        requests = test_agent.otlp_requests()
        assert any(request["url"].endswith(expected_path) for request in requests), requests

    @pytest.mark.parametrize(("endpoint_value", "expected_path"), [pytest.param("unset", DEFAULT_PATH, id="unset")])
    def test_unset_falls_back_to_global_endpoint(
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

    @pytest.mark.parametrize(("endpoint_value", "expected_path"), [pytest.param("empty", DEFAULT_PATH, id="empty")])
    def test_empty_falls_back_to_global_endpoint(
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
    def test_otlp_metrics_custom_endpoint_grpc(
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

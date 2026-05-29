import pytest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary


SPAN_DURATION_METRIC = "dd.trace.span.duration"

# Flush quickly so the client-computed stats are exported within the test window.
DEFAULT_ENVVARS = {
    "DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
    "OTEL_METRIC_EXPORT_INTERVAL": "1000",
    "DD_SERVICE": "test-otlp-stats-svc",
}


@pytest.fixture
def otlp_trace_metrics_library_env(library_env: dict[str, str], test_agent: TestAgentAPI):
    """Point the OTLP metrics exporter at the test agent's OTLP HTTP receiver."""
    library_env["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/metrics"
    yield library_env


def find_metric_by_name(scope_metric: dict, name: str) -> dict:
    for metric in scope_metric["metrics"]:
        if metric["name"] == name:
            return metric
    raise ValueError(f"Metric with name {name} not found")


@scenarios.parametric
@features.client_side_stats_supported
class Test_Otlp_Trace_Metrics:
    """Client-computed span stats are exported as the dd.trace.span.duration OTLP histogram."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_span_duration_histogram_exported(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        with test_library as t, t.dd_start_span(name="web.request", service="test-otlp-stats-svc", typestr="web"):
            pass

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics, "No scope metrics received"

        metric = find_metric_by_name(scope_metrics[0], SPAN_DURATION_METRIC)
        assert metric["unit"] == "s"
        histogram = metric["histogram"]
        assert str(histogram["aggregation_temporality"]).casefold() == "aggregation_temporality_delta"
        assert histogram["data_points"], "No data points in span duration histogram"

        resource_attrs = {
            item["key"]: item["value"]["string_value"]
            for item in metrics[0]["resource_metrics"][0]["resource"]["attributes"]
        }
        assert resource_attrs.get("service.name") == "test-otlp-stats-svc"

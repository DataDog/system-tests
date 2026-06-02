import time
from typing import Any

import pytest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import SPAN_MEASURED_KEY
from .conftest import APMLibrary


SPAN_DURATION_METRIC = "dd.trace.span.duration"
SERVICE = "test-otlp-stats-svc"
TRUTHY = ("yes", "true", "1")
# OTLP AggregationTemporality enum: DELTA == 1. Protobuf's canonical JSON mapping serializes enums
# as their string name (see https://protobuf.dev/programming-guides/json/), but parsers must also
# accept the integer, so a standards-compliant OTLP/JSON exporter may emit either representation.
AGGREGATION_TEMPORALITY_DELTA: tuple[int, str] = (1, "AGGREGATION_TEMPORALITY_DELTA")

# Common env shared by every test. The native OTLP stats worker ticks (and closes stat buckets)
# on the stats writer interval, and only releases buckets older than 2 intervals, so use a short
# interval to keep client-computed stats exported within the test window. The initial implementation only supports json export.
_BASE_ENVVARS = {
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/json",
    "OTEL_METRIC_EXPORT_INTERVAL": "1000",
    "_DD_TRACE_STATS_WRITER_INTERVAL": "1",
    "DD_SERVICE": SERVICE,
}

# OTLP trace metrics explicitly enabled.
DEFAULT_ENVVARS = {**_BASE_ENVVARS, "DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED": "true"}


@pytest.fixture
def otlp_trace_metrics_library_env(library_env: dict[str, str], test_agent: TestAgentAPI):
    """Point the OTLP metrics exporter at the test agent's OTLP HTTP receiver."""
    library_env["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/metrics"
    return library_env


def find_metric_by_name(scope_metric: dict, name: str) -> dict:
    for metric in scope_metric["metrics"]:
        if metric["name"] == name:
            return metric
    raise ValueError(f"Metric with name {name} not found")


def _attr_value(item: dict) -> Any:  # noqa: ANN401
    """Read an OTLP attribute value across the possible typed fields (OTLP/JSON uses camelCase)."""
    value = item["value"]
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return value["boolValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return value["doubleValue"]
    return None


def _data_point_attrs(data_point: dict) -> dict[str, Any]:
    return {item["key"]: _attr_value(item) for item in data_point.get("attributes", [])}


def _duration_data_points(metrics: list[Any]) -> list[dict]:
    """Collect dd.trace.span.duration data points across all captured payloads / resources / scopes."""
    data_points: list[dict] = []
    for payload in metrics:
        for resource_metric in payload["resourceMetrics"]:
            for scope_metric in resource_metric["scopeMetrics"]:
                for metric in scope_metric["metrics"]:
                    if metric["name"] == SPAN_DURATION_METRIC:
                        data_points.extend(metric.get("histogram", {}).get("dataPoints", []))
    return data_points


def _find_data_point(data_points: list[dict], **attrs: Any) -> dict | None:  # noqa: ANN401
    for data_point in data_points:
        point_attrs = _data_point_attrs(data_point)
        if all(point_attrs.get(key) == value for key, value in attrs.items()):
            return data_point
    return None


def _resource_attributes(metrics: list[Any]) -> dict[str, Any]:
    return {item["key"]: _attr_value(item) for item in metrics[0]["resourceMetrics"][0]["resource"]["attributes"]}


def _wait_for_v06_stats(test_agent: TestAgentAPI, *, wait_loops: int = 80) -> list[Any]:
    """Poll for client-computed v0.6 stats, which are flushed on the stats writer interval."""
    requests: list[Any] = []
    for _ in range(wait_loops):
        requests = test_agent.get_v06_stats_requests()
        if requests:
            return requests
        time.sleep(0.1)
    return requests


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR01_Enablement_Configuration:
    """FR01: OTLP trace metrics export is gated by configuration."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr01_1_enabled_explicit(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED=true exports the histogram."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _duration_data_points(metrics), "No span duration data points exported"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED": "false"}])
    def test_fr01_2_disabled_explicit(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED=false exports no OTLP trace metric."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [{**_BASE_ENVVARS, "OTEL_TRACES_EXPORTER": "otlp", "DD_METRICS_OTEL_ENABLED": "true"}],
    )
    def test_fr01_3_enabled_by_default(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """When unset, OTLP trace metrics are enabled if OTLP trace export and metrics export are both on."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _duration_data_points(metrics), "No span duration data points exported"

    @pytest.mark.parametrize(
        "library_env",
        [{**_BASE_ENVVARS, "OTEL_TRACES_EXPORTER": "otlp", "DD_METRICS_OTEL_ENABLED": "false"}],
    )
    def test_fr01_4_disabled_when_metrics_export_off(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """When unset, OTLP trace metrics stay disabled if metrics export is off."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR02_Mutual_Exclusion:
    """FR02: Trace metrics are exported in exactly one format to avoid double counting."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr02_1_otlp_suppresses_native_stats(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """With OTLP enabled: metrics go to /v1/metrics, no native v0.6 stats, and traces carry the
        Datadog-Client-Computed-Stats header so the Agent skips server-side stats computation.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        test_agent.wait_for_num_otlp_metrics(num=1)
        assert not test_agent.get_v06_stats_requests(), "Native v0.6 stats must not be sent when OTLP is enabled"

        trace_requests = [
            r for r in test_agent.requests() if r["url"].endswith(("/v0.4/traces", "/v0.5/traces", "/v0.7/traces"))
        ]
        assert trace_requests, "Expected at least one trace export request"
        headers = {h.lower(): v for h, v in trace_requests[0]["headers"].items()}
        assert headers.get("datadog-client-computed-stats", "").lower() in TRUTHY, (
            f"Expected Datadog-Client-Computed-Stats to be truthy, got headers: {headers}"
        )

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **_BASE_ENVVARS,
                "DD_TRACE_OTEL_STATS_COMPUTATION_ENABLED": "false",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
            }
        ],
    )
    def test_fr02_2_native_stats_no_otlp(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """With OTLP disabled and native stats enabled: stats go to /v0.6/stats, no OTLP metrics."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        assert _wait_for_v06_stats(test_agent), "Native v0.6 stats should be sent when OTLP is disabled"
        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR03_Metric_Shape:
    """FR03: The exported metric is a single delta-temporality histogram named dd.trace.span.duration."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_1_single_histogram_metric(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Exactly one metric is exported: dd.trace.span.duration of kind Histogram."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resourceMetrics"][0]["scopeMetrics"]
        assert scope_metrics, "No scope metrics received"
        assert len(scope_metrics[0]["metrics"]) == 1
        metric = find_metric_by_name(scope_metrics[0], SPAN_DURATION_METRIC)
        assert "histogram" in metric

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_2_unit_seconds(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The histogram unit is seconds and the duration sum is expressed in seconds (not nanoseconds)."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resourceMetrics"][0]["scopeMetrics"]
        metric = find_metric_by_name(scope_metrics[0], SPAN_DURATION_METRIC)
        assert metric["unit"] == "s"
        data_point = metric["histogram"]["dataPoints"][0]
        # A near-instant span is well under a second; a nanosecond value would be enormous.
        assert 0 < float(data_point["sum"]) < 60, f"Duration sum not in seconds: {data_point['sum']}"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_3_delta_temporality(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The histogram uses delta aggregation temporality."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resourceMetrics"][0]["scopeMetrics"]
        histogram = find_metric_by_name(scope_metrics[0], SPAN_DURATION_METRIC)["histogram"]
        # Accept the integer or the Protobuf JSON enum name, since either is standards-compliant.
        assert histogram["aggregationTemporality"] in AGGREGATION_TEMPORALITY_DELTA

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_4_scope(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The instrumentation scope is dd-trace with the tracer version."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope = metrics[0]["resourceMetrics"][0]["scopeMetrics"][0]["scope"]
        assert scope["name"] == "dd-trace"
        assert scope.get("version"), "Scope version should be set to the tracer version"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_5_data_point_consistency(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A single span yields an internally consistent data point."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        data_points = _duration_data_points(metrics)
        assert len(data_points) == 1
        data_point = data_points[0]
        assert int(data_point["count"]) == 1
        assert float(data_point["sum"]) > 0
        assert data_point["min"] == data_point["max"]
        assert sum(int(count) for count in data_point["bucketCounts"]) == 1


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR04_Dimension_Mapping:
    """FR04: Datadog aggregation-key fields map to the expected OTel / Datadog attributes."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_1_service(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Service maps to the resource attribute service.name."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _resource_attributes(metrics).get("service.name") == SERVICE

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_2_resource(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Resource maps to the data-point attribute span.name."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, resource="/users", typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("span.name") == "/users"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_3_operation_name(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Operation name maps to the data-point attribute dd.operation.name."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.operation.name") == "web.request"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_4_type(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Type maps to the data-point attribute dd.span.type."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.span.type") == "web"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_5_http_status_code(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http status code maps to the data-point attribute http.response.status_code."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("http.status_code", "200")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.response.status_code") == 200

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_6_http_method(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http method maps to the data-point attribute http.request.method."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("http.method", "GET")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.request.method") == "GET"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_7_http_route(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http endpoint maps to the data-point attribute http.route."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("http.route", "/users/{id}")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.route") == "/users/{id}"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_8_synthetics(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Synthetics origin maps to the data-point attribute dd.synthetics."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("_dd.origin", "synthetics")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.synthetics") is True


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR05_Error_Tagging:
    """FR05: Error spans are tagged with error=true; ok spans omit the error attribute."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr05_1_error_span(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """An error span produces a data point carrying error=true."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_error(message="boom")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        data_point = _find_data_point(_duration_data_points(metrics), error=True)
        assert data_point is not None, "No data point with error=true"
        assert int(data_point["count"]) == 1

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr05_2_ok_span(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A successful span omits the error attribute entirely."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert "error" not in _data_point_attrs(_duration_data_points(metrics)[0])


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR06_Top_Level_Tagging:
    """FR06: dd.top_level reflects whether a span is a service-entry (top-level) span."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_1_root(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A single root span is top-level."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.top_level") is True

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_2_child_same_service(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A child span with the same service as its parent is not top-level.

        The child is marked measured so it is emitted (a non-top-level, non-measured span is filtered
        out per FR07.2); the assertion verifies it carries dd.top_level=false.
        """
        with test_library as t:
            with (
                t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as parent,
                t.dd_start_span(name="child.op", service=SERVICE, parent_id=parent.span_id) as child,
            ):
                child.set_metric(SPAN_MEASURED_KEY, 1)
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        child_point = _find_data_point(_duration_data_points(metrics), **{"dd.operation.name": "child.op"})
        assert child_point is not None, "No data point for the child span"
        assert _data_point_attrs(child_point).get("dd.top_level") is False

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_3_child_different_service(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A child span with a different service is a service-entry (top-level) span."""
        with test_library as t:
            with (
                t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as parent,
                t.dd_start_span(name="postgres.query", service="postgres", parent_id=parent.span_id),
            ):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        child = _find_data_point(_duration_data_points(metrics), **{"dd.operation.name": "postgres.query"})
        assert child is not None, "No data point for the child span"
        assert _data_point_attrs(child).get("dd.top_level") is True


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR07_Span_Filtering:
    """FR07: Only top-level or measured spans contribute data points."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr07_1_measured_child(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A non-top-level child marked measured produces a data point with dd.top_level=false."""
        with test_library as t:
            with (
                t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as parent,
                t.dd_start_span(name="child.op", service=SERVICE, parent_id=parent.span_id) as child,
            ):
                child.set_metric(SPAN_MEASURED_KEY, 1)
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        child_point = _find_data_point(_duration_data_points(metrics), **{"dd.operation.name": "child.op"})
        assert child_point is not None, "Measured child span should produce a data point"
        assert _data_point_attrs(child_point).get("dd.top_level") is False

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr07_2_unmeasured_child(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A non-top-level, non-measured child is excluded; only the root produces a data point."""
        with test_library as t:
            with (
                t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as parent,
                t.dd_start_span(name="child.op", service=SERVICE, parent_id=parent.span_id),
            ):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        data_points = _duration_data_points(metrics)
        assert _find_data_point(data_points, **{"dd.operation.name": "child.op"}) is None
        assert _find_data_point(data_points, **{"dd.operation.name": "web.request"}) is not None


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR08_Resource_Attributes:
    """FR08: Environment configuration is mapped onto OTLP resource attributes."""

    @pytest.mark.parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_ENV": "prod", "DD_VERSION": "1.2.3"}],
    )
    def test_fr08_1_service_env_version(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """DD_SERVICE / DD_ENV / DD_VERSION map to service.name / deployment.environment / service.version."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        attrs = _resource_attributes(metrics)
        assert attrs.get("service.name") == SERVICE
        assert attrs.get("service.version") == "1.2.3"
        # The deployment environment semantic convention was renamed in 1.27.0.
        assert attrs.get("deployment.environment") == "prod" or attrs.get("deployment.environment.name") == "prod"

    @pytest.mark.parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_HOSTNAME": "ddhostname", "DD_TRACE_REPORT_HOSTNAME": "true"}],
    )
    def test_fr08_2_hostname(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """host.name is set from DD_HOSTNAME when hostname reporting is enabled."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _resource_attributes(metrics).get("host.name") == "ddhostname"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_HOSTNAME": "ddhostname"}])
    def test_fr08_3_hostname_omitted(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """host.name is omitted when hostname reporting is not enabled."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert "host.name" not in _resource_attributes(metrics)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR09_Sampling_Independence:
    """FR09: Trace metrics are computed before head-based sampling, from 100% of spans."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_TRACE_SAMPLING_RULES": '[{"sample_rate": 0}]'}])
    def test_fr09_1_metrics_computed_before_sampling(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """With sample rate 0 the trace is dropped, yet the histogram is still emitted with count=1."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        data_points = _duration_data_points(metrics)
        assert len(data_points) == 1
        assert int(data_points[0]["count"]) == 1

        assert len(test_agent.traces()) == 0, "No traces should be exported with sample rate 0"

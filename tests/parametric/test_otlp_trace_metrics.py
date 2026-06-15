"""System tests for the RFC "OTLP Trace Metrics Export" (SEMCON-1093).

Each test class maps to a functional requirement (FR) from the RFC. A single behaviour is
exercised per test, generating 1-3 spans and asserting on the captured telemetry (OTLP metrics
sent to /v1/metrics, plus native Datadog v0.4/v0.5/v0.6 traces and stats where relevant).

FR -> test-class mapping:
  FR01  Enable/disable with OTEL_CLIENT_STATS_COMPUTATION_ENABLED        Test_FR01_Enablement_Configuration
  FR02  Exactly one histogram named traces.span.sdk.metrics.duration;    Test_FR02_Metric_Identity
        no trace.<name>.* / SMC names via OTLP                           Test_FR02_Mutual_Exclusion (XOR with native stats)
  FR03  Delta-temporality histogram, unit "s", OTLP format               Test_FR03_Metric_Shape
  FR04  Reuse existing client-side stats span-selection                  Test_FR04_Span_Selection
  FR05  Computed before head-based sampling                              Test_FR05_Sampling_Independence
  FR06  OTel semantic-convention attributes wherever applicable          Test_FR06_Otel_Span_Attributes,
                                                                         Test_FR06_Otel_Resource_Attributes
  FR07  DD_TRACE_OTEL_SEMANTICS_ENABLED=true -> only OTel attributes      Test_FR07_Otel_Semantics_Mode
  FR08  DD_TRACE_OTEL_SEMANTICS_ENABLED=false (default) -> dd.* allowed   Test_FR08_Datadog_Attributes
  FR09  Derive request/span count, error count, and duration             Test_FR09_Red_Metric_Derivation
  FR10  Transport over OTLP HTTP/JSON (set in _BASE_ENVVARS, exercised by every test)
  FR11  SDKs without client-side stats are out of scope (handled by manifests / @features gating)
  FR12-FR14  Backend ingestion / billing -> no SDK system-test coverage

Key conventions:
  * Top-level marker is dd.span.top_level.
  * Error is conveyed via the OTel status.code attribute; it works in OTel-semantics mode where dd.* and
    other bespoke attributes are disallowed.
  * Resource name is the OTel span.name attribute in both modes; dd.resource.name is not emitted.
  * The emitter is identified by the resource attributes telemetry.sdk.name ("datadog") and
    telemetry.sdk.language (the library's OTel language token, e.g. "go" for golang).
  * service.name, service.version and deployment.environment.name are reported as resource attributes
    (the configured default service). All data points share a single InstrumentationScope; a span whose
    service differs from the configured default additionally carries service.name on its data point.
  * OTLP metric flush/export cadence is fixed at 10s and is not overridable by OTEL_METRIC_EXPORT_INTERVAL.
    The internal _DD_TRACE_METRICS_OTEL_FLUSH_INTERVAL (milliseconds) shortens it in tests only.
  * Transport differs per library and is out of scope for parity: dd-trace-py exports HTTP/JSON only,
    while dd-trace-js supports both HTTP/JSON and HTTP/protobuf. Tests pin HTTP/JSON via _BASE_ENVVARS.

Datadog span tags are translated to OTel semantic-convention attributes on the exported metric:
grpc.method.name -> rpc.method, grpc.status.code -> rpc.response.status_code, http.method -> http.request.method,
http.status_code -> http.response.status_code, and span.kind -> span.kind. host.name is set from DD_HOSTNAME
when DD_TRACE_REPORT_HOSTNAME is enabled. Process tags (DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED) are
emitted as dd.<key> resource attributes in default mode. Boolean and status-code attributes are accepted as
native or stringified values.
"""

from typing import Any

import pytest

from utils import context, features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import SPAN_MEASURED_KEY
from .conftest import APMLibrary


SPAN_DURATION_METRIC = "traces.span.sdk.metrics.duration"
# OpenTelemetry Span Metrics Connector output that this metric MUST NOT collide with (FR02).
SMC_METRIC_NAMES = ("traces.span.metrics.calls", "traces.span.metrics.duration")
SERVICE = "test-otlp-stats-svc"
TRUTHY = ("yes", "true", "1")
FALSY = ("no", "false", "0")
# HTTP / RPC status codes may be serialized as an int or a string attribute value.
HTTP_OK_VALUES: tuple[Any, ...] = (200, "200")
RPC_OK_VALUES: tuple[Any, ...] = (0, "0")
# OTLP AggregationTemporality enum: DELTA == 1. Protobuf's canonical JSON mapping serializes enums
# as their string name (see https://protobuf.dev/programming-guides/json/), but parsers must also
# accept the integer, so a standards-compliant OTLP/JSON exporter may emit either representation.
AGGREGATION_TEMPORALITY_DELTA: tuple[int, str] = (1, "AGGREGATION_TEMPORALITY_DELTA")
# OTel StatusCode (span status) values that denote an error, across possible serializations.
ERROR_STATUS_VALUES: tuple[Any, ...] = (2, "ERROR", "STATUS_CODE_ERROR")
# Expected telemetry.sdk.language resource-attribute value per system-tests library name. The Go
# tracer reports the OTel-standard "go" token rather than the system-tests "golang" library name.
_SDK_LANGUAGE_BY_LIBRARY = {
    "python": "python",
    "nodejs": "nodejs",
    "dotnet": "dotnet",
    "java": "java",
    "golang": "go",
    "ruby": "ruby",
    "php": "php",
    "rust": "rust",
    "cpp": "cpp",
}
# Known process-tag keys; any one emitted as a dd.<key> resource attribute satisfies FR08. Which tags
# are populated varies per library/runtime, so the test only requires that at least one is present.
_PROCESS_TAG_KEYS = (
    "entrypoint.name",
    "entrypoint.workdir",
    "entrypoint.type",
    "entrypoint.basedir",
    "svc.user",
    "svc.auto",
)

# Common env shared by every test. The OTLP trace-metrics flush cadence is fixed at 10s and is not
# driven by OTEL_METRIC_EXPORT_INTERVAL; the internal _DD_TRACE_METRICS_OTEL_FLUSH_INTERVAL
# (milliseconds) shortens it so metrics export within the test window. On-demand flushes still occur
# via t.dd_flush(). Tests pin HTTP/JSON export (FR10), the transport common to all libraries.
_BASE_ENVVARS = {
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/json",
    "_DD_TRACE_METRICS_OTEL_FLUSH_INTERVAL": "1000",
    "DD_SERVICE": SERVICE,
}

# OTLP trace metrics explicitly enabled. DD_TRACE_OTEL_SEMANTICS_ENABLED is unset, so this is the
# default Datadog mode where dd.* attributes are emitted alongside OTel attributes (FR08).
DEFAULT_ENVVARS = {**_BASE_ENVVARS, "OTEL_CLIENT_STATS_COMPUTATION_ENABLED": "true"}

# OTel-semantics mode: only OpenTelemetry attributes are emitted, no dd.* attributes (FR07).
OTEL_SEMANTICS_ENVVARS = {**DEFAULT_ENVVARS, "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true"}


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


def _all_metric_names(metrics: list[Any]) -> list[str]:
    """Collect every metric name across captured payloads / resources / scopes."""
    names: list[str] = []
    for payload in metrics:
        for resource_metric in payload["resourceMetrics"]:
            for scope_metric in resource_metric["scopeMetrics"]:
                for metric in scope_metric["metrics"]:
                    names.append(metric["name"])
    return names


def _duration_data_points(metrics: list[Any]) -> list[dict]:
    """Collect traces.span.sdk.metrics.duration data points across all payloads / resources / scopes."""
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


def _scopes(metrics: list[Any]) -> list[dict]:
    """Collect every InstrumentationScope across all payloads / resources."""
    scopes: list[dict] = []
    for payload in metrics:
        for resource_metric in payload["resourceMetrics"]:
            for scope_metric in resource_metric["scopeMetrics"]:
                scopes.append(scope_metric.get("scope", {}))
    return scopes


def _data_point_services(metrics: list[Any]) -> set[Any]:
    """Collect every service.name carried on a duration data point (custom/non-default services)."""
    services: set[Any] = set()
    for data_point in _duration_data_points(metrics):
        service = _data_point_attrs(data_point).get("service.name")
        if service is not None:
            services.add(service)
    return services


def _attr_is_true(value: Any) -> bool:  # noqa: ANN401
    """A boolean OTLP attribute may be a native bool or a stringified "true"."""
    return value is True or (isinstance(value, str) and value.lower() in TRUTHY)


def _attr_is_false(value: Any) -> bool:  # noqa: ANN401
    return value is False or (isinstance(value, str) and value.lower() in FALSY)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR01_Enablement_Configuration:
    """FR01: OTLP trace metrics export is gated by OTEL_CLIENT_STATS_COMPUTATION_ENABLED."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr01_1_enabled_explicit(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """OTEL_CLIENT_STATS_COMPUTATION_ENABLED=true exports the histogram."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _duration_data_points(metrics), "No span duration data points exported"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "OTEL_CLIENT_STATS_COMPUTATION_ENABLED": "false"}])
    def test_fr01_2_disabled_explicit(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """OTEL_CLIENT_STATS_COMPUTATION_ENABLED=false exports no OTLP trace metric."""
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

    @pytest.mark.parametrize(
        "library_env",
        [{**_BASE_ENVVARS, "OTEL_TRACES_EXPORTER": "none", "DD_METRICS_OTEL_ENABLED": "true"}],
    )
    def test_fr01_5_disabled_when_traces_exporter_not_otlp(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """When unset, OTLP trace metrics stay disabled if OTLP trace export is off (the other AND branch)."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR02_Metric_Identity:
    """FR02: Exactly one histogram named traces.span.sdk.metrics.duration; no native or SMC names."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr02_1_single_named_histogram(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Exactly one metric is exported: traces.span.sdk.metrics.duration of kind Histogram."""
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
    def test_fr02_2_no_native_or_smc_metric_names(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """No trace.<name>.* (Datadog-native) or SMC metric names are emitted through OTLP."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        names = _all_metric_names(metrics)
        assert SPAN_DURATION_METRIC in names
        assert not any(name in SMC_METRIC_NAMES for name in names), f"SMC metric name emitted via OTLP: {names}"
        assert not any(name.startswith("trace.") for name in names), f"Native trace metric emitted via OTLP: {names}"


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR02_Mutual_Exclusion:
    """FR02: Trace metrics are exported in exactly one path (OTLP XOR native v0.6 stats)."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr02_3_otlp_suppresses_native_stats(
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
                "OTEL_CLIENT_STATS_COMPUTATION_ENABLED": "false",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
            }
        ],
    )
    def test_fr02_4_native_stats_no_otlp(
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

        assert test_agent.wait_for_num_v06_stats(num=1), "Native v0.6 stats should be sent when OTLP is disabled"
        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR03_Metric_Shape:
    """FR03: The exported metric is a delta-temporality histogram with unit "s"."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr03_1_unit_seconds(
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
    def test_fr03_2_delta_temporality(
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


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR04_Span_Selection:
    """FR04: Only spans selected by the existing client-side stats pipeline are emitted."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_1_measured_child_selected(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A non-top-level child marked measured is selected and produces a data point."""
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

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr04_2_unmeasured_child_excluded(
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
class Test_FR05_Sampling_Independence:
    """FR05: Trace metrics are computed before head-based sampling, from 100% of spans."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_TRACE_SAMPLING_RULES": '[{"sample_rate": 0}]'}])
    def test_fr05_1_metrics_computed_before_sampling(
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


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR06_Otel_Span_Attributes:
    """FR06: Span dimensions map to OTel semantic-convention data-point attributes (both modes)."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_1_resource_span_name(
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
    def test_fr06_2_span_kind(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Span kind maps to the data-point attribute span.kind."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                # Source span tag is a tracer-specific assumption; the spec only fixes the emitted OTel key.
                span.set_meta("span.kind", "server")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("span.kind") == "server"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_3_http_method(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http method maps to the data-point attribute http.request.method."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                # Source span tag (http.method) is a tracer-specific assumption; the spec only fixes the OTel key.
                span.set_meta("http.method", "GET")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.request.method") == "GET"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_4_http_status_code(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http status code maps to the data-point attribute http.response.status_code."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                # Source span tag (http.status_code) is a tracer-specific assumption; the spec only fixes
                # the emitted OTel key. Accept int or stringified serialization of the value.
                span.set_meta("http.status_code", "200")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.response.status_code") in HTTP_OK_VALUES

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_5_http_route(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Http route maps to the data-point attribute http.route."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("http.route", "/users/{id}")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("http.route") == "/users/{id}"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_6_rpc_method(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The Datadog gRPC span tag grpc.method.name is translated to the OTel attribute rpc.method."""
        with test_library as t:
            with t.dd_start_span(name="grpc.request", service=SERVICE, typestr="grpc") as span:
                # Datadog gRPC instrumentation tag; the OTLP export translates it to OTel semantics (rpc.method).
                span.set_meta("grpc.method.name", "GetUser")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("rpc.method") == "GetUser"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_7_rpc_status_code(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The Datadog gRPC span tag grpc.status.code is translated to OTel rpc.response.status_code."""
        with test_library as t:
            with t.dd_start_span(name="grpc.request", service=SERVICE, typestr="grpc") as span:
                # gRPC status code 0 == OK. Datadog gRPC instrumentation tag; the OTLP export translates it
                # to OTel semantics (rpc.response.status_code). Accept int or string serialization.
                span.set_meta("grpc.status.code", "0")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("rpc.response.status_code") in RPC_OK_VALUES

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_8_status_code_error(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """An error span carries the OTel status.code attribute indicating an error."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_error(message="boom")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("status.code") in ERROR_STATUS_VALUES


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR06_Otel_Resource_Attributes:
    """FR06: Environment configuration maps to OTel resource attributes."""

    @pytest.mark.parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_ENV": "prod", "DD_VERSION": "1.2.3"}],
    )
    def test_fr06_9_service_env_version(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """DD_SERVICE / DD_ENV / DD_VERSION map to the resource attributes service.name /
        deployment.environment.name / service.version. The single InstrumentationScope carries no
        service identity, and the span uses the default service so its data point omits service.name.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        resource_attrs = _resource_attributes(metrics)
        assert resource_attrs.get("service.name") == SERVICE
        assert resource_attrs.get("service.version") == "1.2.3"
        # The deployment environment semantic convention was renamed in 1.27.0.
        assert (
            resource_attrs.get("deployment.environment") == "prod"
            or resource_attrs.get("deployment.environment.name") == "prod"
        )
        # Service identity lives on the resource, not the scope.
        for scope in _scopes(metrics):
            scope_keys = {item["key"] for item in scope.get("attributes", [])}
            assert "service.name" not in scope_keys, f"service.name must not be a scope attribute: {scope_keys}"
        # The span uses the configured default service, so its data point omits service.name.
        assert SERVICE not in _data_point_services(metrics)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_14_custom_service_on_data_point(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """All data points share a single InstrumentationScope. A span whose service matches the
        configured default omits service.name on its data point (it is implied by the resource); a
        span on a different service carries service.name on its data point. Two root spans are used
        so both are top-level and therefore selected by the client-side stats pipeline in every
        library.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            with t.dd_start_span(name="db.query", service="postgres", typestr="db"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        # The configured default service is reported on the resource.
        assert _resource_attributes(metrics).get("service.name") == SERVICE
        services_on_points = _data_point_services(metrics)
        # The custom service is carried on its own data point; the default service is not repeated.
        assert "postgres" in services_on_points, (
            f"Expected postgres service.name on its data point: {services_on_points}"
        )
        assert SERVICE not in services_on_points, (
            f"Default service must not repeat on data points: {services_on_points}"
        )

    @pytest.mark.parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_HOSTNAME": "ddhostname", "DD_TRACE_REPORT_HOSTNAME": "true"}],
    )
    def test_fr06_10_hostname(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """host.name is set from DD_HOSTNAME when hostname reporting is enabled.

        The spec only requires host.name "where available and allowed"; DD_HOSTNAME + DD_TRACE_REPORT_HOSTNAME
        gating is a tracer policy assumption rather than a spec mandate, and may differ per library.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _resource_attributes(metrics).get("host.name") == "ddhostname"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_HOSTNAME": "ddhostname"}])
    def test_fr06_11_hostname_omitted(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """host.name is omitted when hostname reporting is not enabled.

        Encodes the tracer policy that a configured DD_HOSTNAME is not leaked onto the metric resource
        unless reporting is explicitly enabled; the spec itself only says host.name appears where allowed.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert "host.name" not in _resource_attributes(metrics)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_12_telemetry_sdk_name(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The telemetry.sdk.name resource attribute identifies the Datadog SDK as the emitter."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _resource_attributes(metrics).get("telemetry.sdk.name") == "datadog"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr06_13_telemetry_sdk_language(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """The telemetry.sdk.language resource attribute is set to the library's OTel language token."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        expected_language = _SDK_LANGUAGE_BY_LIBRARY[context.library.name]
        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _resource_attributes(metrics).get("telemetry.sdk.language") == expected_language


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR07_Otel_Semantics_Mode:
    """FR07: With DD_TRACE_OTEL_SEMANTICS_ENABLED=true, only OTel attributes are emitted."""

    @pytest.mark.parametrize("library_env", [{**OTEL_SEMANTICS_ENVVARS}])
    def test_fr07_1_no_datadog_attributes(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """No dd.* prefixed attributes are emitted on the data point in OTel-semantics mode."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, resource="/users", typestr="web") as span:
                span.set_meta("_dd.origin", "synthetics")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        attrs = _data_point_attrs(_duration_data_points(metrics)[0])
        dd_keys = [key for key in attrs if key.startswith("dd.")]
        assert not dd_keys, f"dd.* attributes must not be emitted in OTel-semantics mode: {dd_keys}"

    @pytest.mark.parametrize("library_env", [{**OTEL_SEMANTICS_ENVVARS}])
    def test_fr07_2_no_datadog_resource_or_type(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Resource is carried by span.name (not dd.resource.name) and dd.span.type is absent."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, resource="/users", typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        attrs = _data_point_attrs(_duration_data_points(metrics)[0])
        assert attrs.get("span.name") == "/users"
        assert "dd.resource.name" not in attrs
        assert "dd.span.type" not in attrs
        assert "dd.operation.name" not in attrs

    @pytest.mark.parametrize("library_env", [{**OTEL_SEMANTICS_ENVVARS}])
    def test_fr07_3_otel_attributes_present(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """OTel semantic-convention attributes are still emitted in OTel-semantics mode."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("http.method", "GET")
                span.set_meta("http.route", "/users/{id}")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        attrs = _data_point_attrs(_duration_data_points(metrics)[0])
        assert attrs.get("http.request.method") == "GET"
        assert attrs.get("http.route") == "/users/{id}"

    @pytest.mark.parametrize(
        "library_env",
        [{**OTEL_SEMANTICS_ENVVARS, "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true"}],
    )
    def test_fr07_4_no_datadog_resource_attributes(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """No dd.* resource attributes are emitted in OTel-semantics mode (process tags must not leak)."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        dd_keys = [key for key in _resource_attributes(metrics) if key.startswith("dd.")]
        assert not dd_keys, f"dd.* resource attributes must not be emitted in OTel-semantics mode: {dd_keys}"


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR08_Datadog_Attributes:
    """FR08: In default mode (DD_TRACE_OTEL_SEMANTICS_ENABLED=false) dd.* attributes are added."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_1_operation_name(
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
    def test_fr08_2_span_type(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Span type maps to the data-point attribute dd.span.type."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.span.type") == "web"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_3_top_level_root(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A single root span carries dd.span.top_level=true."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _attr_is_true(_data_point_attrs(_duration_data_points(metrics)[0]).get("dd.span.top_level"))

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_4_top_level_child_same_service(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A child span with the same service as its parent carries dd.span.top_level=false.

        The child is marked measured so it is emitted (a non-top-level, non-measured span is filtered
        out per FR04); the assertion verifies it carries dd.span.top_level=false.
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
        assert _attr_is_false(_data_point_attrs(child_point).get("dd.span.top_level"))

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_5_top_level_child_different_service(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A child span with a different service is a service-entry span: dd.span.top_level=true."""
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
        assert _attr_is_true(_data_point_attrs(child).get("dd.span.top_level"))

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_6_origin(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Origin maps to the data-point attribute dd.origin."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as span:
                span.set_meta("_dd.origin", "synthetics")
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        assert _data_point_attrs(_duration_data_points(metrics)[0]).get("dd.origin") == "synthetics"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr08_7_no_datadog_prefix(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """datadog.* attributes must not be emitted (dd.* is the only Datadog prefix allowed)."""
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, resource="/users", typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        attrs = _data_point_attrs(_duration_data_points(metrics)[0])
        datadog_keys = [key for key in attrs if key.startswith("datadog.")]
        assert not datadog_keys, f"datadog.* attributes must not be emitted: {datadog_keys}"

    @pytest.mark.parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS, "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true"}],
    )
    def test_fr08_8_process_tags(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Process tags are emitted as individual dd.<key> resource attributes in default mode.

        The comma-separated key:value process-tag string is split and each key is prefixed with dd. and
        emitted as a resource attribute. Which process tags are populated varies per library/runtime, so
        the assertion only requires that at least one known process tag is present as a dd.<key> attribute.
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        resource_attrs = _resource_attributes(metrics)
        assert any(f"dd.{tag}" in resource_attrs for tag in _PROCESS_TAG_KEYS), (
            f"Expected at least one dd.<process-tag> resource attribute, got: {list(resource_attrs)}"
        )


@scenarios.parametric
@features.client_side_stats_supported
class Test_FR09_Red_Metric_Derivation:
    """FR09: The histogram provides enough information to derive count, error count, and duration."""

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr09_1_data_point_consistency(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """A single span yields an internally consistent data point (count / sum / min / max / buckets)."""
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

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_fr09_2_error_count(
        self,
        otlp_trace_metrics_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Error count is derivable: with one error and one ok span, errors = 1 of 2 total.

        The error span carries an ERROR status.code while the ok span does not, so the backend can derive
        error count from the subset of data points whose status.code indicates an error (OK / UNSET merge
        into a single non-error state).
        """
        with test_library as t:
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web") as err:
                err.set_error(message="boom")
            with t.dd_start_span(name="web.request", service=SERVICE, typestr="web"):
                pass
            t.dd_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        data_points = _duration_data_points(metrics)
        total = sum(int(dp["count"]) for dp in data_points)
        error_count = sum(
            int(dp["count"]) for dp in data_points if _data_point_attrs(dp).get("status.code") in ERROR_STATUS_VALUES
        )
        assert total == 2, f"Expected 2 selected spans, got {total}"
        assert error_count == 1, f"Expected exactly one error span, got {error_count}"

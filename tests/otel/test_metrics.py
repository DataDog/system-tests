import time

from utils import context, weblog, interfaces, scenarios, irrelevant, features
from collections.abc import Callable


def validate_resource_metrics(resource_metrics_list: list) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message ResourceMetrics {
    #     optional opentelemetry.proto.resource.v1.Resource resource = 1;
    #     repeated ScopeMetrics scope_metrics = 2;
    #     optional string schema_url = 3;
    # }

    assert all(
        len(resource_metrics) == 1 for resource_metrics in resource_metrics_list
    ), "Metrics payloads from one configured application should have one set of resource metrics"
    assert any(
        "scopeMetrics" in resource_metrics[0] and len(resource_metrics[0]["scopeMetrics"]) > 0
        for resource_metrics in resource_metrics_list
    ), "Scope metrics should be present on some payloads"
    assert all(
        resource_metrics[0]["resource"] is not None for resource_metrics in resource_metrics_list
    ), "Resource metrics from an application with configured resources should have a resource field"
    # Do not assert on schema_url, as it is not always present


def validate_scope_metrics(scope_metrics_list: list) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message ScopeMetrics {
    #     optional opentelemetry.proto.common.v1.InstrumentationScope scope = 1;
    #     repeated Metric metrics = 2;
    #     optional string schema_url = 3;
    # }

    assert all(
        len(scope_metrics) >= 1 for scope_metrics in scope_metrics_list
    ), "Metrics payloads from one configured application should have one or more set of scope metrics"
    assert all(
        scope_metrics[0]["scope"] is not None for scope_metrics in scope_metrics_list
    ), "Scope metrics should have a scope field"
    # Do not assert on schema_url, as it is not always present
    for scope_metrics in scope_metrics_list:
        # Assert values only for metrics we created, since we're asserting against specific fields
        if "opentelemetry" not in scope_metrics[0]["scope"]["name"]:
            for metric in scope_metrics[0]["metrics"]:
                validate_metric(metric)


def validate_metric(metric: dict) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message Metric {
    #     optional string name = 1;
    #     optional string description = 2;
    #     optional string unit = 3;
    #     oneof data {
    #         Gauge gauge = 5;
    #         Sum sum = 7;
    #         Histogram histogram = 9;
    #         ExponentialHistogram exponential_histogram = 10;
    #         Summary summary = 11;
    #     }
    #     repeated opentelemetry.proto.common.v1.KeyValue metadata = 12;
    # }

    assert metric["name"] is not None, "Metrics are expected to have a name"
    # assert metric["description"] is not None, "Metrics are expected to have a description"
    # assert metric["unit"] is not None, "Metrics are expected to have a unit"
    # assert metric["metadata"] is not None, "Metrics are expected to have metadata"

    assert metric["name"].lower() in metric_to_validator, f"Metric {metric['name']} is not expected"
    func, name, value, aggregation_temporality = metric_to_validator[metric["name"].lower()]
    func(metric, name, value, aggregation_temporality)


def validate_counter(metric: dict, name: str, value: object, aggregation_temporality: str) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message Sum {
    #     repeated NumberDataPoint data_points = 1;
    #     optional AggregationTemporality aggregation_temporality = 2;
    #     optional bool is_monotonic = 3;
    # }
    # enum AggregationTemporality {
    #     AGGREGATION_TEMPORALITY_UNSPECIFIED = 0;
    #     AGGREGATION_TEMPORALITY_DELTA = 1;
    #     AGGREGATION_TEMPORALITY_CUMULATIVE = 2;
    # }

    assert metric["name"].lower() == name
    assert "sum" in metric
    assert len(metric["sum"]["dataPoints"]) == 1
    assert metric["sum"]["aggregationTemporality"] == aggregation_temporality
    assert metric["sum"]["isMonotonic"]
    validate_number_data_point(metric["sum"]["dataPoints"][0], "asInt", value, "0")


def validate_histogram(metric: dict, name: str, value: object, aggregation_temporality: str) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message Histogram {
    #     repeated HistogramDataPoint data_points = 1;
    #     optional AggregationTemporality aggregation_temporality = 2;
    # }
    # message HistogramDataPoint {
    #     reserved 1;
    #     repeated opentelemetry.proto.common.v1.KeyValue attributes = 9;
    #     fixed64 start_time_unix_nano = 2;
    #     fixed64 time_unix_nano = 3;
    #     fixed64 count = 4;
    #     optional double sum = 5;
    #     repeated fixed64 bucket_counts = 6;
    #     repeated double explicit_bounds = 7;
    #     repeated Exemplar exemplars = 8;
    #     uint32 flags = 10;
    #     optional double min = 11;
    #     optional double max = 12;
    # }

    assert metric["name"].lower() == name
    assert "histogram" in metric  # This asserts the metric type is a histogram
    assert len(metric["histogram"]["dataPoints"]) == 1
    assert metric["histogram"]["aggregationTemporality"] == aggregation_temporality

    assert metric["histogram"]["dataPoints"][0]["startTimeUnixNano"].isdecimal()
    assert metric["histogram"]["dataPoints"][0]["timeUnixNano"].isdecimal()
    assert metric["histogram"]["dataPoints"][0]["count"] == "1"
    assert metric["histogram"]["dataPoints"][0]["sum"] == value
    assert metric["histogram"]["dataPoints"][0]["min"] == value
    assert metric["histogram"]["dataPoints"][0]["max"] == value


def validate_up_down_counter(metric: dict, name: str, value: object, aggregation_temporality: str) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message Sum {
    #     repeated NumberDataPoint data_points = 1;
    #     optional AggregationTemporality aggregation_temporality = 2;
    #     optional bool is_monotonic = 3;
    # }
    # enum AggregationTemporality {
    #     AGGREGATION_TEMPORALITY_UNSPECIFIED = 0;
    #     AGGREGATION_TEMPORALITY_DELTA = 1;
    #     AGGREGATION_TEMPORALITY_CUMULATIVE = 2;
    # }

    assert metric["name"].lower() == name
    assert "sum" in metric
    assert len(metric["sum"]["dataPoints"]) == 1
    assert metric["sum"]["aggregationTemporality"] == aggregation_temporality
    validate_number_data_point(metric["sum"]["dataPoints"][0], "asInt", value)


def validate_gauge(metric: dict, name: str, value: object, _: str) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message Gauge {
    #     repeated NumberDataPoint data_points = 1;
    # }

    assert metric["name"].lower() == name
    assert "gauge" in metric
    assert len(metric["gauge"]["dataPoints"]) == 1
    validate_number_data_point(metric["gauge"]["dataPoints"][0], "asDouble", value, start_time_is_required=False)


def validate_number_data_point(
    data_point: dict, value_type: object, value: object, default_value: object = None, start_time_is_required: bool = True
) -> None:
    # Assert the following protobuf structure from https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/opentelemetry/proto/metrics/v1/metrics.proto:
    # message NumberDataPoint {
    #     reserved 1;
    #     repeated opentelemetry.proto.common.v1.KeyValue attributes = 7;
    #     optional fixed64 start_time_unix_nano = 2;
    #     optional fixed64 time_unix_nano = 3;
    #     oneof value {
    #         double as_double = 4;
    #         sfixed64 as_int = 6;
    #     }
    #     repeated Exemplar exemplars = 5;
    #     uint32 flags = 8;
    # }

    if start_time_is_required:
        assert data_point["startTimeUnixNano"].isdecimal()
    assert data_point["timeUnixNano"].isdecimal()
    if default_value is not None:
        assert data_point[value_type] == value or data_point[value_type] == default_value
    else:
        assert data_point[value_type] == value
    # Do not assert attributes on every data point
    # Do not assert exemplars on every data point
    # Do not assert flags on every data point


metric_to_validator: dict[str, tuple[Callable[[dict, str, object, str], None], str, object, str]] = {
    "example.counter": (validate_counter, "example.counter", "11", "AGGREGATION_TEMPORALITY_DELTA"),
    "example.async.counter": (validate_counter, "example.async.counter", "22", "AGGREGATION_TEMPORALITY_DELTA"),
    "example.histogram": (validate_histogram, "example.histogram", 33.0, "AGGREGATION_TEMPORALITY_DELTA"),
    "example.updowncounter": (
        validate_up_down_counter,
        "example.updowncounter",
        "55",
        "AGGREGATION_TEMPORALITY_CUMULATIVE",
    ),
    "example.async.updowncounter": (
        validate_up_down_counter,
        "example.async.updowncounter",
        "66",
        "AGGREGATION_TEMPORALITY_CUMULATIVE",
    ),
    "example.gauge": (validate_gauge, "example.gauge", 77.0, ""),
    "example.async.gauge": (validate_gauge, "example.async.gauge", 88.0, ""),
}


@scenarios.otel_metric_e2e
@scenarios.apm_tracing_e2e_otel
@irrelevant(context.library not in ("java_otel", "dotnet", "python"))
@features.not_reported  # FPD does not support otel libs
class Test_OTelMetrics:
    def setup_agent_otlp_upload(self):
        self.start = int(time.time())
        self.r = weblog.get(path="/basic/metric")
        self.expected_metrics = [
            "example.counter",
            "example.async.counter",
            "example.gauge",
            "example.async.gauge",
            "example.updowncounter",
            "example.async.updowncounter",
            "example.histogram",
        ]

    def test_agent_otlp_upload(self):
        seen = set()

        all_resource_metrics = []
        all_scope_metrics = []
        filtered_individual_metrics = []

        for _, resource_metrics in interfaces.open_telemetry.get_metrics(host="agent"):
            all_resource_metrics.append(resource_metrics)
            if "scopeMetrics" not in resource_metrics[0]:
                continue

            scope_metrics = resource_metrics[0]["scopeMetrics"]
            all_scope_metrics.append(scope_metrics)

            for scope_metric in scope_metrics:
                for metric in scope_metric["metrics"]:
                    metric_name = metric["name"].lower()
                    if metric_name.startswith("example"):
                        # Asynchronous instruments report on each metric read, so we need to deduplicate
                        # Also, the UpDownCounter instrument (in addition to the AsyncUpDownCounter instrument) is cumulative, so we need to deduplicate
                        if metric_name.startswith("example.async") or metric_name == "example.updowncounter":
                            if metric_name not in seen:
                                filtered_individual_metrics.append(metric)
                                seen.add(metric_name)
                        else:
                            filtered_individual_metrics.append(metric)

        # Assert resource metrics are present and valid
        assert all(
            len(resource_metrics) == 1 for resource_metrics in all_resource_metrics
        ), "Metrics payloads from one configured application should have one set of resource metrics, but in general this may be 0+"
        assert all(
            resource_metrics[0]["resource"] is not None for resource_metrics in all_resource_metrics
        ), "Resource metrics from an application with configured resources should have a resource field, but in general is optional"
        validate_resource_metrics(all_resource_metrics)

        # Assert scope metrics are present and valid
        # Specific OTLP metric types not tested are: ExponentialHistogram (and by extension ExponentialHistogramDataPoint), Summary (and by extension SummaryDataPoint), Exemplar
        assert len(filtered_individual_metrics) == len(self.expected_metrics), "Agent metrics should match expected"
        validate_scope_metrics(all_scope_metrics)

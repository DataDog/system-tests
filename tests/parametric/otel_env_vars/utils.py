import re
from typing import Any, Final

from utils import pytest

from utils import context

from tests.parametric.conftest import APMLibrary
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


BLRP_LIBRARY_ENV: Final = {
    "DD_LOGS_OTEL_ENABLED": "true",
    "DD_LOGS_OTEL_INTERVAL": None,
    "DD_LOGS_OTEL_TIMEOUT": None,
    "DD_LOGS_OTEL_QUEUE_SIZE": None,
    "DD_LOGS_OTEL_BATCH_SIZE": None,
    "OTEL_BLRP_SCHEDULE_DELAY": None,
    "OTEL_BLRP_EXPORT_TIMEOUT": None,
    "OTEL_BLRP_MAX_QUEUE_SIZE": None,
    "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE": None,
}

JAVA_TELEMETRY_NAMES: Final = {
    "OTEL_BLRP_SCHEDULE_DELAY": "DD_LOGS_OTEL_INTERVAL",
    "OTEL_BLRP_EXPORT_TIMEOUT": "DD_LOGS_OTEL_TIMEOUT",
    "OTEL_BLRP_MAX_QUEUE_SIZE": "DD_LOGS_OTEL_QUEUE_SIZE",
    "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE": "DD_LOGS_OTEL_BATCH_SIZE",
}

TEST_LOGGER_NAME: Final = "blrp_configuration"
TEST_LOG_MESSAGE: Final = "blrp_configuration"


def has_warning_for_value(language: str, logs: str, value: str) -> bool:
    for raw_line in logs.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", raw_line).strip()
        if value not in line:
            continue
        json_start = re.search(r'[\[{]\s*"', line)
        levels = r"WARN(?:ING)?|WRN|DEBUG|DBG|INFO|INF|ERROR|ERR|TRACE|TRC|FATAL|CRITICAL"
        level = re.search(
            rf"(?<![\w.])(?:{levels})(?=[\s:\]])|(?<=\[)(?i:{levels})(?=\])|^(?i:{levels})(?=[:\s])",
            line,
        )
        if level is not None:
            # Ignore levels inside JSON echoes. Real warning messages may contain JSON.
            if json_start is not None and json_start.start() < level.start():
                continue
            # The first level wins, so an INFO/DEBUG echo of a warning cannot pass.
            if level.group().lower() in {"warn", "warning", "wrn"} and value in line[level.end() :]:
                return True
        elif (
            language in {"nodejs", "python"}
            and json_start is None
            and re.search(
                r"\b(?:invalid|unknown|unsupported|not supported|not registered|warning)\b", line, re.IGNORECASE
            )
        ):
            # These SDKs can print warnings without a level prefix. Require a
            # diagnostic containing the test value without fixing its wording.
            return True
    return False


def assert_blrp_configuration(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    variable_name: str,
    expected_value: int,
) -> None:
    with test_library as library:
        library.create_logger(TEST_LOGGER_NAME, LogLevel.INFO)
        library.write_log(TEST_LOGGER_NAME, LogLevel.INFO, TEST_LOG_MESSAGE)

    configuration_name = variable_name
    if test_library.lang == "java":
        configuration_name = JAVA_TELEMETRY_NAMES.get(variable_name, variable_name)

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(configuration_name)
    assert entries, f"No telemetry configuration '{configuration_name}'"
    assert int(entries[0]["value"]) == expected_value


def non_default_protocol(signal: str) -> str:
    """An uppercase transport distinguishable from this SDK's default."""
    if context.library == "nodejs" or (context.library == "php" and signal == "logs"):
        return "HTTP/JSON"
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "HTTP/PROTOBUF"
    return "GRPC"


def default_protocol(signal: str) -> str:
    # OTel permits retaining a historical gRPC default. These defaults are
    # published by the SDKs; never derive the expectation from the tested input.
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "grpc"
    if context.library == "golang" and signal == "logs":
        return "http/json"
    return "http/protobuf"


def expected_protocol(generic_protocol: str | None, protocol: str | None, signal: str) -> str:
    if generic_protocol and not protocol:
        return generic_protocol
    if protocol and protocol != "unsupported":
        return protocol.lower()
    return default_protocol(signal)


# Shared OTLP metric payload assertions and instrument defaults.
EXPECTED_TAGS = [("foo", "bar1"), ("baz", "qux1")]

DEFAULT_METER_NAME = "parametric-api"
DEFAULT_METER_VERSION = "1.0.0"
# schema_url is not supported by .NET's System.Diagnostics.Metrics API
DEFAULT_SCHEMA_URL = "https://opentelemetry.io/schemas/1.21.0"

DEFAULT_INSTRUMENT_UNIT = "triggers"
DEFAULT_INSTRUMENT_DESCRIPTION = "test_description"
DEFAULT_EXPLICIT_BUCKET_BOUNDARIES = [
    0.0,
    5.0,
    10.0,
    25.0,
    50.0,
    75.0,
    100.0,
    250.0,
    500.0,
    750.0,
    1000.0,
    2500.0,
    5000.0,
    7500.0,
    10000.0,
]

DEFAULT_SCOPE_ATTRIBUTES = {"scope.attr": "scope.value"}
DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "test_value"}
NON_DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "non_default_value"}

# Define common default environment variables to support the OpenTelemetry Metrics API feature:
#   DD_METRICS_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
DEFAULT_ENVVARS = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "DD_RUNTIME_METRICS_ENABLED": "false",  # Prevent runtime metrics (System.Runtime, Microsoft.AspNetCore.*) from leaking into custom metric tests
    "OTEL_METRIC_EXPORT_INTERVAL": "60000",  # Mitigate test flake by increasing the interval so that the only time new metrics are exported are when we manually flush them
    "CORECLR_ENABLE_PROFILING": "1",
}


def generate_default_counter_data_point(test_library: APMLibrary, instrument_name: str) -> None:
    test_library.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
    test_library.otel_metrics_force_flush()
    test_library.otel_create_counter(
        DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
    )
    test_library.otel_counter_add(
        DEFAULT_METER_NAME,
        instrument_name,
        DEFAULT_INSTRUMENT_UNIT,
        DEFAULT_INSTRUMENT_DESCRIPTION,
        42,
        DEFAULT_MEASUREMENT_ATTRIBUTES,
    )
    test_library.otel_metrics_force_flush()


def assert_metric_info(metric: dict[str, Any], name: str, unit: str, description: str) -> None:
    assert metric["name"] == name
    assert metric["unit"] == unit
    assert metric["description"] == description


def assert_sum_aggregation(
    sum_aggregation: dict[str, Any],
    aggregation_temporality: str,
    *,
    is_monotonic: bool,
    value: int,
    attributes: dict[str, str],
) -> None:
    assert sum_aggregation["aggregation_temporality"].casefold() == aggregation_temporality.casefold()
    assert sum_aggregation["is_monotonic"] if is_monotonic else not sum_aggregation.get("is_monotonic")

    for sum_data_point in sum_aggregation["data_points"]:
        if attributes == {item["key"]: item["value"]["string_value"] for item in sum_data_point["attributes"]}:
            if "as_double" in sum_data_point:
                actual_value = sum_data_point["as_double"]
            elif "as_int" in sum_data_point:
                actual_value = int(sum_data_point["as_int"])
            else:
                actual_value = None
            assert actual_value == value
            assert (
                attributes.items()
                == {item["key"]: item["value"]["string_value"] for item in sum_data_point["attributes"]}.items()
            )
            assert "time_unix_nano" in sum_data_point
            return

    pytest.fail(f"Sum data point with attributes {attributes} not found in {sum_aggregation['data_points']}")


def assert_gauge_aggregation(gauge_aggregation: dict[str, Any], value: int, attributes: dict[str, str]) -> None:
    for gauge_data_point in gauge_aggregation["data_points"]:
        if attributes == {item["key"]: item["value"]["string_value"] for item in gauge_data_point["attributes"]}:
            if "as_double" in gauge_data_point:
                actual_value = gauge_data_point["as_double"]
            elif "as_int" in gauge_data_point:
                actual_value = int(gauge_data_point["as_int"])
            else:
                actual_value = None
            assert actual_value == value
            assert "time_unix_nano" in gauge_data_point
            return

    pytest.fail(f"Sum data point with attributes {attributes} not found in {gauge_aggregation['data_points']}")


def assert_histogram_aggregation(
    histogram_aggregation: dict[str, Any],
    histogram_temporality: str,
    count: int,
    sum_value: int,
    min_value: int,
    max_value: int,
    bucket_boundaries: list[float],
    bucket_counts: list[int],
    attributes: dict[str, str],
) -> None:
    aggregation_temporality = str(histogram_aggregation["aggregation_temporality"])
    assert aggregation_temporality.casefold() == histogram_temporality.casefold()

    assert isinstance(histogram_aggregation["data_points"], list)
    data_points: list[dict[str, Any]] = histogram_aggregation["data_points"]
    for histogram_data_point in data_points:
        if attributes == {item["key"]: item["value"]["string_value"] for item in histogram_data_point["attributes"]}:
            assert int(histogram_data_point["count"]) == count
            assert histogram_data_point["sum"] == sum_value
            assert histogram_data_point["min"] == min_value
            assert histogram_data_point["max"] == max_value
            assert_histogram_buckets(histogram_data_point, bucket_boundaries, bucket_counts)
            assert "time_unix_nano" in histogram_data_point
            return

    pytest.fail(f"Sum data point with attributes {attributes} not found in {histogram_aggregation['data_points']}")


def assert_histogram_buckets(
    histogram_data_point: dict[str, Any],
    bucket_bounds: list[float],
    bucket_counts: list[int],
) -> None:
    actual_bounds = histogram_data_point["explicit_bounds"]
    actual_counts = [int(c) for c in histogram_data_point["bucket_counts"]]
    if len(bucket_bounds) == 0:
        # only time we expect boundaries and counts to have the same length
        assert bucket_counts == []
        assert actual_bounds == []
        assert actual_counts == []
        return
    # otherwise we expect counts for every boundary plus an overflow count
    # (some empty buckets may be collapsed into one on languages like Java)
    assert len(bucket_counts) == len(bucket_bounds) + 1
    assert len(actual_counts) == len(actual_bounds) + 1
    idx = 0
    last_collapsed_bound = None
    for expected_bound, expected_count in zip(bucket_bounds, bucket_counts, strict=False):
        if idx < len(actual_bounds) and actual_bounds[idx] == expected_bound and actual_counts[idx] == expected_count:
            # actual boundary and count are aligned with expectations
            last_collapsed_bound = None
            idx += 1
        elif expected_count == 0:
            # tolerate collapsing series of empty buckets into one (using the last boundary)
            last_collapsed_bound = expected_bound
        else:
            if last_collapsed_bound is not None:
                # preceding empty buckets collapsed before non-empty bucket
                assert actual_bounds[idx] == last_collapsed_bound
                assert actual_counts[idx] == 0
                idx += 1
            last_collapsed_bound = None
            assert actual_bounds[idx] == expected_bound
            assert actual_counts[idx] == expected_count
            idx += 1
    if last_collapsed_bound is not None:
        if bucket_counts[-1] == 0:
            # expect trailing empty buckets to be collapsed into overflow bucket
            assert actual_counts[-1] == 0
        else:
            # preceding empty buckets collapsed before non-empty overflow bucket
            assert actual_bounds[idx] == last_collapsed_bound
            assert actual_counts[idx] == 0
            idx += 1
    assert idx == len(actual_bounds), f"unexpected extra buckets: {actual_bounds[idx:]}"
    # check the overflow bucket count matches (its boundary is never exported)
    assert actual_counts[-1] == bucket_counts[-1]


def find_metric_by_name(scope_metric: dict[str, Any], name: str) -> dict[str, Any]:
    for metric in scope_metric["metrics"]:
        if metric["name"] == name:
            return metric
    raise ValueError(f"Metric with name {name} not found")


def get_expected_bucket_counts(entries: list[int], bucket_boundaries: list[float]) -> list[int]:
    bucket_counts = [0] * (len(bucket_boundaries) + 1)
    for entry in entries:
        for i in range(len(bucket_boundaries)):
            if entry <= bucket_boundaries[i]:
                bucket_counts[i] += 1
                break
        else:
            bucket_counts[-1] += 1
    return bucket_counts

import time

import json
import pytest
import pprint

from hypothesis import given, settings, HealthCheck, strategies as st

from utils.parametric._library_client import Link
from opentelemetry.trace import StatusCode
from opentelemetry.trace import SpanKind
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import retrieve_span_links
from utils.parametric.spec.trace import find_first_span_in_trace_payload
from utils import bug, features, missing_feature, irrelevant, context, scenarios

EXPECTED_SERVICE_NAME = "test2"
EXPECTED_ENV = "test1"
EXPECTED_VERSION = "5"
EXPECTED_TAGS = [("foo", "bar1"), ("baz", "qux1")]

DEFAULT_METER_NAME = "parametric-api"
DEFAULT_METER_VERSION = "1.0.0"
DEFAULT_SCHEMA_URL = "https://opentelemetry.io/schemas/1.27.0"

DEFAULT_INSTRUMENT_UNIT = "triggers"
DEFAULT_INSTRUMENT_DESCRIPTION = "test_description"
DEFAULT_EXPLICIT_BUCKET_BOUNDARIES = [0.0, 5.0, 10.0, 25.0, 50.0, 75.0, 100.0, 250.0, 500.0, 750.0, 1000.0, 2500.0, 5000.0, 7500.0, 10000.0]

DEFAULT_SCOPE_ATTRIBUTES = {"scope.attr": "scope.value"}
DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "test_value"}

# Define common default environment variables to support the OpenTelemetry Metrics API feature:
#   DD_METRICS_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
DEFAULT_ENVVARS = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000", # Mitigate test flake by increasing the interval so that the only time new metrics are exported are when we manually flush them
    "CORECLR_ENABLE_PROFILING": "1",
}

def find_metric_by_name(scope_metrics: list[dict], name: str):
    for scope_metric in scope_metrics:
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


@scenarios.parametric
@features.otel_metrics_api
class Test_FR01_Enable_OTLP_Metrics_Collection:
    """FR01: OTLP Metrics Collection Enable/Disable Tests"""
    
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "true", "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
        ],
    )
    def test_otlp_metrics_enabled(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted when enabled."""

        name = "enabled-counter"
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        assert first_metrics_data is not None

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "false", "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
        ],
    )
    def test_otlp_metrics_disabled(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted when enabled."""
        name = "disabled-counter"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)

    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": None, "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
        ],
    )
    def test_otlp_metrics_disabled_by_default(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted when enabled."""
        name = "disabled-by-default-counter"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api:
    def assert_scope_metrics(self, scope_metrics, meter_name, meter_version, schema_url, expected_scope_attributes):
        assert scope_metrics[0]["scope"]["name"] == meter_name
        assert scope_metrics[0]["scope"]["version"] == meter_version
        assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metrics[0]["scope"]["attributes"]})
        assert scope_metrics[0]["schema_url"] == schema_url

    def assert_metric_info(self, metric, name, unit, description):
        assert metric["name"] == name
        assert metric["unit"] == unit
        assert metric["description"] == description

    def assert_sum_aggregation(self, sum_aggregation, aggregation_temporality, is_monotonic, value, attributes):
        assert sum_aggregation["aggregation_temporality"].casefold() == aggregation_temporality.casefold()
        assert sum_aggregation["is_monotonic"] if is_monotonic else not sum_aggregation.get("is_monotonic")

        sum_data_point = sum_aggregation["data_points"][0]
        assert sum_data_point["as_double"] == value
        assert set(attributes) == set({item['key']:item['value']['string_value'] for item in sum_data_point["attributes"]})
        assert "time_unix_nano" in sum_data_point

    def assert_gauge_aggregation(self, gauge_aggregation, value, attributes):
        gauge_data_point = gauge_aggregation["data_points"][0]
        assert gauge_data_point["as_double"] == value
        assert set(attributes) == set({item['key']:item['value']['string_value'] for item in gauge_data_point["attributes"]})
        assert "time_unix_nano" in gauge_data_point

    def assert_histogram_aggregation(self, histogram_aggregation, aggregation_temporality, count, sum_value, min_value, max_value, bucket_boundaries, bucket_counts, attributes):
        assert histogram_aggregation["aggregation_temporality"].casefold() == aggregation_temporality.casefold()

        histogram_data_point = histogram_aggregation["data_points"][0]
        assert int(histogram_data_point["count"]) == count
        assert histogram_data_point["sum"] == sum_value
        assert histogram_data_point["min"] == min_value
        assert histogram_data_point["max"] == max_value

        assert histogram_data_point["explicit_bounds"] == bucket_boundaries
        assert list(map(int, histogram_data_point["bucket_counts"])) == bucket_counts
        assert set(attributes) == set({item['key']:item['value']['string_value'] for item in histogram_data_point["attributes"]})
        assert "time_unix_nano" in histogram_data_point

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_value(self, test_agent, test_library, n):
        name = f"counter1-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=-2**32, max_value=-1)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_and_negative_values(self, test_agent, test_library, non_negative_value, negative_value):
        name = f"counter1-{non_negative_value}-{negative_value}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = scope_metrics[0]["metrics"][0]
        self.assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_values(self, test_agent, test_library, non_negative_value, second_non_negative_value):
        name = f"counter1-{non_negative_value}-{second_non_negative_value}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = scope_metrics[0]["metrics"][0]
        self.assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, non_negative_value + second_non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_updowncounter_add_value(self, test_agent, test_library, n):
        name = f"updowncounter1-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        updowncounter = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(updowncounter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32), st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_updowncounter_add_multiple_values(self, test_agent, test_library, first_value, second_value):
        name = f"updowncounter1-{first_value}-{second_value}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        updowncounter = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(updowncounter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, first_value + second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_gauge_record_value(self, test_agent, test_library, n):
        name = f"gauge-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_gauge_aggregation(gauge["gauge"], n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32), st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_gauge_record_multiple_values(self, test_agent, test_library, first_value, second_value):
        name = f"gauge-{first_value}-{second_value}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_gauge_aggregation(gauge["gauge"], second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_histogram_add_non_negative_value(self, test_agent, test_library, n):
        name = f"histogram-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(histogram, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=1, sum_value=n, min_value=n, max_value=n, bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([n], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=0, max_value=2**32), st.integers(min_value=-2**32, max_value=-1)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_histogram_add_non_negative_and_negative_values(self, test_agent, test_library, non_negative_value1, non_negative_value2, negative_value1):
        name = f"histogram-{non_negative_value1}-{non_negative_value2}-{negative_value1}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value1, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value2, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, negative_value1, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(histogram, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        # Negative values are ignored by the Histogram Record API, so we only have 2 data points
        self.assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=2, sum_value=non_negative_value1 + non_negative_value2, min_value=min(non_negative_value1, non_negative_value2), max_value=max(non_negative_value1, non_negative_value2), bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([non_negative_value1, non_negative_value2], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_asynchronous_counter_constant_callback_value(self, test_agent, test_library, n):
        name = f"observablecounter1-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_asynchronous_updowncounter_constant_callback_value(self, test_agent, test_library, n):
        name = f"observableupdowncounter1-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_asynchronous_gauge_constant_callback_value(self, test_agent, test_library, n):
        name = f"observablegauge-{n}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, n, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        self.assert_scope_metrics(scope_metrics, DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics, name)
        self.assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        self.assert_gauge_aggregation(gauge["gauge"], n, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @missing_feature(context.library == "python", reason="Doesn't implement OTEL_RESOURCE_ATTRIBUTES with metrics")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "test1",
                "DD_SERVICE": "test2",
                "DD_VERSION": "5",
                "DD_TAGS": "foo:bar1,baz:qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_SERVICE": "test2",
                "DD_VERSION": "5",
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=test1,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "test1",
                "DD_VERSION": "5",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=test2,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "test1",
                "DD_SERVICE": "test2",
                "OTEL_RESOURCE_ATTRIBUTES": "service.version=5,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "test1",
                "DD_SERVICE": "test2",
                "OTEL_RESOURCE_ATTRIBUTES": "service.version=5,foo=bar1,baz=qux1",
            },
        ],
    )
    def test_otel_resource_attributes_mapping(self, test_agent, test_library):
        name = "counter1"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 2, {"test_attr": "test_value"})
            t.otel_metrics_force_flush()

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        pprint.pprint(metrics_data)

        # Assert that there is only one item in ResourceMetrics
        assert len(metrics_data) == 1

        # Assert that the ResourceMetrics has the expected resources
        resource_metrics = metrics_data[0]["resource_metrics"]
        resource = resource_metrics[0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}
        assert set(expected_attributes) <= set(actual_attributes)

        # Add separate assertion for the DD_ENV mapping, whose semantic convention was updated in 1.27.0
        assert actual_attributes.get("deployment.environment") == "test1" or actual_attributes.get("deployment.environment.name") == "test1"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "test1",
                "DD_SERVICE": "test2",
                "DD_VERSION": "5",
                "DD_TAGS": "foo:bar1,baz:qux1",
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=ignored_env,service.name=ignored_service,service.version=ignored_version,foo=ignored_bar1,baz=ignored_qux1",
            },
        ],
    )
    def test_otel_resource_attributes_mapping_dd_preference(self, test_agent, test_library):
        name = "counter1"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 2, {"test_attr": "test_value"})
            t.otel_metrics_force_flush()

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        pprint.pprint(metrics_data)

        # Assert that there is only one item in ResourceMetrics
        assert len(metrics_data) == 1

        # Assert that the ResourceMetrics has the expected resources
        resource_metrics = metrics_data[0]["resource_metrics"]
        resource = resource_metrics[0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}
        assert set(expected_attributes) <= set(actual_attributes)

        # Add separate assertion for the DD_ENV mapping, whose semantic convention was updated in 1.27.0
        assert actual_attributes.get("deployment.environment") == "test1" or actual_attributes.get("deployment.environment.name") == "test1"


@features.otel_metrics_api
@scenarios.parametric
class Test_OTLP_Protocols:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            },
        ],
        ids=["http_protobuf", "grpc"],
    )
    def test_otlp_protocols(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted in expected format."""
        protocol = library_env["OTEL_EXPORTER_OTLP_PROTOCOL"]
        name = f"test_otlp_protocols-{protocol}-counter"
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name)
        assert first_metrics_data is not None

        requests = test_agent.requests()
        test_agent.clear()
        metrics_requests = [r for r in requests if r["url"].endswith("/v1/metrics")]
        assert metrics_requests, f"Expected metrics request, got {requests}"
        assert (
            metrics_requests[0]["headers"].get("Content-Type") == "application/x-protobuf" if protocol == "http/protobuf" else "application/grpc"
        ), f"Expected correct Content-Type, got {metrics_requests[0]['headers']}"


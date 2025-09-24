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
from urllib.parse import urlparse

EXPECTED_TAGS = [("foo", "bar1"), ("baz", "qux1")]

DEFAULT_METER_NAME = "parametric-api"
DEFAULT_METER_VERSION = "1.0.0"
DEFAULT_SCHEMA_URL = "https://opentelemetry.io/schemas/1.27.0"

DEFAULT_INSTRUMENT_UNIT = "triggers"
DEFAULT_INSTRUMENT_DESCRIPTION = "test_description"
DEFAULT_EXPLICIT_BUCKET_BOUNDARIES = [0.0, 5.0, 10.0, 25.0, 50.0, 75.0, 100.0, 250.0, 500.0, 750.0, 1000.0, 2500.0, 5000.0, 7500.0, 10000.0]

DEFAULT_SCOPE_ATTRIBUTES = {"scope.attr": "scope.value"}
DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "test_value"}
NON_DEFAULT_MEASUREMENT_ATTRIBUTES = {"test_attr": "non_default_value"}

# Define common default environment variables to support the OpenTelemetry Metrics API feature:
#   DD_METRICS_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
DEFAULT_ENVVARS = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_METRIC_EXPORT_INTERVAL": "60000", # Mitigate test flake by increasing the interval so that the only time new metrics are exported are when we manually flush them
    "CORECLR_ENABLE_PROFILING": "1",
}

@pytest.fixture
def otlp_endpoint_library_env(library_env, endpoint_env, test_agent_container_name, test_agent_otlp_grpc_port):
    """Set up a custom endpoint for OTLP metrics."""
    prev_value = library_env.get(endpoint_env)
    library_env[endpoint_env] = f"http://{test_agent_container_name}:{test_agent_otlp_grpc_port}"
    yield library_env
    if prev_value is None:
        del library_env[endpoint_env]
    else:
        library_env[endpoint_env] = prev_value

def assert_scope_metric(scope_metric, meter_name, meter_version, schema_url, expected_scope_attributes):
    assert scope_metric["scope"]["name"] == meter_name
    assert scope_metric["scope"]["version"] == meter_version
    assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metric["scope"]["attributes"]})
    assert scope_metric["schema_url"] == schema_url

def assert_metric_info(metric, name, unit, description):
    assert metric["name"] == name
    assert metric["unit"] == unit
    assert metric["description"] == description

def assert_sum_aggregation(sum_aggregation, aggregation_temporality, is_monotonic, value, attributes):
    assert sum_aggregation["aggregation_temporality"].casefold() == aggregation_temporality.casefold()
    assert sum_aggregation["is_monotonic"] if is_monotonic else not sum_aggregation.get("is_monotonic")

    for sum_data_point in sum_aggregation["data_points"]:
        if attributes == {item['key']:item['value']['string_value'] for item in sum_data_point["attributes"]}:
            assert sum_data_point["as_double"] == value
            assert set(attributes) == set({item['key']:item['value']['string_value'] for item in sum_data_point["attributes"]})
            assert "time_unix_nano" in sum_data_point
            return
    
    assert False, f"Sum data point with attributes {attributes} not found in {sum_aggregation['data_points']}"

def assert_gauge_aggregation(gauge_aggregation, value, attributes):
    for gauge_data_point in gauge_aggregation["data_points"]:
        if attributes == {item['key']:item['value']['string_value'] for item in gauge_data_point["attributes"]}:
            assert gauge_data_point["as_double"] == value
            assert "time_unix_nano" in gauge_data_point
            return

    assert False, f"Sum data point with attributes {attributes} not found in {gauge_aggregation['data_points']}"

def assert_histogram_aggregation(histogram_aggregation, aggregation_temporality, count, sum_value, min_value, max_value, bucket_boundaries, bucket_counts, attributes):
    assert histogram_aggregation["aggregation_temporality"].casefold() == aggregation_temporality.casefold()

    for histogram_data_point in histogram_aggregation["data_points"]:
        if attributes == {item['key']:item['value']['string_value'] for item in histogram_data_point["attributes"]}:
            assert int(histogram_data_point["count"]) == count
            assert histogram_data_point["sum"] == sum_value
            assert histogram_data_point["min"] == min_value
            assert histogram_data_point["max"] == max_value

            assert histogram_data_point["explicit_bounds"] == bucket_boundaries
            assert list(map(int, histogram_data_point["bucket_counts"])) == bucket_counts
            assert "time_unix_nano" in histogram_data_point
            return

    assert False, f"Sum data point with attributes {attributes} not found in {histogram_aggregation['data_points']}"

def find_metric_by_name(scope_metric: dict, name: str):
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
    """Tests the enablement and disablement of the OTel Metrics API through the following configurations:
    - DD_METRICS_OTEL_ENABLED
    - OTEL_METRICS_EXPORTER
    """
    
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "true", "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
            {"DD_METRICS_OTEL_ENABLED": "true", "OTEL_METRICS_EXPORTER": "otlp", "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
        ],
    )
    def test_otlp_metrics_enabled(self, test_agent, test_library, library_env):
        """Ensure that OTLP metrics are emitted."""

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
            {"DD_METRICS_OTEL_ENABLED": "true", "OTEL_METRICS_EXPORTER": "none", "OTEL_METRIC_EXPORT_INTERVAL": "60000", "CORECLR_ENABLE_PROFILING": "1"},
        ],
    )
    def test_otlp_metrics_disabled(self, test_agent, test_library, library_env):
        """Ensure that OTLP metrics are not emitted."""
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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = scope_metrics[0]["metrics"][0]
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = scope_metrics[0]["metrics"][0]
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, non_negative_value + second_non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_values_with_different_tags(self, test_agent, test_library, non_negative_value, second_non_negative_value):
        name = f"counter1-{non_negative_value}-{second_non_negative_value}-different-tags"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_non_negative_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        pprint.pprint(scope_metrics)
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = scope_metrics[0]["metrics"][0]
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, non_negative_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, second_non_negative_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        updowncounter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(updowncounter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        updowncounter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(updowncounter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, first_value + second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32), st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_updowncounter_add_multiple_values_with_different_tags(self, test_agent, test_library, first_value, second_value):
        name = f"updowncounter1-{first_value}-{second_value}-different-tags"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)
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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        updowncounter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(updowncounter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
        assert_sum_aggregation(updowncounter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, second_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(gauge["gauge"], n, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(gauge["gauge"], second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32), st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_gauge_record_multiple_values_with_different_tags(self, test_agent, test_library, first_value, second_value):
        name = f"gauge-{first_value}-{second_value}-different-tags"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, second_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)
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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(gauge["gauge"], first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
        assert_gauge_aggregation(gauge["gauge"], second_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(histogram, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=1, sum_value=n, min_value=n, max_value=n, bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([n], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(histogram, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        # Negative values are ignored by the Histogram Record API, so we only have 2 data points
        assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=2, sum_value=non_negative_value1 + non_negative_value2, min_value=min(non_negative_value1, non_negative_value2), max_value=max(non_negative_value1, non_negative_value2), bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([non_negative_value1, non_negative_value2], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_histogram_add_non_negative_values_with_different_tags(self, test_agent, test_library, non_negative_value1, non_negative_value2):
        name = f"histogram-{non_negative_value1}-{non_negative_value2}-different-tags"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value1, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, non_negative_value2, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)
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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(histogram, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        # Negative values are ignored by the Histogram Record API, so we only have 2 data points
        assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=1, sum_value=non_negative_value1, min_value=non_negative_value1, max_value=non_negative_value1, bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([non_negative_value1], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)
        assert_histogram_aggregation(histogram["histogram"], "AGGREGATION_TEMPORALITY_DELTA", count=1, sum_value=non_negative_value2, min_value=non_negative_value2, max_value=non_negative_value2, bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([non_negative_value2], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=NON_DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_DELTA", True, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        counter = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(counter, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(counter["sum"], "AGGREGATION_TEMPORALITY_CUMULATIVE", False, n, DEFAULT_MEASUREMENT_ATTRIBUTES)

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
        assert_scope_metric(scope_metrics[0], DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

        gauge = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(gauge, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(gauge["gauge"], n, DEFAULT_MEASUREMENT_ATTRIBUTES)


@scenarios.parametric
@features.otel_metrics_api
class Test_Metrics_Temporality_Preference:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_counter(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_counter-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_CUMULATIVE" if temporality_preference == "CUMULATIVE" else "AGGREGATION_TEMPORALITY_DELTA"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        counter = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_sum_aggregation(counter["sum"], expected_aggregation_temporality, True, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_updowncounter(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_updowncounter-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_CUMULATIVE"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_updowncounter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        updowncounter = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_sum_aggregation(updowncounter["sum"], expected_aggregation_temporality, False, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_gauge(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_gauge-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_CUMULATIVE"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Note: Temporality does not affect the OTLP metric for Gauges
        gauge = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_gauge_aggregation(gauge["gauge"], 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_histogram(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_histogram-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_CUMULATIVE" if temporality_preference == "CUMULATIVE" else "AGGREGATION_TEMPORALITY_DELTA"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        histogram = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_histogram_aggregation(histogram["histogram"], expected_aggregation_temporality, count=1, sum_value=42, min_value=42, max_value=42, bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES, bucket_counts=get_expected_bucket_counts([42], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES), attributes=DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_asynchronous_counter(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_asynchronous_counter-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_DELTA" if temporality_preference == "DELTA" or temporality_preference == "default" else "AGGREGATION_TEMPORALITY_CUMULATIVE"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        counter = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_sum_aggregation(counter["sum"], expected_aggregation_temporality, True, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_asynchronous_updowncounter(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_asynchronous_updowncounter-{temporality_preference.lower()}"
        expected_aggregation_temporality = "AGGREGATION_TEMPORALITY_CUMULATIVE"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_updowncounter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        updowncounter = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_sum_aggregation(updowncounter["sum"], expected_aggregation_temporality, False, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"
            }
        ],
        ids=["default", "delta", "cumulative"]
    )
    def test_otel_aggregation_temporality_asynchronous_gauge(self, library_env, test_agent, test_library):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")
        name = f"test_otel_aggregation_temporality_asynchronous_gauge-{temporality_preference.lower()}"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_metrics_force_flush()
            t.otel_create_asynchronous_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        pprint.pprint(first_metrics_data)

        # Note: Temporality does not affect the OTLP metric for Gauges
        gauge = find_metric_by_name(first_metrics_data["resource_metrics"][0]["scope_metrics"][0], name)
        assert_gauge_aggregation(gauge["gauge"], 42, DEFAULT_MEASUREMENT_ATTRIBUTES)


@scenarios.parametric
@features.otel_metrics_api
class Test_Resource_Attributes:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=otelenv,service.name=service,service.version=5,foo=bar1,baz=qux1",
            },
        ],
    )
    def test_otel_resource_attributes(self, test_agent, test_library):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
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
        assert actual_attributes.get("deployment.environment") == "otelenv" or actual_attributes.get("deployment.environment.name") == "otelenv"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "otelenv",
                "DD_SERVICE": "service",
                "DD_VERSION": "2.0",
                "DD_TAGS": "foo:bar1,baz:qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=otelenv,service.name=service,service.version=2.0,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_SERVICE": "service",
                "DD_VERSION": "2.0",
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=otelenv,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "otelenv",
                "DD_VERSION": "2.0",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=service,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "otelenv",
                "DD_SERVICE": "service",
                "OTEL_RESOURCE_ATTRIBUTES": "service.version=2.0,foo=bar1,baz=qux1",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "otelenv",
                "DD_SERVICE": "service",
                "OTEL_RESOURCE_ATTRIBUTES": "service.version=2.0,foo=bar1,baz=qux1",
            },
        ],
    )
    def test_otel_resource_attributes_populated_by_dd_otel_envs(self, test_agent, test_library):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
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
        assert actual_attributes.get("deployment.environment") == "otelenv" or actual_attributes.get("deployment.environment.name") == "otelenv"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_ENV": "otelenv",
                "DD_SERVICE": "service",
                "DD_VERSION": "2.0",
                "DD_TAGS": "foo:bar1,baz:qux1",
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=ignored_env,service.name=ignored_service,service.version=ignored_version,foo=ignored_bar1,baz=ignored_qux1",
            },
        ],
    )
    def test_dd_env_vars_override_otel(self, test_agent, test_library):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
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
        assert actual_attributes.get("deployment.environment") == "otelenv" or actual_attributes.get("deployment.environment.name") == "otelenv"


@scenarios.parametric
@features.otel_metrics_api
class Test_Custom_Endpoints:
    """FR05: Custom OTLP Endpoint Tests"""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {**DEFAULT_ENVVARS},
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = f"test_otlp_custom_endpoint-counter"
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        assert (
            urlparse(library_env[endpoint_env]).port == 4320
        ), f"Expected port 4320 in {urlparse(library_env[endpoint_env])}"

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        assert first_metrics_data is not None

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {**DEFAULT_ENVVARS},
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                4321,
            ),
        ],
    )
    def test_otlp_metrics_custom_endpoint(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = f"test_otlp_metrics_custom_endpoint-counter"
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        assert (
            urlparse(library_env[endpoint_env]).port == 4321
        ), f"Expected port 4321 in {urlparse(library_env[endpoint_env])}"

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=True)
        assert first_metrics_data is not None


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


@features.otel_metrics_api
@scenarios.parametric
class Test_FR08_Custom_Headers:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
        ],
    )
    def test_custom_http_headers_included_in_otlp_export(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted when enabled."""

        name = "test_custom_http_headers_included_in_otlp_export-counter"
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
        assert metrics_requests[0]["headers"].get("api-key") == "key", f"Expected api-key, got {metrics_requests[0]['headers']}"
        assert (
            metrics_requests[0]["headers"].get("other-config-value") == "value"
        ), f"Expected other-config-value, got {metrics_requests[0]['headers']}"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=otelenv,service.name=service,service.version=5,foo=bar1,baz=qux1",
                "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "api-key=key,other-config-value=value",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
        ],
    )
    def test_custom_metrics_http_headers_included_in_otlp_export(self, test_agent, test_library, library_env):
        """OTLP metrics are emitted when enabled."""

        name = "test_custom_metrics_http_headers_included_in_otlp_export-counter"
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
        assert metrics_requests[0]["headers"].get("api-key") == "key", f"Expected api-key, got {metrics_requests[0]['headers']}"
        assert (
            metrics_requests[0]["headers"].get("other-config-value") == "value"
        ), f"Expected other-config-value, got {metrics_requests[0]['headers']}"


@features.otel_metrics_api
@scenarios.parametric
class Test_Metric_Export_Interval:
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1", "DD_TRACE_DEBUG": None, "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"},
        ],
    )
    def test_default_interval(self, test_agent, test_library, library_env):
        """SDK uses default interval when no interval env vars are set."""
        name = "test_default_interval"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        # Find default configurations (since no env vars are set, these should have default origin)
        metrics_export_interval = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_METRIC_EXPORT_INTERVAL", "default", fallback_to_first=True
        )

        assert metrics_export_interval is not None, "OTEL_METRIC_EXPORT_INTERVAL should be set"

        assert (
            metrics_export_interval.get("value") == 10000
        ), f"OTEL_METRIC_EXPORT_INTERVAL should be 10000, metrics_export_interval: {metrics_export_interval}"


@features.otel_metrics_api
@scenarios.parametric
class Test_Metric_Export_Timeout:
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1", "DD_TRACE_DEBUG": None, "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"},
        ],
    )
    def test_default_timeout(self, test_agent, test_library, library_env):
        """SDK uses a non-standard default timeout when no timeout env vars are set."""
        name = "test_default_timeout"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        # Find default configurations (since no env vars are set, these should have default origin)
        metrics_export_timeout = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_METRIC_EXPORT_TIMEOUT", "default", fallback_to_first=True
        )

        assert metrics_export_timeout is not None, "OTEL_METRIC_EXPORT_TIMEOUT should be set"

        assert (
            metrics_export_timeout.get("value") == 7500
        ), f"OTEL_METRIC_EXPORT_TIMEOUT should be 7500, metrics_export_timeout: {metrics_export_timeout}"


@features.otel_metrics_api
@scenarios.parametric
class Test_Metrics_Host_Name:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "true",
            },
        ],
    )
    def test_hostname_from_dd_hostname(self, test_agent, test_library, library_env):
        """host.name is set from DD_HOSTNAME."""
        name = "test_hostname_from_dd_hostname"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 2, {"test_attr": "test_value"})
            t.otel_metrics_force_flush()

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}

        assert actual_attributes.get("host.name") == "ddhostname"

    @pytest.mark.parametrize(
        ("library_env", "host_attribute"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_RESOURCE_ATTRIBUTES": "host=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                },
                "host",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_RESOURCE_ATTRIBUTES": "datadog.host.name=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                },
                "datadog.host.name",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_RESOURCE_ATTRIBUTES": "host.name=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                },
                "host.name",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_RESOURCE_ATTRIBUTES": "host.id=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                },
                "host.id",
            ),
        ],
        ids=["host", "datadog.host.name", "host.name", "host.id"],
    )
    def test_hostname_from_otel_resources(self, test_agent, test_library, library_env, host_attribute):
        """Hostname attributes in OTEL_RESOURCE_ATTRIBUTES takes precedence over DD_HOSTNAME."""
        name = "test_hostname_from_otel_resources"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 2, {"test_attr": "test_value"})
            t.otel_metrics_force_flush()

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}

        assert actual_attributes.get(host_attribute) == "otelenv-host"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": "false",
            },
            {
                **DEFAULT_ENVVARS,
                "DD_HOSTNAME": "ddhostname",
                "DD_TRACE_REPORT_HOSTNAME": None,
            },
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_REPORT_HOSTNAME": None,
            },
        ],
        ids=["disabled", "hostname_set_via_dd_hostname", "default"],
    )
    def test_hostname_omitted(self, test_agent, test_library, library_env):
        """host.name is omitted when not configured."""
        name = "test_hostname_omitted"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 2, {"test_attr": "test_value"})
            t.otel_metrics_force_flush()

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}

        assert "host.name" not in actual_attributes


@features.otel_metrics_api
@scenarios.parametric
class Test_OTLP_Exporter_Metrics_Timeout:
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_METRICS_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1", "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"},
        ],
    )
    def test_default_timeout(self, test_agent, test_library, library_env):
        """SDK uses default timeout when no timeout env vars are set."""
        name = "test_default_timeout"

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        # Wait for telemetry configurations and verify the timeout has the default value of 10s
        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        # Find default configurations (since no env vars are set, these should have default origin)
        exporter_timeout = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_EXPORTER_OTLP_TIMEOUT", "default", fallback_to_first=True
        )
        exporter_metrics_timeout = test_agent.get_telemetry_config_by_origin(
            configurations_by_name, "OTEL_EXPORTER_OTLP_METRICS_TIMEOUT", "default", fallback_to_first=True
        )

        assert exporter_timeout is not None, "OTEL_EXPORTER_OTLP_TIMEOUT should be set"
        assert exporter_metrics_timeout is not None, "OTEL_EXPORTER_OTLP_METRICS_TIMEOUT should be set"

        assert (
            exporter_timeout.get("value") == 10000
        ), f"OTEL_EXPORTER_OTLP_TIMEOUT should be 10000, exporter_timeout: {exporter_timeout}"
        assert (
            exporter_metrics_timeout.get("value") == 10000
        ), f"OTEL_EXPORTER_OTLP_METRICS_TIMEOUT should be 10000, exporter_metrics_timeout: {exporter_metrics_timeout}"


@features.otel_metrics_api
@scenarios.parametric
class Test_FR11_Telemetry:
    """Test OTLP Logs generated via OpenTelemetry API generate telemetry configurations and metrics."""

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_telemetry_exporter_configurations(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Test configurations starting with OTEL_EXPORTER_OTLP_ are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_exporter_configurations"
        
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_TIMEOUT", 30000),
            ("OTEL_EXPORTER_OTLP_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc"),
            ("OTEL_EXPORTER_OTLP_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_ENDPOINT"]),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert (
                config.get("value") == expected_value
            ), f"Expected {expected_env} to be {expected_value}, configuration: {config}"

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    "DD_METRICS_OTEL_ENABLED": "true",
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_METRICS_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                4325,
            ),
        ],
    )
    def test_telemetry_exporter_metrics_configurations(
        self, library_env, endpoint_env, test_agent_otlp_grpc_port, otlp_endpoint_library_env, test_agent, test_library
    ):
        """Test Teleemtry configurations starting with OTEL_EXPORTER_OTLP_METRICS_ are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_exporter_metrics_configurations"
        
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_METRICS_TIMEOUT", 30000),
            ("OTEL_EXPORTER_OTLP_METRICS_HEADERS", "api-key=key,other-config-value=value"),
            ("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", "grpc"),
            ("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", library_env["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"]),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert (
                config.get("value") == expected_value
            ), f"Expected {expected_env} to be {expected_value}, configuration: {config}"

    @pytest.mark.parametrize(
        ("library_env", "protocol"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                },
                "grpc",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                },
                "http/protobuf",
            )
        ],
        ids=["grpc", "http/protobuf"],
    )
    def test_telemetry_metrics(self, library_env, test_agent, test_library, protocol):
        """Test telemetry metrics are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_metrics"
        
        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(DEFAULT_METER_NAME)
            t.otel_metrics_force_flush()
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION, 42, DEFAULT_MEASUREMENT_ATTRIBUTES)
            t.otel_metrics_force_flush()

        first_metrics_data = test_agent.wait_for_first_otlp_metric(metric_name=name, clear=False)
        assert first_metrics_data is not None

        metrics = test_agent.wait_for_telemetry_metrics("otel.metrics_export_attempts")
        assert metrics, f"Expected metrics, got {metrics}"
        for metric in metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert f"protocol:{protocol}" in metric.get("tags")

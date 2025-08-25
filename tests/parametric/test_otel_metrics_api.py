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

# Define common default environment variables to support the OpenTelemetry Metrics API feature:
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   DD_METRICS_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
DEFAULT_ENVVARS = {
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_METRIC_EXPORT_INTERVAL": "100", # Reduce the interval to speed up the tests
    "CORECLR_ENABLE_PROFILING": "1",
}

@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api:
    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_value(self, test_agent, test_library, n):
        meter_name = "parametric-api"
        name = f"counter1-{n}"
        unit = "triggers"
        description = "test_description"
        expected_scope_attributes = {"scope.attr": "scope.value"}
        expected_add_attributes = {"test_attr": "test_value"}

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name, version="1.0.0", schema_url="https://opentelemetry.io/schemas/1.27.0", attributes=expected_scope_attributes)
            t.otel_create_counter(meter_name, name, unit, description)
            t.otel_counter_add(meter_name, name, unit, description, n, expected_add_attributes)
            time.sleep(0.5)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1, clear=True)
        pprint.pprint(metrics_data)

        # Assert that there is only one request
        assert len(metrics_data) == 1

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = metrics_data[0]["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        assert scope_metrics[0]["scope"]["name"] == "parametric-api"
        assert scope_metrics[0]["scope"]["version"] == "1.0.0"
        assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metrics[0]["scope"]["attributes"]})

        assert scope_metrics[0]["schema_url"] == "https://opentelemetry.io/schemas/1.27.0"

        counter = scope_metrics[0]["metrics"][0]
        assert counter["name"] == name
        assert counter["unit"] == unit
        assert counter["description"] == description

        assert counter["sum"]["aggregation_temporality"].casefold() == "AGGREGATION_TEMPORALITY_DELTA".casefold()
        assert counter["sum"]["is_monotonic"] == True

        sum_data_point = counter["sum"]["data_points"][0]
        assert sum_data_point["as_double"] == n
        assert set(expected_add_attributes) == set({item['key']:item['value']['string_value'] for item in sum_data_point["attributes"]})
        assert "time_unix_nano" in sum_data_point

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=-1)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_negative_value(self, test_agent, test_library, n):
        meter_name = "parametric-api"
        name = f"counter1-{n}"
        unit = "triggers"
        description = "test_description"
        expected_scope_attributes = {"scope.attr": "scope.value"}
        expected_add_attributes = {"test_attr": "test_value"}

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name, version="1.0.0", schema_url="https://opentelemetry.io/schemas/1.27.0", attributes=expected_scope_attributes)
            t.otel_create_counter(meter_name, name, unit, description)
            t.otel_counter_add(meter_name, name, unit, description, n, expected_add_attributes)
            time.sleep(0.5)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=0, clear=True)
        pprint.pprint(metrics_data)
        assert len(metrics_data) == 0

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=0, max_value=2**32), st.integers(min_value=-2**32, max_value=-1)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_counter_add_non_negative_and_negative_values(self, test_agent, test_library, non_negative_value, negative_value):
        meter_name = "parametric-api"
        name = f"counter1-{non_negative_value}-{negative_value}"
        unit = "triggers"
        description = "test_description"
        expected_scope_attributes = {"scope.attr": "scope.value"}
        expected_add_attributes = {"test_attr": "test_value"}

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name, version="1.0.0", schema_url="https://opentelemetry.io/schemas/1.27.0", attributes=expected_scope_attributes)
            t.otel_create_counter(meter_name=meter_name, name=name, unit=unit, description=description)
            t.otel_counter_add(meter_name, name, unit, description, non_negative_value, expected_add_attributes)
            t.otel_counter_add(meter_name, name, unit, description, negative_value, expected_add_attributes)
            time.sleep(0.5)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1, clear=True)
        pprint.pprint(metrics_data)

        # Assert that there is only one request
        assert len(metrics_data) == 1

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = metrics_data[0]["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        assert scope_metrics[0]["scope"]["name"] == "parametric-api"
        assert scope_metrics[0]["scope"]["version"] == "1.0.0"
        assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metrics[0]["scope"]["attributes"]})

        assert scope_metrics[0]["schema_url"] == "https://opentelemetry.io/schemas/1.27.0"

        counter = scope_metrics[0]["metrics"][0]
        assert counter["name"] == name
        assert counter["unit"] == "triggers"
        assert counter["description"] == "test_description"

        assert counter["sum"]["aggregation_temporality"].casefold() == "AGGREGATION_TEMPORALITY_DELTA".casefold()
        assert counter["sum"]["is_monotonic"] == True

        sum_data_point = counter["sum"]["data_points"][0]
        assert sum_data_point["as_double"] == non_negative_value
        assert set(expected_add_attributes) == set({item['key']:item['value']['string_value'] for item in sum_data_point["attributes"]})
        assert "time_unix_nano" in sum_data_point

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_gauge_record_value(self, test_agent, test_library, n):
        meter_name = "parametric-api"
        name = f"gauge-{n}"
        unit = "latest"
        description = "test_description"
        expected_scope_attributes = {"scope.attr": "scope.value"}
        expected_add_attributes = {"test_attr": "test_value"}

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name, version="1.0.0", schema_url="https://opentelemetry.io/schemas/1.27.0", attributes=expected_scope_attributes)
            t.otel_create_gauge(meter_name, name, unit, description)
            t.otel_gauge_record(meter_name, name, unit, description, n, expected_add_attributes)
            time.sleep(0.5)

        first_metrics_data = test_agent.wait_for_first_otlp_metric(clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        assert scope_metrics[0]["scope"]["name"] == "parametric-api"
        assert scope_metrics[0]["scope"]["version"] == "1.0.0"
        assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metrics[0]["scope"]["attributes"]})

        assert scope_metrics[0]["schema_url"] == "https://opentelemetry.io/schemas/1.27.0"

        gauge = scope_metrics[0]["metrics"][0]
        assert gauge["name"] == name
        assert gauge["unit"] == unit
        assert gauge["description"] == description

        gauge_data_point = gauge["gauge"]["data_points"][0]
        assert gauge_data_point["as_double"] == n
        assert set(expected_add_attributes) == set({item['key']:item['value']['string_value'] for item in gauge_data_point["attributes"]})
        assert "time_unix_nano" in gauge_data_point

    # This test takes upwards of 25 seconds to run
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @given(st.integers(min_value=-2**32, max_value=2**32), st.integers(min_value=-2**32, max_value=2**32)) # Limit the range of integers to avoid int/float equality issues
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None, max_examples=20) # Limit the number of examples to speed up the test
    def test_otel_gauge_record_multiple_values(self, test_agent, test_library, first_value, second_value):
        meter_name = "parametric-api"
        name = f"gauge-{first_value}-{second_value}"
        unit = "latest"
        description = "test_description"
        expected_scope_attributes = {"scope.attr": "scope.value"}
        expected_add_attributes = {"test_attr": "test_value"}

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name, version="1.0.0", schema_url="https://opentelemetry.io/schemas/1.27.0", attributes=expected_scope_attributes)
            t.otel_create_gauge(meter_name, name, unit, description)
            t.otel_gauge_record(meter_name, name, unit, description, first_value, expected_add_attributes)
            t.otel_gauge_record(meter_name, name, unit, description, second_value, expected_add_attributes)
            time.sleep(0.5)

        first_metrics_data = test_agent.wait_for_first_otlp_metric(clear=True)
        pprint.pprint(first_metrics_data)

        # Assert that there is only one item in ResourceMetrics
        resource_metrics = first_metrics_data["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that the ResourceMetrics has the expected ScopeMetrics
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 1

        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        assert scope_metrics[0]["scope"]["name"] == "parametric-api"
        assert scope_metrics[0]["scope"]["version"] == "1.0.0"
        assert set(expected_scope_attributes) == set({item['key']:item['value']['string_value'] for item in scope_metrics[0]["scope"]["attributes"]})

        assert scope_metrics[0]["schema_url"] == "https://opentelemetry.io/schemas/1.27.0"

        gauge = scope_metrics[0]["metrics"][0]
        assert gauge["name"] == name
        assert gauge["unit"] == unit
        assert gauge["description"] == description

        gauge_data_point = gauge["gauge"]["data_points"][0]
        assert gauge_data_point["as_double"] == second_value
        assert set(expected_add_attributes) == set({item['key']:item['value']['string_value'] for item in gauge_data_point["attributes"]})
        assert "time_unix_nano" in gauge_data_point

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
        meter_name = "parametric-api"
        name = "counter1"
        unit = "triggers"
        description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name=meter_name, name=name, unit=unit, description=description)
            t.otel_counter_add(meter_name, name, unit, description, 2, {"test_attr": "test_value"})
            time.sleep(5)

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
            },
        ],
    )
    def test_otel_resource_attributes_mapping_sem_conv_1_27_0(self, test_agent, test_library):
        meter_name = "parametric-api"
        name = "counter1"
        unit = "triggers"
        description = "test_description"
        expected_attributes = {
            "deployment.environment.name": "test1",
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name, name, unit, description)
            t.otel_counter_add(meter_name, name, unit, description, 2, {"test_attr": "test_value"})
            time.sleep(5)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        pprint.pprint(metrics_data)

        # Assert that there is only one item in ResourceMetrics
        assert len(metrics_data) == 1

        # Assert that the ResourceMetrics has the expected resources
        resource_metrics = metrics_data[0]["resource_metrics"]
        resource = resource_metrics[0]["resource"]
        actual_attributes = {item['key']:item['value']['string_value'] for item in resource["attributes"]}
        assert set(expected_attributes) <= set(actual_attributes)

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
        meter_name = "parametric-api"
        name = "counter1"
        unit = "triggers"
        description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name, name, unit, description)
            t.otel_counter_add(meter_name, name, unit, description, 2, {"test_attr": "test_value"})
            time.sleep(5)

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
                "DD_ENV": "ignored_env",
                "DD_SERVICE": "ignored_service",
                "DD_VERSION": "ignored_version",
                "DD_TAGS": "foo:ignored_bar1,baz:ignored_qux1",
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1",
            },
        ],
    )
    def test_otel_resource_attributes_mapping_otel_preference(self, test_agent, test_library):
        meter_name = "parametric-api"
        name = "counter1"
        unit = "triggers"
        description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name, name, unit, description)
            t.otel_counter_add(meter_name, name, unit, description, 2, {"test_attr": "test_value"})
            time.sleep(5)

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

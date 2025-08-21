import time

import json
import pytest
import pprint

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
    "OTEL_METRIC_EXPORT_INTERVAL": "1000", # Reduce the interval to speed up the tests
    "CORECLR_ENABLE_PROFILING": "1",
}

@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api:
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
        counter_name = "counter1"
        counter_unit = "triggers"
        counter_description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description)
            t.otel_counter_add(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description, value=2, attributes={"test_attr": "test_value"})
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
        counter_name = "counter1"
        counter_unit = "triggers"
        counter_description = "test_description"
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
            t.otel_create_counter(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description)
            t.otel_counter_add(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description, value=2, attributes={"test_attr": "test_value"})
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
        counter_name = "counter1"
        counter_unit = "triggers"
        counter_description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description)
            t.otel_counter_add(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description, value=2, attributes={"test_attr": "test_value"})
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
        counter_name = "counter1"
        counter_unit = "triggers"
        counter_description = "test_description"
        expected_attributes = {
            "service.name": "test2",
            "service.version": "5",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            t.disable_traces_flush()
            t.otel_get_meter(name=meter_name)
            t.otel_create_counter(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description)
            t.otel_counter_add(meter_name=meter_name, name=counter_name, unit=counter_unit, description=counter_description, value=2, attributes={"test_attr": "test_value"})
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

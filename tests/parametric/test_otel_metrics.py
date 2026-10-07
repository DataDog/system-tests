from urllib.parse import urlparse
from utils import pytest

from utils import features, scenarios

from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary
from .otel_env_vars.utils import (
    DEFAULT_METER_NAME,
    DEFAULT_METER_VERSION,
    DEFAULT_SCHEMA_URL,
    DEFAULT_INSTRUMENT_UNIT,
    DEFAULT_INSTRUMENT_DESCRIPTION,
    DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
    DEFAULT_SCOPE_ATTRIBUTES,
    DEFAULT_MEASUREMENT_ATTRIBUTES,
    NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
    DEFAULT_ENVVARS,
    generate_default_counter_data_point,
    assert_metric_info,
    assert_sum_aggregation,
    assert_gauge_aggregation,
    assert_histogram_aggregation,
    find_metric_by_name,
    get_expected_bucket_counts,
)


@pytest.fixture
def otlp_metrics_endpoint_library_env(
    library_env: dict[str, str],
    endpoint_env: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
):
    """Set up a custom endpoint for OTLP metrics."""
    prev_value = library_env.get(endpoint_env)

    protocol = library_env.get("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", library_env.get("OTEL_EXPORTER_OTLP_PROTOCOL"))
    if protocol is None:
        raise ValueError(
            "One of the following environment variables must be set in library_env: OTEL_EXPORTER_OTLP_METRICS_PROTOCOL, OTEL_EXPORTER_OTLP_PROTOCOL"
        )

    port = test_agent_otlp_grpc_port if protocol == "grpc" else test_agent_otlp_http_port
    path = "/" if protocol == "grpc" or endpoint_env == "OTEL_EXPORTER_OTLP_ENDPOINT" else "/v1/metrics"

    library_env[endpoint_env] = f"http://{test_agent.container_name}:{port}{path}"
    yield library_env
    if prev_value is None:
        del library_env[endpoint_env]
    else:
        library_env[endpoint_env] = prev_value


@scenarios.parametric
@features.otel_metrics_api
@pytest.mark.parametrize("endpoint_env", ["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"])
@pytest.mark.usefixtures("otlp_metrics_endpoint_library_env")
class Test_Otel_Metrics_Configuration_Enabled:
    """Tests the enablement and disablement of the OTel Metrics API through the following configurations:
    - DD_METRICS_OTEL_ENABLED
    - OTEL_METRICS_EXPORTER

    Pin HTTP/protobuf in library_env because SDK protocol defaults differ across
    languages (for example, Python defaults to gRPC). This keeps the exporter and
    collector on the same transport while these tests exercise enablement.
    Use an explicit, reachable collector so disabling Datadog endpoint defaults
    cannot be mistaken for disabling export.
    """

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_METRIC_EXPORT_INTERVAL": "60000",
                "CORECLR_ENABLE_PROFILING": "1",
            },
        ],
    )
    def test_otlp_metrics_enabled(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Ensure that OTLP metrics are emitted."""

        name = "enabled-counter"
        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_METRICS_OTEL_ENABLED": "false",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_METRIC_EXPORT_INTERVAL": "60000",
                "CORECLR_ENABLE_PROFILING": "1",
            },
        ],
    )
    def test_otlp_metrics_disabled(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the Datadog enablement flag disables metrics export."""
        with test_library as t:
            generate_default_counter_data_point(t, "disabled-counter")

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_METRICS_EXPORTER": "none",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                "OTEL_METRIC_EXPORT_INTERVAL": "60000",
                "CORECLR_ENABLE_PROFILING": "1",
            },
        ],
    )
    def test_otlp_metrics_exporter_none(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure selecting no exporter disables metrics export."""
        name = "disabled-counter"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api_MeterProvider:
    """Tests the OpenTelemetry MeterProvider API functionality.

    This class validates the behavior of the MeterProvider, which is responsible for:
    - Creating and managing Meter instances
    - Producing one Instrumentation Scope per unique Meter

    Note: This class doesn't exhaustively test every combination of mismatching fields.
    Note: It is unspecified whether the Meter name is case-insensitive or case-sensitive when determining uniqueness.
    """

    def generate_metrics(
        self, metric_name: str, meter_names: list[str], test_library: APMLibrary, test_agent: TestAgentAPI
    ):
        with test_library as t:
            for meter_name in meter_names:
                t.otel_get_meter(meter_name, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
                t.otel_create_counter(meter_name, metric_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
                t.otel_counter_add(
                    meter_name,
                    metric_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)

        # Assert that there is only one metrics request per MetricsProvider.ForceFlush() call
        assert len(metrics) == 1
        # Assert that there is only one item in ResourceMetrics (one per tracer)
        resource_metrics = metrics[0]["resource_metrics"]
        assert len(resource_metrics) == 1

        # Assert that we get one ScopeMetrics per distinct Meter
        scope_metrics = resource_metrics[0]["scope_metrics"]
        assert len(scope_metrics) == 2
        return sorted(scope_metrics, key=lambda x: x["scope"]["name"])

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_get_meter_by_distinct(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        metric_name = "counter-test_get_meter_distinct"
        meter_names = [DEFAULT_METER_NAME, DEFAULT_METER_NAME, DEFAULT_METER_NAME + "-different"]
        metrics = self.generate_metrics(metric_name, meter_names, test_library, test_agent)
        distinct_meter_names = sorted(set(meter_names))
        # Assert that the ScopeMetrics has the correct Scope, SchemaUrl, and Metrics data
        for scope_metric, meter_name in zip(metrics, distinct_meter_names, strict=True):
            assert scope_metric["scope"]["name"] == meter_name
            assert len(scope_metric["metrics"]) == 1

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_get_meter_by_distinct_version(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        metric_name = "counter-test_get_meter_distinct_version"
        meter_names = [DEFAULT_METER_NAME, DEFAULT_METER_NAME, DEFAULT_METER_NAME + "-different"]
        metrics = self.generate_metrics(metric_name, meter_names, test_library, test_agent)
        distinct_meter_names = sorted(set(meter_names))
        for scope_metric, meter_name in zip(metrics, distinct_meter_names, strict=True):
            assert scope_metric["scope"]["name"] == meter_name
            assert scope_metric["scope"]["version"] == DEFAULT_METER_VERSION
            assert len(scope_metric["metrics"]) == 1

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_get_meter_by_distinct_scope_attributes(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        metric_name = "counter-test_get_meter_distinct_scope_attributes"
        meter_names = [DEFAULT_METER_NAME, DEFAULT_METER_NAME, DEFAULT_METER_NAME + "-different"]
        metrics = self.generate_metrics(metric_name, meter_names, test_library, test_agent)
        distinct_meter_names = sorted(set(meter_names))
        for scope_metric, meter_name in zip(metrics, distinct_meter_names, strict=True):
            assert scope_metric["scope"]["name"] == meter_name
            assert (
                DEFAULT_SCOPE_ATTRIBUTES.items()
                == {item["key"]: item["value"]["string_value"] for item in scope_metric["scope"]["attributes"]}.items()
            )

            assert len(scope_metric["metrics"]) == 1

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_get_meter_by_distinct_schema_url(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        metric_name = "counter-test_get_meter_distinct_schema_url"
        meter_names = [DEFAULT_METER_NAME, DEFAULT_METER_NAME, DEFAULT_METER_NAME + "-different"]
        metrics = self.generate_metrics(metric_name, meter_names, test_library, test_agent)
        distinct_meter_names = sorted(set(meter_names))
        for scope_metric, meter_name in zip(metrics, distinct_meter_names, strict=True):
            assert scope_metric["scope"]["name"] == meter_name
            assert scope_metric["schema_url"] == DEFAULT_SCHEMA_URL
            assert len(scope_metric["metrics"]) == 1


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api_Meter:
    """Tests the OpenTelemetry Meter API functionality.

    This class validates the behavior of the Meter, which is responsible for:
    - Creating each type of synchronous and asynchronous instruments through the Meter API
    - Handling instrument creation based on identifying fields (only name is case-insensitive)

    Note: This class doesn't exhaustively test every combination of mismatching fields.
    """

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_create_instruments_by_distinct(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        counter_name = "test_otel_create_counter"
        updowncounter_name = "test_otel_create_updowncounter"
        gauge_name = "test_otel_create_gauge"
        histogram_name = "test_otel_create_histogram"
        asynchronous_counter_name = "test_otel_create_asynchronous_counter"
        asynchronous_updowncounter_name = "test_otel_create_asynchronous_updowncounter"
        asynchronous_gauge_name = "test_otel_create_asynchronous_gauge"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)

            for instrument_name in [counter_name, counter_name.upper(), counter_name + "-different"]:
                t.otel_create_counter(
                    DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
                )
                t.otel_counter_add(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [updowncounter_name, updowncounter_name.upper(), updowncounter_name + "-different"]:
                t.otel_create_updowncounter(
                    DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
                )
                t.otel_updowncounter_add(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [gauge_name, gauge_name.upper(), gauge_name + "-different"]:
                t.otel_create_gauge(
                    DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
                )
                t.otel_gauge_record(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [histogram_name, histogram_name.upper(), histogram_name + "-different"]:
                t.otel_create_histogram(
                    DEFAULT_METER_NAME, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
                )
                t.otel_histogram_record(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [
                asynchronous_counter_name,
                asynchronous_counter_name.upper(),
                asynchronous_counter_name + "-different",
            ]:
                t.otel_create_asynchronous_counter(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [
                asynchronous_updowncounter_name,
                asynchronous_updowncounter_name.upper(),
                asynchronous_updowncounter_name + "-different",
            ]:
                t.otel_create_asynchronous_updowncounter(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            for instrument_name in [
                asynchronous_gauge_name,
                asynchronous_gauge_name.upper(),
                asynchronous_gauge_name + "-different",
            ]:
                t.otel_create_asynchronous_gauge(
                    DEFAULT_METER_NAME,
                    instrument_name,
                    DEFAULT_INSTRUMENT_UNIT,
                    DEFAULT_INSTRUMENT_DESCRIPTION,
                    42,
                    DEFAULT_MEASUREMENT_ATTRIBUTES,
                )

            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        # Instrument names are case-insensitive, so the measurements for 'name' and 'name_upper' will be recorded by the same Instrument,
        # and, as a result, will be aggregated together

        # Assert Counter aggregations
        for instrument_name, value in [(counter_name, 84), (counter_name + "-different", 42)]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_sum_aggregation(
                metric["sum"],
                "AGGREGATION_TEMPORALITY_DELTA",
                is_monotonic=True,
                value=value,
                attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

        # Assert UpDownCounter aggregations
        for instrument_name, value in [(updowncounter_name, 84), (updowncounter_name + "-different", 42)]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_sum_aggregation(
                metric["sum"],
                "AGGREGATION_TEMPORALITY_CUMULATIVE",
                is_monotonic=False,
                value=value,
                attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

        # Assert Gauge aggregations
        for instrument_name, value in [(gauge_name, 42), (gauge_name + "-different", 42)]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_gauge_aggregation(metric["gauge"], value, DEFAULT_MEASUREMENT_ATTRIBUTES)

        # Assert Histogram aggregations
        for instrument_name, values in [(histogram_name, [42, 42]), (histogram_name + "-different", [42])]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_histogram_aggregation(
                metric["histogram"],
                "AGGREGATION_TEMPORALITY_DELTA",
                count=len(values),
                sum_value=sum(values),
                min_value=min(values),
                max_value=max(values),
                bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
                bucket_counts=get_expected_bucket_counts(values, DEFAULT_EXPLICIT_BUCKET_BOUNDARIES),
                attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

        # Assert Asynchronous Counter aggregations
        for instrument_name, value in [(asynchronous_counter_name, 42), (asynchronous_counter_name + "-different", 42)]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_sum_aggregation(
                metric["sum"],
                "AGGREGATION_TEMPORALITY_DELTA",
                is_monotonic=True,
                value=value,
                attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

        # Assert Asynchronous UpDownCounter aggregations
        for instrument_name, value in [
            (asynchronous_updowncounter_name, 42),
            (asynchronous_updowncounter_name + "-different", 42),
        ]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_sum_aggregation(
                metric["sum"],
                "AGGREGATION_TEMPORALITY_CUMULATIVE",
                is_monotonic=False,
                value=value,
                attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

        # Assert Asynchronous Gauge aggregations
        for instrument_name, value in [(asynchronous_gauge_name, 42), (asynchronous_gauge_name + "-different", 42)]:
            metric = find_metric_by_name(scope_metrics[0], instrument_name)
            assert_metric_info(metric, instrument_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            assert_gauge_aggregation(metric["gauge"], value, DEFAULT_MEASUREMENT_ATTRIBUTES)


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Api_Instrument:
    """Tests the OpenTelemetry Instrument API functionality.

    This class validates the behavior of individual instruments, including:
    - Counter operations with both non-negative values and negative (invalid) values
    - Gauge operations
    - Histogram operations with bucket boundaries and counts
    - UpDownCounter operations
    - Within an Instrument/time-series, generating unique data points per set of measurement attributees
    """

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_counter_add_non_negative_and_negative_values(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        non_negative_value = 42
        second_non_negative_value = 21
        negative_value = -21
        name = f"counter1-{non_negative_value}-{second_non_negative_value}-{negative_value}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_non_negative_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                negative_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME
        metric = scope_metrics[0]["metrics"][0]
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_DELTA",
            is_monotonic=True,
            value=non_negative_value + second_non_negative_value,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_counter_add_non_negative_values_with_different_tags(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        non_negative_value = 42
        second_non_negative_value = 21
        name = f"counter1-{non_negative_value}-{second_non_negative_value}-different-tags"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_counter(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_non_negative_value,
                NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = scope_metrics[0]["metrics"][0]
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_DELTA",
            is_monotonic=True,
            value=non_negative_value,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_DELTA",
            is_monotonic=True,
            value=second_non_negative_value,
            attributes=NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_updowncounter_add_multiple_values(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        first_value = 42
        second_value = 21
        name = f"updowncounter1-{first_value}-{second_value}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_updowncounter(
                DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
            )
            t.otel_updowncounter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                first_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_updowncounter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=first_value + second_value,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_updowncounter_add_multiple_values_with_different_tags(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        first_value = 42
        second_value = 21
        name = f"updowncounter1-{first_value}-{second_value}-different-tags"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_updowncounter(
                DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
            )
            t.otel_updowncounter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                first_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_updowncounter_add(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_value,
                NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=first_value,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=second_value,
            attributes=NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_gauge_record_multiple_values(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        first_value = 42
        second_value = 21
        name = f"gauge-{first_value}-{second_value}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                first_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_gauge_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(metric["gauge"], second_value, DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_gauge_record_multiple_values_with_different_tags(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        first_value = 42
        second_value = 21
        name = f"gauge-{first_value}-{second_value}-different-tags"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_gauge(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                first_value,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_gauge_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                second_value,
                NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(metric["gauge"], first_value, DEFAULT_MEASUREMENT_ATTRIBUTES)
        assert_gauge_aggregation(metric["gauge"], second_value, NON_DEFAULT_MEASUREMENT_ATTRIBUTES)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_histogram_add_non_negative_and_negative_values(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        non_negative_value1 = 42
        non_negative_value2 = 21
        negative_value1 = -21
        name = f"histogram-{non_negative_value1}-{non_negative_value2}-{negative_value1}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value1,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value2,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                negative_value1,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        # Negative values are ignored by the Histogram Record API, so we only have 2 data points
        assert_histogram_aggregation(
            metric["histogram"],
            "AGGREGATION_TEMPORALITY_DELTA",
            count=2,
            sum_value=non_negative_value1 + non_negative_value2,
            min_value=min(non_negative_value1, non_negative_value2),
            max_value=max(non_negative_value1, non_negative_value2),
            bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
            bucket_counts=get_expected_bucket_counts(
                [non_negative_value1, non_negative_value2], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES
            ),
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_histogram_add_non_negative_values_with_different_tags(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        non_negative_value1 = 42
        non_negative_value2 = 21
        name = f"histogram-{non_negative_value1}-{non_negative_value2}-different-tags"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_histogram(DEFAULT_METER_NAME, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value1,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                non_negative_value2,
                NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        # Negative values are ignored by the Histogram Record API, so we only have 2 data points
        assert_histogram_aggregation(
            metric["histogram"],
            "AGGREGATION_TEMPORALITY_DELTA",
            count=1,
            sum_value=non_negative_value1,
            min_value=non_negative_value1,
            max_value=non_negative_value1,
            bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
            bucket_counts=get_expected_bucket_counts([non_negative_value1], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES),
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )
        assert_histogram_aggregation(
            metric["histogram"],
            "AGGREGATION_TEMPORALITY_DELTA",
            count=1,
            sum_value=non_negative_value2,
            min_value=non_negative_value2,
            max_value=non_negative_value2,
            bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
            bucket_counts=get_expected_bucket_counts([non_negative_value2], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES),
            attributes=NON_DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_asynchronous_counter_constant_callback_value(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        n = 42
        name = f"observablecounter1-{n}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_asynchronous_counter(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                n,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_DELTA",
            is_monotonic=True,
            value=n,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_asynchronous_updowncounter_constant_callback_value(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        n = 42
        name = f"observableupdowncounter1-{n}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_asynchronous_updowncounter(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                n,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_sum_aggregation(
            metric["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=n,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_otel_asynchronous_gauge_constant_callback_value(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        n = 42
        name = f"observablegauge-{n}"

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_asynchronous_gauge(
                DEFAULT_METER_NAME,
                name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                n,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )
            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]

        assert scope_metrics[0]["scope"]["name"] == DEFAULT_METER_NAME

        metric = find_metric_by_name(scope_metrics[0], name)
        assert_metric_info(metric, name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
        assert_gauge_aggregation(metric["gauge"], n, DEFAULT_MEASUREMENT_ATTRIBUTES)


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Configuration_OTLP_Exporter_Metrics_Endpoint:
    """Tests the OpenTelemetry OTLP exporter metrics endpoint configuration.

    This class validates the behavior of OTLP endpoint settings:
    - Custom endpoint configuration through environment variables OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
    """

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint_http_protobuf(
        self,
        library_env: dict[str, str],
        endpoint_env: str,
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = "test_otlp_custom_endpoint-counter"
        with test_library as t:
            generate_default_counter_data_point(t, name)

        assert urlparse(library_env[endpoint_env]).port == 4320, (
            f"Expected port 4320 in {urlparse(library_env[endpoint_env])}"
        )

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_otlp_custom_endpoint_grpc(
        self,
        library_env: dict[str, str],
        endpoint_env: str,
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = "test_otlp_custom_endpoint-counter"
        with test_library as t:
            generate_default_counter_data_point(t, name)

        assert urlparse(library_env[endpoint_env]).port == 4320, (
            f"Expected port 4320 in {urlparse(library_env[endpoint_env])}"
        )

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                4321,
            ),
        ],
    )
    def test_otlp_metrics_custom_endpoint_http_protobuf(
        self,
        library_env: dict[str, str],
        endpoint_env: str,
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = "test_otlp_metrics_custom_endpoint_http_protobuf-counter"
        with test_library as t:
            generate_default_counter_data_point(t, name)

        assert urlparse(library_env[endpoint_env]).port == 4321, (
            f"Expected port 4321 in {urlparse(library_env[endpoint_env])}"
        )

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_grpc_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                },
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                4321,
            ),
        ],
    )
    def test_otlp_metrics_custom_endpoint_grpc(
        self,
        library_env: dict[str, str],
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        endpoint_env: str,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Metrics are exported to custom OTLP endpoint."""
        name = "test_otlp_metrics_custom_endpoint_grpc-counter"
        with test_library as t:
            generate_default_counter_data_point(t, name)

        assert urlparse(library_env[endpoint_env]).port == 4321, (
            f"Expected port 4321 in {urlparse(library_env[endpoint_env])}"
        )

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None


@features.otel_metrics_api
@scenarios.parametric
class Test_Otel_Metrics_Host_Name:
    """Tests the OpenTelemetry metrics host name configuration.

    This class validates the behavior of host name configuration:
    - Host name configuration when both environment variables DD_HOSTNAME and DD_TRACE_REPORT_HOSTNAME are set
    - Resource attributes set through environment variable OTEL_RESOURCE_ATTRIBUTES are preserved
    """

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
    def test_hostname_from_dd_hostname(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """host.name is set from DD_HOSTNAME."""
        name = "test_hostname_from_dd_hostname"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}

        assert actual_attributes.get("host.name") == "ddhostname"

    @pytest.mark.parametrize(
        ("library_env", "host_attribute"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "OTEL_RESOURCE_ATTRIBUTES": "host.name=otelenv-host",
                    "DD_HOSTNAME": "ddhostname",
                },
                "host.name",
            ),
        ],
        ids=["host.name"],
    )
    def test_hostname_from_otel_resources(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, host_attribute: str
    ):
        """Hostname attributes in OTEL_RESOURCE_ATTRIBUTES takes precedence over DD_HOSTNAME."""
        name = "test_hostname_from_otel_resources"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}

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
        ],
        ids=["disabled", "default"],
    )
    def test_hostname_omitted(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """host.name is omitted when not configured."""
        name = "test_hostname_omitted"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}

        assert "host.name" not in actual_attributes


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Resource_Attributes:
    """Tests the OpenTelemetry metrics resource attributes configuration.

    This class validates the behavior of resource attribute configuration:
    - Resource attributes configuration through environment variable OTEL_RESOURCE_ATTRIBUTES
    - Datadog environment variable mapping (DD_ENV, DD_SERVICE, DD_VERSION, DD_TAGS) to resource attributes
    - The expected OpenTelemetry vs Datadog precedence is observed
    """

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=otelenv,service.name=service,service.version=2.0,foo=bar1,baz=qux1",
            },
        ],
    )
    def test_otel_resource_attributes(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)

        # Assert that the ResourceMetrics has the expected resources
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}
        assert expected_attributes.items() <= actual_attributes.items()

        # Add separate assertion for the DD_ENV mapping, whose semantic convention was updated in 1.27.0
        assert (
            actual_attributes.get("deployment.environment") == "otelenv"
            or actual_attributes.get("deployment.environment.name") == "otelenv"
        )

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
        ],
    )
    def test_otel_resource_attributes_populated_by_dd_otel_envs(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)

        # Assert that the ResourceMetrics has the expected resources
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}
        assert expected_attributes.items() <= actual_attributes.items()

        # Add separate assertion for the DD_ENV mapping, whose semantic convention was updated in 1.27.0
        assert (
            actual_attributes.get("deployment.environment") == "otelenv"
            or actual_attributes.get("deployment.environment.name") == "otelenv"
        )

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
    def test_dd_env_vars_override_otel(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        name = "counter1"
        expected_attributes = {
            "service.name": "service",
            "service.version": "2.0",
            "foo": "bar1",
            "baz": "qux1",
        }

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics_data = test_agent.wait_for_num_otlp_metrics(num=1)

        # Assert that the ResourceMetrics has the expected resources
        resource = metrics_data[0]["resource_metrics"][0]["resource"]
        actual_attributes = {item["key"]: item["value"]["string_value"] for item in resource["attributes"]}
        assert expected_attributes.items() <= actual_attributes.items()

        # Add separate assertion for the DD_ENV mapping, whose semantic convention was updated in 1.27.0
        assert (
            actual_attributes.get("deployment.environment") == "otelenv"
            or actual_attributes.get("deployment.environment.name") == "otelenv"
        )


@features.otel_metrics_api
@scenarios.parametric
class Test_Otel_Metrics_Telemetry:
    """Tests the OpenTelemetry metrics telemetry configuration reporting.

    This class validates the behavior of telemetry configuration reporting:
    - Telemetry configuration reporting for OTLP metrics exporter settings
    - Telemetry metrics reporting for OTLP metrics exporter operations
    """

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_METRICS_OTEL_ENABLED": "true",
                "CORECLR_ENABLE_PROFILING": "1",
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
            },
        ],
    )
    def test_telemetry_default_configurations(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test default configurations values for environment variables associated with the OTel Metrics features."""
        name = "test_telemetry_exporter_configurations"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_METRICS_TIMEOUT", 10000),
            ("OTEL_METRIC_EXPORT_INTERVAL", 10000),
            ("OTEL_METRIC_EXPORT_TIMEOUT", 7500),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "default", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert isinstance(config, dict)
            value = config.get("value")
            assert value is not None, f"Configuration value is None for '{expected_env}'"
            assert int(value) == expected_value, (
                f"Expected {expected_env} to be {expected_value}, configuration: {config}"
            )

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                    "OTEL_METRIC_EXPORT_INTERVAL": "5000",
                    "OTEL_METRIC_EXPORT_TIMEOUT": "5000",
                },
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                4320,
            ),
        ],
    )
    def test_telemetry_exporter_configurations(
        self,
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Test configurations starting with OTEL_EXPORTER_OTLP_ are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_exporter_configurations"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_TIMEOUT", "30000"),
            # TODO: uncomment when redaction is implemented everywhere
            # ("OTEL_EXPORTER_OTLP_HEADERS", "<redacted>"),
            ("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
            # TODO: uncomment when redaction is implemented everywhere
            # ("OTEL_EXPORTER_OTLP_ENDPOINT", "<redacted>"),
            ("OTEL_METRIC_EXPORT_INTERVAL", "5000"),
            ("OTEL_METRIC_EXPORT_TIMEOUT", "5000"),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert isinstance(config, dict)
            assert str(config.get("value")) == expected_value, (
                f"Expected {expected_env} to be {expected_value}, configuration: {config}"
            )

    @pytest.mark.parametrize(
        ("library_env", "endpoint_env", "test_agent_otlp_http_port"),
        [
            (
                {
                    "DD_METRICS_OTEL_ENABLED": "true",
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                    "OTEL_EXPORTER_OTLP_METRICS_TIMEOUT": "30000",
                    "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "api-key=key,other-config-value=value",
                    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
                },
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                4325,
            ),
        ],
    )
    def test_telemetry_exporter_metrics_configurations(
        self,
        otlp_metrics_endpoint_library_env: dict[str, str],  # noqa: ARG002
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        """Test Teleemtry configurations starting with OTEL_EXPORTER_OTLP_METRICS_ are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_exporter_metrics_configurations"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        configurations_by_name = test_agent.wait_for_telemetry_configurations()

        for expected_env, expected_value in [
            ("OTEL_EXPORTER_OTLP_METRICS_TIMEOUT", "30000"),
            # TODO: uncomment when redaction is implemented everywhere
            # ("OTEL_EXPORTER_OTLP_METRICS_HEADERS", "<redacted>"),
            ("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", "http/protobuf"),
            # TODO: uncomment when redaction is implemented everywhere
            # ("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "<redacted>"),
        ]:
            # Find configuration with env_var origin (since these are set via environment variables)
            config = test_agent.get_telemetry_config_by_origin(
                configurations_by_name, expected_env, "env_var", fallback_to_first=True
            )
            assert config is not None, f"No configuration found for '{expected_env}'"
            assert isinstance(config, dict)
            assert str(config.get("value")) == expected_value, (
                f"Expected {expected_env} to be {expected_value}, configuration: {config}"
            )

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                # Required by ruby metrics exporter, defaults to 10 seconds
                "DD_TELEMETRY_METRICS_AGGREGATION_INTERVAL": "0.1",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            },
        ],
    )
    def test_telemetry_metrics_http_protobuf(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test telemetry metrics are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_metrics"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        telemetry_metrics = test_agent.wait_for_telemetry_metrics("otel.metrics_export_attempts")
        assert telemetry_metrics, f"Expected metrics, got {telemetry_metrics}"
        for metric in telemetry_metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:http" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")

        telemetry_metrics = test_agent.wait_for_telemetry_metrics("otel.metrics_export_successes")
        assert telemetry_metrics, f"Expected metrics, got {telemetry_metrics}"
        for metric in telemetry_metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:http" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            },
        ],
    )
    def test_telemetry_metrics_grpc(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test telemetry metrics are sent to the instrumentation telemetry intake."""
        name = "test_telemetry_metrics"

        with test_library as t:
            generate_default_counter_data_point(t, name)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        telemetry_metrics = test_agent.wait_for_telemetry_metrics("otel.metrics_export_attempts")
        assert telemetry_metrics, f"Expected metrics, got {telemetry_metrics}"
        for metric in telemetry_metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:grpc" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")

        telemetry_metrics = test_agent.wait_for_telemetry_metrics("otel.metrics_export_successes")
        assert telemetry_metrics, f"Expected metrics, got {telemetry_metrics}"
        for metric in telemetry_metrics:
            assert metric.get("type") == "count", f"Expected count, got {metric}"
            assert len(metric.get("points", [])) > 0, f"Expected at least 1 point, got {metric}"
            assert metric.get("common") is True, f"Expected common, got {metric}"
            assert metric.get("tags") is not None, f"Expected tags, got {metric}"
            assert "protocol:grpc" in metric.get("tags")
            assert "encoding:protobuf" in metric.get("tags")

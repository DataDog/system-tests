"""OTLP exporter temporality configuration, observed in exported instrument data.

https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/otlp/
"""

from utils import features, pytest, scenarios
from tests.parametric.conftest import APMLibrary
from utils.docker_fixtures import TestAgentAPI
from .utils import (
    DEFAULT_METER_NAME,
    DEFAULT_METER_VERSION,
    DEFAULT_SCHEMA_URL,
    DEFAULT_INSTRUMENT_UNIT,
    DEFAULT_INSTRUMENT_DESCRIPTION,
    DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
    DEFAULT_SCOPE_ATTRIBUTES,
    DEFAULT_MEASUREMENT_ATTRIBUTES,
    DEFAULT_ENVVARS,
    assert_sum_aggregation,
    assert_gauge_aggregation,
    assert_histogram_aggregation,
    find_metric_by_name,
    get_expected_bucket_counts,
)


@scenarios.parametric
@features.otel_metrics_api
class Test_Otel_Metrics_Configuration_Temporality_Preference:
    """Tests the OpenTelemetry metrics aggregation temporality preference configuration.

    This class validates the behavior of temporality preference configuration:
    - Default temporality behavior is set to DELTA
    - Configuration of temporality preference through the OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE environment variable
    - Proper instrument-specific aggregation temporality in exported metrics
    """

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
            },
            {**DEFAULT_ENVVARS, "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "DELTA"},
            {**DEFAULT_ENVVARS, "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "CUMULATIVE"},
        ],
        ids=["default", "delta", "cumulative"],
    )
    def test_otel_aggregation_temporality(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ):
        temporality_preference = library_env.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "default")

        counter_name = f"test_otel_aggregation_temporality_counter-{temporality_preference.lower()}"
        updowncounter_name = f"test_otel_aggregation_temporality_updowncounter-{temporality_preference.lower()}"
        gauge_name = f"test_otel_aggregation_temporality_gauge-{temporality_preference.lower()}"
        histogram_name = f"test_otel_aggregation_temporality_histogram-{temporality_preference.lower()}"
        asynchronous_counter_name = (
            f"test_otel_aggregation_temporality_asynchronous_counter-{temporality_preference.lower()}"
        )
        asynchronous_updowncounter_name = (
            f"test_otel_aggregation_temporality_asynchronous_updowncounter-{temporality_preference.lower()}"
        )
        asynchronous_gauge_name = (
            f"test_otel_aggregation_temporality_asynchronous_gauge-{temporality_preference.lower()}"
        )

        with test_library as t:
            t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
            t.otel_create_counter(
                DEFAULT_METER_NAME, counter_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
            )
            t.otel_counter_add(
                DEFAULT_METER_NAME,
                counter_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_updowncounter(
                DEFAULT_METER_NAME, updowncounter_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
            )
            t.otel_updowncounter_add(
                DEFAULT_METER_NAME,
                updowncounter_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_gauge(DEFAULT_METER_NAME, gauge_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
            t.otel_gauge_record(
                DEFAULT_METER_NAME,
                gauge_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_histogram(
                DEFAULT_METER_NAME, histogram_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION
            )
            t.otel_histogram_record(
                DEFAULT_METER_NAME,
                histogram_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_asynchronous_counter(
                DEFAULT_METER_NAME,
                asynchronous_counter_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_asynchronous_updowncounter(
                DEFAULT_METER_NAME,
                asynchronous_updowncounter_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_create_asynchronous_gauge(
                DEFAULT_METER_NAME,
                asynchronous_gauge_name,
                DEFAULT_INSTRUMENT_UNIT,
                DEFAULT_INSTRUMENT_DESCRIPTION,
                42,
                DEFAULT_MEASUREMENT_ATTRIBUTES,
            )

            t.otel_metrics_force_flush()

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        scope_metrics = metrics[0]["resource_metrics"][0]["scope_metrics"]
        assert scope_metrics is not None

        counter = find_metric_by_name(scope_metrics[0], counter_name)
        assert_sum_aggregation(
            counter["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE"
            if temporality_preference == "CUMULATIVE"
            else "AGGREGATION_TEMPORALITY_DELTA",
            is_monotonic=True,
            value=42,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

        updowncounter = find_metric_by_name(scope_metrics[0], updowncounter_name)
        assert_sum_aggregation(
            updowncounter["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=42,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

        # Note: Temporality does not affect the OTLP metric for Gauges
        gauge = find_metric_by_name(scope_metrics[0], gauge_name)
        assert_gauge_aggregation(gauge["gauge"], 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

        histogram = find_metric_by_name(scope_metrics[0], histogram_name)
        assert_histogram_aggregation(
            histogram["histogram"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE"
            if temporality_preference == "CUMULATIVE"
            else "AGGREGATION_TEMPORALITY_DELTA",
            count=1,
            sum_value=42,
            min_value=42,
            max_value=42,
            bucket_boundaries=DEFAULT_EXPLICIT_BUCKET_BOUNDARIES,
            bucket_counts=get_expected_bucket_counts([42], DEFAULT_EXPLICIT_BUCKET_BOUNDARIES),
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

        asynchronous_counter = find_metric_by_name(scope_metrics[0], asynchronous_counter_name)
        assert_sum_aggregation(
            asynchronous_counter["sum"],
            "AGGREGATION_TEMPORALITY_DELTA"
            if temporality_preference in ("DELTA", "default")
            else "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=True,
            value=42,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

        asynchronous_updowncounter = find_metric_by_name(scope_metrics[0], asynchronous_updowncounter_name)
        assert_sum_aggregation(
            asynchronous_updowncounter["sum"],
            "AGGREGATION_TEMPORALITY_CUMULATIVE",
            is_monotonic=False,
            value=42,
            attributes=DEFAULT_MEASUREMENT_ATTRIBUTES,
        )

        # Note: Temporality does not affect the OTLP metric for Gauges
        asynchronous_gauge = find_metric_by_name(scope_metrics[0], asynchronous_gauge_name)
        assert_gauge_aggregation(asynchronous_gauge["gauge"], 42, DEFAULT_MEASUREMENT_ATTRIBUTES)

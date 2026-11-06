"""OTLP exporter temporality configuration, observed in exported instrument data.

https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/otlp/
"""

from typing import Final

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

VARIABLE_NAME = "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"
LIBRARY_ENV: Final = {
    **DEFAULT_ENVVARS,
    VARIABLE_NAME: None,
    "DD_OTLP_METRICS_TEMPORALITY_PREFERENCE": None,
    # Setting this to none disables the entire Node.js tracer, including metrics.
    "OTEL_TRACES_EXPORTER": None,
    "OTEL_LOGS_EXPORTER": "none",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
}

# One stable-value matrix, split into methods so manifests can distinguish
# missing LowMemory support from case-insensitive parsing gaps and Delta-only bugs.
STABLE_VALUES: Final[tuple[tuple[str, str], ...]] = (
    ("cumulative", "cumulative"),
    ("CUMULATIVE", "cumulative"),
    ("CuMuLaTiVe", "cumulative"),
    ("delta", "delta"),
    ("DELTA", "delta"),
    ("DeLtA", "delta"),
    ("lowmemory", "lowmemory"),
    ("LOWMEMORY", "lowmemory"),
    ("LoWmEmOrY", "lowmemory"),
)


def _assert_temporality(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    temporality_preference: str,
    *,
    check_payload: bool = False,
) -> None:
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
    asynchronous_gauge_name = f"test_otel_aggregation_temporality_asynchronous_gauge-{temporality_preference.lower()}"

    with test_library as t:
        t.otel_get_meter(DEFAULT_METER_NAME, DEFAULT_METER_VERSION, DEFAULT_SCHEMA_URL, DEFAULT_SCOPE_ATTRIBUTES)
        t.otel_create_counter(DEFAULT_METER_NAME, counter_name, DEFAULT_INSTRUMENT_UNIT, DEFAULT_INSTRUMENT_DESCRIPTION)
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

        if check_payload:
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

        if check_payload:
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

    expected_sync = "CUMULATIVE" if temporality_preference == "cumulative" else "DELTA"
    expected_async = "DELTA" if temporality_preference == "delta" else "CUMULATIVE"
    for name, aggregation, expected in (
        (counter_name, "sum", expected_sync),
        (histogram_name, "histogram", expected_sync),
        (asynchronous_counter_name, "sum", expected_async),
        (updowncounter_name, "sum", "CUMULATIVE"),
        (asynchronous_updowncounter_name, "sum", "CUMULATIVE"),
    ):
        metric = find_metric_by_name(scope_metrics[0], name)
        assert metric[aggregation]["aggregation_temporality"] == f"AGGREGATION_TEMPORALITY_{expected}", name
    if not check_payload:
        return

    counter = find_metric_by_name(scope_metrics[0], counter_name)
    assert_sum_aggregation(
        counter["sum"],
        "AGGREGATION_TEMPORALITY_CUMULATIVE"
        if temporality_preference == "cumulative"
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
        if temporality_preference == "cumulative"
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
        "AGGREGATION_TEMPORALITY_DELTA" if temporality_preference == "delta" else "AGGREGATION_TEMPORALITY_CUMULATIVE",
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


@scenarios.parametric
@features.otel_metrics_api
@features.otel_exporter_otlp_metrics_temporality_preference
class Test_OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE:
    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "cumulative" and wire in (wire.lower(), wire.upper())
        ],
    )
    def test_cumulative_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "delta" and wire in (wire.lower(), wire.upper())
        ],
    )
    def test_delta_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "lowmemory" and wire in (wire.lower(), wire.upper())
        ],
    )
    def test_lowmemory(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "cumulative" and wire not in (wire.lower(), wire.upper())
        ],
    )
    def test_cumulative_case_insensitive(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str
    ) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "delta" and wire not in (wire.lower(), wire.upper())
        ],
    )
    def test_delta_case_insensitive(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: wire}, expected, id=wire)
            for wire, expected in STABLE_VALUES
            if expected == "lowmemory" and wire not in (wire.lower(), wire.upper())
        ],
    )
    def test_lowmemory_case_insensitive(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str
    ) -> None:
        _assert_temporality(test_agent, test_library, expected)

    @pytest.mark.parametrize("library_env", [pytest.param(LIBRARY_ENV, id="unset")])
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_temporality(test_agent, test_library, "cumulative")

    @pytest.mark.parametrize("library_env", [pytest.param(LIBRARY_ENV, id="unset")])
    def test_datadog_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Preserve the documented Datadog Delta default separately from OTel compliance."""
        _assert_temporality(test_agent, test_library, "delta")

    @pytest.mark.parametrize("library_env", [pytest.param({**LIBRARY_ENV, VARIABLE_NAME: ""}, id="empty")])
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_temporality(test_agent, test_library, "delta")

    @pytest.mark.parametrize("library_env", [pytest.param({**LIBRARY_ENV, VARIABLE_NAME: "invalid"}, id="invalid")])
    def test_invalid_value_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_temporality(test_agent, test_library, "delta")

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param(LIBRARY_ENV, "delta", id="unset"),
            pytest.param({**LIBRARY_ENV, VARIABLE_NAME: "DELTA"}, "delta", id="DELTA"),
        ],
    )
    def test_exported_payload(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        """Preserve the original test's values, attributes, timestamps, and histogram buckets."""
        _assert_temporality(test_agent, test_library, expected, check_payload=True)

    @pytest.mark.parametrize(
        "library_env", [pytest.param({**LIBRARY_ENV, VARIABLE_NAME: "CUMULATIVE"}, id="CUMULATIVE")]
    )
    def test_exported_payload_cumulative(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Keep Cumulative payload coverage enabled independently of Delta support."""
        _assert_temporality(test_agent, test_library, "cumulative", check_payload=True)

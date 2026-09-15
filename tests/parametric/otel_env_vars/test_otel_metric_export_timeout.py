import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


DEFAULT_ENVIRONMENT = {
    # Enable the OTel metrics pipeline in tracers where it is not enabled by default.
    "DD_METRICS_OTEL_ENABLED": "true",
    # Prevent unrelated runtime metrics from satisfying the OTLP metrics wait.
    "DD_RUNTIME_METRICS_ENABLED": "false",
    # Deliver configuration telemetry promptly instead of waiting for the normal heartbeat.
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    # Avoid periodic exports so the test observes only the metric it explicitly flushes.
    "OTEL_METRIC_EXPORT_INTERVAL": "60000",
}

STABLE_VALUES = [
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "0"}, 0, id="zero-unlimited"),
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "1"}, 1, id="minimum-finite"),
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "12000"}, 12000, id="twelve-seconds"),
    pytest.param(
        {**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "2147483647"},
        2147483647,
        id="int32-max",
    ),
]

INVALID_VALUES = [
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "-1"}, id="negative"),
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "not-a-timeout"}, id="not-an-integer"),
]

UNSET_AND_EMPTY_VALUES = [
    pytest.param(DEFAULT_ENVIRONMENT, id="unset"),
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": ""}, id="empty"),
]


def _metric_export_timeout_configuration(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
) -> dict[str, object]:
    meter_name = "otel-metric-export-timeout"
    instrument_name = "otel.metric.export.timeout"

    with test_library as library:
        library.otel_get_meter(meter_name, "1.0.0", "", {})
        library.otel_create_counter(meter_name, instrument_name, "1", "Metric SDK initialization")
        library.otel_counter_add(meter_name, instrument_name, "1", "Metric SDK initialization", 1, {})
        library.otel_metrics_force_flush()

    test_agent.wait_for_num_otlp_metrics(num=1)
    configurations = test_agent.wait_for_telemetry_configurations()
    config = test_agent.get_telemetry_config_by_origin(
        configurations,
        "OTEL_METRIC_EXPORT_TIMEOUT",
        "env_var",
        fallback_to_first=True,
    )
    assert isinstance(config, dict), "No telemetry configuration found for 'OTEL_METRIC_EXPORT_TIMEOUT'"

    return config


def _metric_export_timeout(config: dict[str, object]) -> int:
    value = config.get("value")
    assert value is not None, f"OTEL_METRIC_EXPORT_TIMEOUT value is missing from configuration: {config}"
    return int(str(value))


@scenarios.parametric
@features.otel_metric_export_timeout
class Test_OTEL_METRIC_EXPORT_TIMEOUT:
    @pytest.mark.parametrize(("library_env", "expected"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: int,
    ) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert config.get("origin") == "env_var"
        assert _metric_export_timeout(config) == expected

    @pytest.mark.parametrize("library_env", INVALID_VALUES)
    def test_invalid_values_use_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert config.get("origin") == "default"
        assert _metric_export_timeout(config) >= 0

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_unset_and_empty_use_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert config.get("origin") == "default"
        assert _metric_export_timeout(config) >= 0

    # All DD SDKs but PHP intentionally default to 7500 ms,
    # which is not the OTel specification default of 30000 ms. This test is irrelevant for them.
    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert _metric_export_timeout(config) == 30000

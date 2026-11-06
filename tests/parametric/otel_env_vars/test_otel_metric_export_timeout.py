from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


DEFAULT_ENVIRONMENT = {
    # Enable the OTel metrics pipeline in tracers where it is not enabled by default.
    "DD_METRICS_OTEL_ENABLED": "true",
    # Deliver configuration telemetry promptly instead of waiting for the normal heartbeat.
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
}

STABLE_VALUES = [
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_METRIC_EXPORT_TIMEOUT": "0"}, 0, id="zero-unlimited"),
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


def _metric_export_timeout_configuration(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
) -> dict[str, object]:
    meter_name = "otel-metric-export-timeout"
    with test_library as library:
        library.otel_get_meter(meter_name, "1.0.0", "", {})

    configurations = test_agent.wait_for_telemetry_configurations()
    configs = configurations.get("OTEL_METRIC_EXPORT_TIMEOUT")
    assert configs, "No telemetry configuration found for 'OTEL_METRIC_EXPORT_TIMEOUT'"

    return configs[0]


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
        assert _metric_export_timeout(config) == expected

    @pytest.mark.parametrize("library_env", INVALID_VALUES)
    def test_invalid_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert _metric_export_timeout(config) >= 0

    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_unset_uses_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert _metric_export_timeout(config) >= 0

    # All DD SDKs but PHP intentionally default to 7500 ms,
    # which is not the OTel specification default of 30000 ms. This test is irrelevant for them.
    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_spec_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        config = _metric_export_timeout_configuration(test_agent, test_library)
        assert _metric_export_timeout(config) == 30000

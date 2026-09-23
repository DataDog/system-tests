import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_TIMEOUT"
DEFAULT_TIMEOUT_MS = 10000
JAVA_TELEMETRY_NAME = "DD_OTLP_METRICS_TIMEOUT"
METRICS_ENVIRONMENT = {
    "DD_METRICS_OTEL_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
}

STABLE_VALUES = [
    pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "500"}, 500, id="500-ms"),
    pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "0"}, 0, id="zero-unlimited"),
]


def _configuration_name(library: APMLibrary) -> str:
    if library.lang == "java":
        return JAVA_TELEMETRY_NAME
    return VARIABLE_NAME


def _timeout_value(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    with test_library as library:
        library.otel_get_meter("otel-exporter-otlp-timeout", "1.0.0", "", {})
        configuration_name = _configuration_name(library)

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(configuration_name)
    assert entries, f"No telemetry configuration '{configuration_name}'"

    value = entries[0].get("value")
    assert value is not None, f"{configuration_name} value is missing from configuration: {entries[0]}"
    return int(str(value))


@scenarios.parametric
@features.otel_logs_enabled
@features.otel_exporter_otlp_timeout
class Test_OTEL_EXPORTER_OTLP_TIMEOUT:
    @pytest.mark.parametrize(("library_env", "expected_value"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected_value: int,
    ) -> None:
        assert _timeout_value(test_agent, test_library) == expected_value

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "-1"}, id="negative")],
    )
    def test_invalid_value_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param(METRICS_ENVIRONMENT, id="unset")],
    )
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: ""}, id="empty")],
    )
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

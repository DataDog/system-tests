import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT"
DEFAULT_TIMEOUT_MS = 10000
JAVA_TELEMETRY_NAME = "DD_OTLP_LOGS_TIMEOUT"
LOGS_ENVIRONMENT = {
    "DD_LOGS_OTEL_ENABLED": "true",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
}
LOGGER_NAME = "otel-exporter-otlp-logs-timeout"
LOG_MESSAGE = "otel-exporter-otlp-logs-timeout"

STABLE_VALUES = [
    pytest.param({**LOGS_ENVIRONMENT, VARIABLE_NAME: "500"}, 500, id="500-ms"),
    pytest.param({**LOGS_ENVIRONMENT, VARIABLE_NAME: "0"}, 0, id="zero-unlimited"),
]


def _configuration_name(library: APMLibrary) -> str:
    if library.lang == "java":
        return JAVA_TELEMETRY_NAME
    return VARIABLE_NAME


def _timeout_value(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    with test_library as library:
        library.create_logger(LOGGER_NAME, LogLevel.INFO)
        library.write_log(LOGGER_NAME, LogLevel.INFO, LOG_MESSAGE)
        configuration_name = _configuration_name(library)

    assert test_agent.wait_for_num_log_payloads(1)
    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(configuration_name)
    assert entries, f"No telemetry configuration '{configuration_name}'"

    value = entries[0].get("value")
    assert value is not None, f"{configuration_name} value is missing from configuration: {entries[0]}"
    return int(str(value))


@scenarios.parametric
@features.otel_logs_enabled
@features.otel_exporter_otlp_logs_timeout
class Test_OTEL_EXPORTER_OTLP_LOGS_TIMEOUT:
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
        [pytest.param({**LOGS_ENVIRONMENT, VARIABLE_NAME: "-1"}, id="negative")],
    )
    def test_invalid_value_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param(LOGS_ENVIRONMENT, id="unset")],
    )
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**LOGS_ENVIRONMENT, VARIABLE_NAME: ""}, id="empty")],
    )
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

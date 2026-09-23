import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_TRACES_TIMEOUT"
DEFAULT_TIMEOUT_MS = 10000
JAVA_TELEMETRY_NAME = "DD_OTLP_TRACES_TIMEOUT"
TRACES_ENVIRONMENT = {
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    "DD_TRACE_OTEL_ENABLED": "true",
}
SPAN_NAME = "otel-exporter-otlp-traces-timeout"

STABLE_VALUES = [
    pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "500"}, 500, id="500-ms"),
    pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "0"}, 0, id="zero-unlimited"),
]


def _configuration_name(library: APMLibrary) -> str:
    if library.lang == "java":
        return JAVA_TELEMETRY_NAME
    return VARIABLE_NAME


def _timeout_value(test_agent: TestAgentAPI, test_library: APMLibrary) -> int:
    with test_library as library:
        with library.dd_start_span(name=SPAN_NAME):
            pass
        assert library.dd_flush()
        configuration_name = _configuration_name(library)

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(configuration_name)
    assert entries, f"No telemetry configuration '{configuration_name}'"

    value = entries[0].get("value")
    assert value is not None, f"{configuration_name} value is missing from configuration: {entries[0]}"
    return int(str(value))


@scenarios.parametric
@features.otel_exporter_otlp_traces_timeout
class Test_OTEL_EXPORTER_OTLP_TRACES_TIMEOUT:
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
        [pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "-1"}, id="negative")],
    )
    def test_invalid_value_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param(TRACES_ENVIRONMENT, id="unset")],
    )
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: ""}, id="empty")],
    )
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        assert _timeout_value(test_agent, test_library) == DEFAULT_TIMEOUT_MS

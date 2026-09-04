import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


OTEL_SDK_DISABLED = "OTEL_SDK_DISABLED"
DD_TRACE_OTEL_ENABLED = "DD_TRACE_OTEL_ENABLED"
DD_METRICS_OTEL_ENABLED = "DD_METRICS_OTEL_ENABLED"
DD_LOGS_OTEL_ENABLED = "DD_LOGS_OTEL_ENABLED"


def _library_env(otel_sdk_disabled: str | None) -> dict[str, str | None]:
    return {
        OTEL_SDK_DISABLED: otel_sdk_disabled,
        DD_TRACE_OTEL_ENABLED: None,
        DD_METRICS_OTEL_ENABLED: "false",
        DD_LOGS_OTEL_ENABLED: "false",
    }


def _otel_sdk_disabled(test_agent: TestAgentAPI, test_library: APMLibrary) -> bool:
    with test_library as library:
        if library.lang == "nodejs":
            value = nodejs_telemetry_value(test_agent, "otel_sdk_disabled")
            assert isinstance(value, bool)
            return value

        otel_enabled = library.config()["dd_trace_otel_enabled"]

    assert otel_enabled in ("true", "false")
    return otel_enabled == "false"


STABLE_VALUES = [
    pytest.param(
        _library_env("true"),
        True,
        id="true",
    ),
    pytest.param(
        _library_env("false"),
        False,
        id="false",
    ),
]


@scenarios.parametric
@features.otel_sdk_disabled
class Test_OTEL_SDK_DISABLED:
    @pytest.mark.parametrize(("library_env", "expected"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: bool,
    ):
        assert _otel_sdk_disabled(test_agent, test_library) is expected

    @pytest.mark.parametrize(
        "library_env",
        [_library_env(None)],
    )
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        assert _otel_sdk_disabled(test_agent, test_library) is False

    @pytest.mark.parametrize(
        "library_env",
        [_library_env("true") | {DD_TRACE_OTEL_ENABLED: "true"}],
    )
    def test_datadog_configuration_takes_precedence(self, test_library: APMLibrary):
        with test_library as library:
            config = library.config()

        assert config["dd_trace_otel_enabled"] == "true"

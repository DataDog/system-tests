import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


def _otel_sdk_disabled(test_agent: TestAgentAPI, library: APMLibrary) -> bool:
    if library.lang == "nodejs":
        value = nodejs_telemetry_value(test_agent, "otel_sdk_disabled")
        assert isinstance(value, bool)
        return value

    otel_enabled = library.config()["dd_trace_otel_enabled"]

    assert otel_enabled in ("true", "false")
    return otel_enabled == "false"


STABLE_VALUES = [
    pytest.param(
        {
            "OTEL_SDK_DISABLED": "true",
            "DD_TRACE_OTEL_ENABLED": None,
        },
        True,
        id="true",
    ),
    pytest.param(
        {
            "OTEL_SDK_DISABLED": "false",
            "DD_TRACE_OTEL_ENABLED": None,
        },
        False,
        id="false",
    ),
]

UNSET_AND_EMPTY_VALUES = [
    pytest.param(
        {
            "DD_TRACE_OTEL_ENABLED": None,
        },
        id="unset",
    ),
    pytest.param(
        {
            "OTEL_SDK_DISABLED": "",
            "DD_TRACE_OTEL_ENABLED": None,
        },
        id="empty",
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
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is expected

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is False

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
            }
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is False
            config = library.config()

        assert config["dd_trace_otel_enabled"] == "true"

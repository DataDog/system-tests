from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_TRACES_TIMEOUT"
DEFAULT_TIMEOUT_MS = 10000
TRACES_ENVIRONMENT = {
    "DD_TRACE_OTEL_ENABLED": "true",
}

STABLE_VALUES = [
    pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "500"}, 500, id="500-ms"),
]


def _timeout_value(test_library: APMLibrary) -> int:
    with test_library as library:
        value = library.config().get("otel_exporter_otlp_traces_timeout_ms")

    assert value is not None, "No effective timeout configuration 'otel_exporter_otlp_traces_timeout_ms'"
    return int(value)


@scenarios.parametric
@features.otel_exporter_otlp_traces_timeout
class Test_OTEL_EXPORTER_OTLP_TRACES_TIMEOUT:
    @pytest.mark.parametrize(("library_env", "expected_value"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_library: APMLibrary,
        *,
        expected_value: int,
    ) -> None:
        assert _timeout_value(test_library) == expected_value

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "0"}, id="zero-unlimited")],
    )
    def test_zero_is_unlimited(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == 0

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: "-1"}, id="negative")],
    )
    def test_invalid_value_is_ignored(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param(TRACES_ENVIRONMENT, id="unset")],
    )
    def test_default_matches_specification(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**TRACES_ENVIRONMENT, VARIABLE_NAME: ""}, id="empty")],
    )
    def test_empty_is_treated_as_unset(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

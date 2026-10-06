from utils import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios


VARIABLE_NAME = "OTEL_EXPORTER_OTLP_TIMEOUT"
DEFAULT_TIMEOUT_MS = 10000
METRICS_ENVIRONMENT = {
    "DD_METRICS_OTEL_ENABLED": "true",
}

STABLE_VALUES = [
    pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "500"}, 500, id="500-ms"),
    pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "0"}, 0, id="zero-unlimited"),
]


def _timeout_value(test_library: APMLibrary) -> int:
    with test_library as library:
        library.otel_get_meter("otel-exporter-otlp-timeout", "1.0.0", "", {})
        value = library.config().get("otel_exporter_otlp_metrics_timeout_ms")

    assert value is not None, "No effective timeout configuration 'otel_exporter_otlp_metrics_timeout_ms'"
    return int(value)


@scenarios.parametric
@features.otel_exporter_otlp_timeout
class Test_OTEL_EXPORTER_OTLP_TIMEOUT:
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
        [pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: "-1"}, id="negative")],
    )
    def test_invalid_value_is_ignored(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param(METRICS_ENVIRONMENT, id="unset")],
    )
    def test_default_matches_specification(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**METRICS_ENVIRONMENT, VARIABLE_NAME: ""}, id="empty")],
    )
    def test_empty_is_treated_as_unset(self, test_library: APMLibrary) -> None:
        assert _timeout_value(test_library) == DEFAULT_TIMEOUT_MS

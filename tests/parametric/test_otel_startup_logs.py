"""OTel fields in the tracer's startup configuration JSON that depend on the tracer configuration.

OTEL_ENABLED is true only when DD_TRACE_OTEL_SEMANTICS_ENABLED is enabled and at least one
OpenTelemetry signal is enabled: the tracing API bridge, OTLP metrics, OTLP logs or OTLP traces.
"""

from utils import pytest

from utils import features, scenarios

from .conftest import APMLibrary
from .utils import get_startup_logs
from tests.otel.utils import assert_configuration_keys, parse_startup_configurations

parametrize = pytest.mark.parametrize

# Parametric enables the OpenTelemetry tracing API bridge by default, so it is turned off explicitly.
_OTEL_SIGNALS_DISABLED: dict[str, str | None] = {
    "DD_TRACE_OTEL_ENABLED": "false",
    "DD_METRICS_OTEL_ENABLED": "false",
    "DD_LOGS_OTEL_ENABLED": "false",
    "OTEL_TRACES_EXPORTER": None,
}
# Each entry enables a single OpenTelemetry signal on top of _OTEL_SIGNALS_DISABLED.
_OTEL_SIGNALS: dict[str, dict[str, str]] = {
    "tracing_api": {"DD_TRACE_OTEL_ENABLED": "true"},
    "otlp_metrics": {"DD_METRICS_OTEL_ENABLED": "true"},
    "otlp_logs": {"DD_LOGS_OTEL_ENABLED": "true"},
    # Some tracers only export OTLP traces over HTTP.
    "otlp_traces": {"OTEL_TRACES_EXPORTER": "otlp", "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf"},
}


def _assert_otel_enabled(test_library: APMLibrary, *, expected: bool) -> None:
    logs = get_startup_logs(test_library, required=True)
    assert logs is not None
    # Do not combine values across startup records from different workers/processes.
    for index, configuration in enumerate(parse_startup_configurations(logs)):
        assert_configuration_keys(index, configuration, {"OTEL_ENABLED"})
        actual = configuration["OTEL_ENABLED"]
        assert actual is expected, f"Startup configuration #{index + 1}: OTEL_ENABLED={actual!r}; expected {expected!r}"


@scenarios.parametric
@features.log_tracer_status_at_startup
class Test_OTEL_Startup_Logs:
    @parametrize(
        "library_env",
        [
            pytest.param({**_OTEL_SIGNALS_DISABLED, **signal, "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true"}, id=name)
            for name, signal in _OTEL_SIGNALS.items()
        ],
    )
    def test_otel_enabled_with_semantics_and_signal(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=True)

    @parametrize("library_env", [{**_OTEL_SIGNALS_DISABLED, "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true"}])
    def test_otel_enabled_without_signal(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

    @parametrize(
        "library_env",
        [
            pytest.param({**_OTEL_SIGNALS_DISABLED, **signal, "DD_TRACE_OTEL_SEMANTICS_ENABLED": "false"}, id=name)
            for name, signal in _OTEL_SIGNALS.items()
        ],
    )
    def test_otel_enabled_without_semantics(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

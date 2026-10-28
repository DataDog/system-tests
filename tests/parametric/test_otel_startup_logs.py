"""OTel fields in the tracer's startup configuration JSON that depend on the tracer configuration.

OTEL_ENABLED reports whether the tracer works in OpenTelemetry mode: DD_TRACE_OTEL_SEMANTICS_ENABLED is
enabled and at least one OpenTelemetry signal is on. The signals are the OpenTelemetry tracing API
(DD_TRACE_OTEL_ENABLED), OTLP trace export (OTEL_TRACES_EXPORTER=otlp, with tracing enabled), and the
OpenTelemetry metrics and logs APIs with OTLP export (DD_METRICS_OTEL_ENABLED, DD_LOGS_OTEL_ENABLED).
Each case has its own test, so that manifests can declare them per library.
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
_TRACING_API = {"DD_TRACE_OTEL_ENABLED": "true"}
_OTLP_METRICS = {"DD_METRICS_OTEL_ENABLED": "true"}
_OTLP_LOGS = {"DD_LOGS_OTEL_ENABLED": "true"}
_OTLP_TRACES = {"OTEL_TRACES_EXPORTER": "otlp"}


# The OTel semantics RFC makes DD_TRACE_OTEL_SEMANTICS_ENABLED set OTEL_TRACES_EXPORTER=otlp, so with tracing
# enabled, OTEL_ENABLED is true as soon as semantics mode is on. Each signal is tested without semantics mode, where
# it must report false. With tracing disabled, OTLP trace export doesn't count, which shows that the others do.
def _library_env(signal: dict[str, str], *, semantics: bool, tracing: bool = True) -> dict[str, str | None]:
    # Enables at most one OpenTelemetry signal on top of _OTEL_SIGNALS_DISABLED.
    env = {**_OTEL_SIGNALS_DISABLED, **signal, "DD_TRACE_OTEL_SEMANTICS_ENABLED": str(semantics).lower()}
    if not tracing:
        env["DD_TRACE_ENABLED"] = "false"
    return env


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
    @parametrize("library_env", [_library_env({}, semantics=True)])
    def test_otel_enabled_semantics_alone(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=True)

    @parametrize("library_env", [_library_env(_TRACING_API, semantics=False)])
    def test_otel_enabled_tracing_api_without_semantics(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

    @parametrize("library_env", [_library_env(_OTLP_METRICS, semantics=False)])
    def test_otel_enabled_otlp_metrics_without_semantics(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

    @parametrize("library_env", [_library_env(_OTLP_LOGS, semantics=False)])
    def test_otel_enabled_otlp_logs_without_semantics(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

    @parametrize("library_env", [_library_env(_OTLP_TRACES, semantics=False)])
    def test_otel_enabled_otlp_traces_without_semantics(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

    @parametrize("library_env", [_library_env(_TRACING_API, semantics=True, tracing=False)])
    def test_otel_enabled_tracing_api_with_tracing_disabled(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=True)

    @parametrize("library_env", [_library_env(_OTLP_METRICS, semantics=True, tracing=False)])
    def test_otel_enabled_otlp_metrics_with_tracing_disabled(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=True)

    @parametrize("library_env", [_library_env(_OTLP_LOGS, semantics=True, tracing=False)])
    def test_otel_enabled_otlp_logs_with_tracing_disabled(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=True)

    @parametrize("library_env", [_library_env(_OTLP_TRACES, semantics=True, tracing=False)])
    def test_otel_enabled_otlp_traces_with_tracing_disabled(self, test_library: APMLibrary) -> None:
        with test_library:
            _assert_otel_enabled(test_library, expected=False)

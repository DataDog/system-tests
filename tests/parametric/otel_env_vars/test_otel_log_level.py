"""Internal SDK logger configuration, not the severity of exported application logs."""

import time

from utils import features, pytest, scenarios
from tests.parametric.conftest import APMLibrary, APMLibraryFactory, nodejs_startup_config
from tests.parametric.otel_env_vars.utils import has_warning_for_value
from utils.docker_fixtures import TestAgentAPI


VARIABLE = "OTEL_LOG_LEVEL"

DEFAULT_ENVIRONMENT: dict[str, str | None] = {
    VARIABLE: None,
    # The harness enables debug by default, which otherwise masks OTEL_LOG_LEVEL.
    "DD_TRACE_DEBUG": None,
    "DD_TRACE_STARTUP_LOGS": "true",
    "DD_TRACE_LOG_DIRECTORY": "/tmp/otel-log-level",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
}


def _log_level(test_agent: TestAgentAPI, library: APMLibrary) -> str:
    """Adapt effective logger views and emitted diagnostics to a common spelling."""
    if library.lang == "nodejs":
        entries = test_agent.wait_for_telemetry_configurations().get("DD_TRACE_LOG_LEVEL", [])
        # Rejected attempts may precede the effective default in configuration telemetry.
        accepted = [entry for entry in entries if not entry.get("error")]
        assert accepted, "No accepted DD_TRACE_LOG_LEVEL configuration in telemetry"
        value = accepted[0].get("value")
    elif library.lang in ("golang", "dotnet"):
        # The debug-only mapping does not expose a scalar threshold. Require an
        # actual INFO diagnostic as well as the published effective debug flag.
        assert _debug_enabled(library) is False
        if library.lang == "golang":
            value = library.config().get("dd_trace_startup_log_level")
        else:
            with library.dd_start_span("otel-log-level-default"):
                pass
            library.dd_flush()
            deadline = time.monotonic() + 5
            while True:
                logs = _diagnostic_logs(library)
                if any("[INF]" in line and "DATADOG TRACER CONFIGURATION" in line for line in logs.splitlines()):
                    value = "info"
                    break
                assert time.monotonic() < deadline, f"No INFO startup diagnostic from the SDK:\n{logs}"
                time.sleep(0.1)
    else:
        config = library.config()
        # Java's dd_log_level is raw input, so it cannot prove effective defaults or fallback.
        key = "dd_trace_effective_log_level" if library.lang in ("java", "python", "ruby") else "dd_log_level"
        value = config.get(key)
    assert isinstance(value, str), "The parametric application does not expose the effective logger level"
    return value.lower()


def _php_threshold_diagnostics(library: APMLibrary) -> tuple[bool, bool]:
    assert library.dd_log_level_diagnostics(), "The SDK logger diagnostic probe did not complete"
    # Both SDK calls execute synchronously before the endpoint responds.
    logs = library.get_logs().lower()
    return (
        "cannot update the span duration of an unfinished span" in logs,
        "unexpected parameter, expecting double for start time" in logs,
    )


def _fallback_log_level(test_agent: TestAgentAPI, library: APMLibrary) -> str | tuple[bool, bool]:
    if library.lang == "php":
        return _php_threshold_diagnostics(library)
    return _log_level(test_agent, library)


@pytest.fixture
def default_log_level(test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory) -> str | tuple[bool, bool]:
    with test_library_factory(DEFAULT_ENVIRONMENT) as library:
        observed = _fallback_log_level(test_agent, library)
        if isinstance(observed, tuple):
            # A positive baseline artifact prevents a completely disabled logger
            # from passing merely because both processes emit nothing.
            assert observed[0], "The unset SDK logger did not emit the ERROR diagnostic"
        return observed


def _diagnostic_logs(library: APMLibrary) -> str:
    if library.lang == "dotnet":
        success, logs = library.container_exec_run(
            "sh -c 'for file in /tmp/otel-log-level/dotnet-tracer-managed*; "
            'do if [ -e "$file" ]; then cat "$file" || exit 1; fi; done\''
        )
        assert success, "Could not read the .NET diagnostic log files"
        return logs
    return library.get_logs()


def _debug_enabled(library: APMLibrary) -> bool:
    if library.lang == "nodejs":
        value = nodejs_startup_config(library)["debug"]
        assert isinstance(value, bool)
        return value
    config = library.config()
    value = config["dd_trace_debug"]
    assert value in ("true", "false")
    if value == "true":
        level = config.get("dd_log_level")
        assert level is None or level.lower() == "debug"
    return value == "true"


@scenarios.parametric
@features.otel_log_level
class Test_OTEL_LOG_LEVEL:
    # The specification defines the default and enum parsing, but does not enumerate
    # levels. These are the common values supported by the full log-level mappings.
    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**DEFAULT_ENVIRONMENT, VARIABLE: level}, level, id=level)
            for level in ("debug", "info", "warn", "error")
        ],
    )
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == expected

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**DEFAULT_ENVIRONMENT, VARIABLE: value}, value.lower(), id=value)
            for value in ("DEBUG", "DeBuG", "ERROR")
        ],
    )
    def test_case_insensitive_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == expected

    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == "info"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, VARIABLE: ""}], ids=["empty"])
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library_factory: APMLibraryFactory,
        library_env: dict[str, str | None],
        default_log_level: str | tuple[bool, bool],
    ) -> None:
        with test_library_factory(library_env) as library:
            assert _fallback_log_level(test_agent, library) == default_log_level

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, VARIABLE: "warn"}], ids=["warn"])
    def test_warning_threshold_diagnostic(self, test_library: APMLibrary) -> None:
        # Positive control for the warning suppressed by the PHP fallback threshold.
        with test_library as library:
            assert _php_threshold_diagnostics(library) == (True, True)

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, VARIABLE: "not-a-log-level"}, id="unrecognized")],
    )
    def test_invalid_value_is_ignored(
        self,
        test_agent: TestAgentAPI,
        test_library_factory: APMLibraryFactory,
        library_env: dict[str, str | None],
        default_log_level: str | tuple[bool, bool],
    ) -> None:
        with test_library_factory(library_env) as library:
            assert _fallback_log_level(test_agent, library) == default_log_level

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, VARIABLE: "not-a-log-level"}, id="unrecognized")],
    )
    def test_invalid_value_emits_warning(self, test_library: APMLibrary) -> None:
        with test_library as library:
            with library.dd_start_span("otel-log-level-diagnostics"):
                pass
            library.dd_flush()
            # Configuration diagnostics can run asynchronously after the first agent handshake.
            deadline = time.monotonic() + 5
            while True:
                logs = _diagnostic_logs(library)
                if has_warning_for_value(library.lang, logs, "not-a-log-level"):
                    return
                assert time.monotonic() < deadline, f"No warning about the unrecognized {VARIABLE} value:\n{logs}"
                time.sleep(0.1)

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, VARIABLE: "error"}], ids=["error"])
    def test_otel_log_level_env(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Preserve the existing error-level assertion in the variable's feature.
        with test_library as library:
            assert _log_level(test_agent, library) == "error"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, VARIABLE: "debug"}], ids=["debug"])
    def test_otel_log_level_to_debug_mapping(self, test_library: APMLibrary) -> None:
        # Some SDKs implement OTEL_LOG_LEVEL only as a debug-mode switch.
        with test_library as library:
            assert _debug_enabled(library) is True

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, VARIABLE: value}, id=value) for value in ("DEBUG", "DeBuG")],
    )
    def test_case_insensitive_debug_mapping(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _debug_enabled(library) is True

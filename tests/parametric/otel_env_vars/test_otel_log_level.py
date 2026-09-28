"""Internal SDK logger configuration, not the severity of exported application logs."""

from utils import features, pytest, scenarios
from tests.parametric.conftest import APMLibrary, nodejs_startup_config
from utils.docker_fixtures import TestAgentAPI


DEFAULT_ENVIRONMENT: dict[str, str | None] = {
    "OTEL_LOG_LEVEL": None,
    # The harness enables debug by default, which otherwise masks OTEL_LOG_LEVEL.
    "DD_TRACE_DEBUG": None,
    "DD_TRACE_LOG_LEVEL": None,
    "DD_LOG_LEVEL": None,
    "DD_TRACE_STARTUP_LOGS": "true",
    "DD_TRACE_LOG_DIRECTORY": "/tmp/otel-log-level",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
}

# The specification defines the default and enum parsing, but does not enumerate
# levels. These are the common values supported by the full log-level mappings.
STABLE_VALUES = [
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": level}, level, id=level)
    for level in ("debug", "info", "warn", "error")
]

CASE_INSENSITIVE_VALUES = [
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": value}, value.lower(), id=value)
    for value in ("DEBUG", "DeBuG", "ERROR")
]

UNSET_AND_EMPTY = [
    pytest.param(DEFAULT_ENVIRONMENT, id="unset"),
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": ""}, id="empty"),
]


FALLBACK_VALUES = [
    *UNSET_AND_EMPTY,
    pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "not-a-log-level"}, id="unrecognized"),
]


def _log_level(test_agent: TestAgentAPI, library: APMLibrary) -> str:
    """Adapt the published configuration surfaces to a common level spelling."""
    if library.lang == "nodejs":
        entries = test_agent.wait_for_telemetry_configurations().get("DD_TRACE_LOG_LEVEL", [])
        # Rejected attempts may precede the effective default in configuration telemetry.
        accepted = [entry for entry in entries if not entry.get("error")]
        assert accepted, "No accepted DD_TRACE_LOG_LEVEL configuration in telemetry"
        value = accepted[0].get("value")
    else:
        config = library.config()
        value = config.get("dd_trace_effective_log_level") or config.get("dd_log_level")
    assert isinstance(value, str), "The parametric application does not expose the effective logger level"
    return value.lower()


def _diagnostic_logs(library: APMLibrary) -> str:
    if library.lang == "dotnet":
        success, logs = library.container_exec_run("sh -c 'cat /tmp/otel-log-level/dotnet-tracer-managed*'")
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
    @pytest.mark.parametrize(("library_env", "expected"), STABLE_VALUES)
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), CASE_INSENSITIVE_VALUES)
    def test_case_insensitive_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == expected

    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == "info"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": ""}], ids=["empty"])
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == "info"

    @pytest.mark.parametrize("library_env", FALLBACK_VALUES)
    def test_default_debug_threshold(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Node.js keeps a debug threshold but disables debug output by default.
        with test_library as library:
            assert _log_level(test_agent, library) == "debug"
            assert _debug_enabled(library) is False

    @pytest.mark.parametrize("library_env", [pytest.param(DEFAULT_ENVIRONMENT, id="unset")])
    def test_default_error_threshold(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # PHP's documented Datadog logger default is error.
        with test_library as library:
            assert _log_level(test_agent, library) == "error"
            assert _debug_enabled(library) is False

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": ""}, id="empty"),
            pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "not-a-log-level"}, id="unrecognized"),
        ],
    )
    def test_error_threshold_fallback(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == "error"

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY)
    def test_default_does_not_enable_debug(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _debug_enabled(library) is False

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "not-a-log-level"}, id="unrecognized")],
    )
    def test_invalid_value_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _log_level(test_agent, library) == "info"

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "not-a-log-level"}, id="unrecognized")],
    )
    def test_invalid_value_emits_warning(self, test_library: APMLibrary) -> None:
        with test_library as library:
            logs = _diagnostic_logs(library).lower()
        assert any(
            ("otel_log_level" in line or "not-a-log-level" in line)
            and ("warn" in line or "invalid" in line or "unsupported" in line or "not supported" in line)
            for line in logs.splitlines()
        ), "No warning about the unrecognized OTEL_LOG_LEVEL value"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "error"}], ids=["error"])
    def test_otel_log_level_env(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Preserve the existing error-level assertion in the variable's feature.
        with test_library as library:
            assert _log_level(test_agent, library) == "error"

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": "debug"}], ids=["debug"])
    def test_otel_log_level_to_debug_mapping(self, test_library: APMLibrary) -> None:
        # Some SDKs implement OTEL_LOG_LEVEL only as a debug-mode switch.
        with test_library as library:
            assert _debug_enabled(library) is True

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**DEFAULT_ENVIRONMENT, "OTEL_LOG_LEVEL": value}, id=value) for value in ("DEBUG", "DeBuG")],
    )
    def test_case_insensitive_debug_mapping(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _debug_enabled(library) is True

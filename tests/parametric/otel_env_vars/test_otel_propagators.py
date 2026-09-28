from pathlib import Path

from tests.parametric.conftest import APMLibrary
from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI, new_test_id


# https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/
BASE_ENV = {
    "DD_TRACE_PROPAGATION_STYLE": None,
    "DD_TRACE_PROPAGATION_STYLE_INJECT": None,
    "DD_TRACE_PROPAGATION_STYLE_EXTRACT": None,
    "DD_PROPAGATION_STYLE_INJECT": None,
    "DD_PROPAGATION_STYLE_EXTRACT": None,
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_TRACE_LOG_DIRECTORY": "/tmp/otel-propagators",
    "DD_DATA_STREAMS_ENABLED": "false",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
    "OTEL_PROPAGATORS": None,
}

# Keep the stable enum values together; separate methods allow manifests to
# declare partial support without disabling the supported formats.
STABLE_VALUES = {
    value: pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": value}, expected, id=value)
    for value, expected in (
        ("tracecontext", {"tracecontext"}),
        ("baggage", {"baggage"}),
        ("b3", {"b3"}),
        ("b3multi", {"b3multi"}),
        ("xray", {"xray"}),
        ("none", set()),
    )
}

DEPRECATED_VALUES = [
    pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": value}, {value}, id=value) for value in ("jaeger", "ottrace")
]

DEFAULT_VALUE = [pytest.param(BASE_ENV, id="unset")]
EMPTY_VALUE = [pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": ""}, id="empty")]
INVALID_VALUE = [pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": "not-a-propagator"}, id="not-a-propagator")]

PROPAGATOR_HEADERS = {
    "tracecontext": "traceparent",
    "baggage": "baggage",
    "b3": "b3",
    "b3multi": "x-b3-traceid",
    "xray": "x-amzn-trace-id",
    "jaeger": "uber-trace-id",
    "ottrace": "ot-tracer-traceid",
    "datadog": "x-datadog-trace-id",
}


def _configured_propagators(library: APMLibrary) -> set[str]:
    # One child span supplies a minimal public observation of the configured
    # propagators. Supplying baggage also makes baggage-only selection observable.
    headers = library.dd_make_child_span_and_get_headers([("baggage", "otel.propagators=selected")])
    if "baggage" in headers:
        assert headers["baggage"] == "otel.propagators=selected"
    return {name for name, header in PROPAGATOR_HEADERS.items() if header in headers}


def _diagnostic_logs(library: APMLibrary) -> str:
    if library.lang == "dotnet":
        success, logs = library.container_exec_run("sh -c 'cat /tmp/otel-propagators/dotnet-tracer-managed*'")
        assert success, "Could not read the .NET diagnostic log files"
        return logs
    return library.get_logs()


@pytest.fixture
def default_and_configured_propagators(
    request: pytest.FixtureRequest,
    worker_id: str,
    test_agent: TestAgentAPI,
    library_env: dict[str, str],
    library_extra_command_arguments: list[str],
) -> tuple[set[str], set[str]]:
    """Compare with a fresh unset process without baking in a tracer's defaults."""
    scenarios.parametric.parametrized_tests_metadata[request.node.nodeid] = library_env
    observed = []
    for label, environment in (("unset", BASE_ENV), ("configured", library_env)):
        # The factory tears each container down before the next reuses its port.
        with scenarios.parametric.get_apm_library(
            request=request,
            worker_id=worker_id,
            test_id=new_test_id(),
            test_agent=test_agent,
            library_env=environment,
            library_extra_command_arguments=library_extra_command_arguments,
        ) as library:
            with library:
                observed.append(_configured_propagators(library))
            # The factory's server_log.log is reused for a given pytest node;
            # retain each process's diagnostics for failed comparisons.
            log_folder = (
                Path(scenarios.parametric.host_log_folder) / "outputs" / request.cls.__name__ / request.node.name
            )
            (log_folder / f"{label}_server_log.log").write_text(library.get_logs(), encoding="utf-8")
    return observed[0], observed[1]


@scenarios.parametric
@features.otel_propagators
class Test_OTEL_PROPAGATORS:
    @pytest.mark.parametrize(("library_env", "expected"), [STABLE_VALUES["tracecontext"], STABLE_VALUES["b3multi"]])
    def test_trace_propagators(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), [STABLE_VALUES["b3"]])
    def test_b3_single_header(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), [STABLE_VALUES["baggage"]])
    def test_baggage(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), [STABLE_VALUES["xray"]])
    def test_xray(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), [STABLE_VALUES["none"]])
    def test_none(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(("library_env", "expected"), DEPRECATED_VALUES)
    def test_deprecated_values(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": "b3,tracecontext"}, id="b3,tracecontext")],
    )
    def test_multiple_trace_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"b3", "tracecontext"}

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": "tracecontext,baggage"}, id="tracecontext,baggage")],
    )
    def test_composite_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {**BASE_ENV, "OTEL_PROPAGATORS": "tracecontext,b3multi,tracecontext,b3multi"},
                id="tracecontext,b3multi,tracecontext,b3multi",
            )
        ],
    )
    def test_duplicate_propagators(self, test_library: APMLibrary) -> None:
        # Duplicate entries must have the same observable effect as one entry.
        # Header maps do not expose how many internal propagators were registered.
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext", "b3multi"}

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, "OTEL_PROPAGATORS": "TRACEContext,B3MULTI"}, id="TRACEContext,B3MULTI")],
    )
    def test_case_insensitive_values(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext", "b3multi"}

    @pytest.mark.parametrize("library_env", DEFAULT_VALUE)
    def test_default_is_sensible(self, test_library: APMLibrary) -> None:
        with test_library as library:
            propagators = _configured_propagators(library)
        assert "tracecontext" in propagators
        assert propagators <= {"datadog", "tracecontext", "baggage"}

    @pytest.mark.parametrize("library_env", DEFAULT_VALUE)
    def test_default_matches_specification(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(self, default_and_configured_propagators: tuple[set[str], set[str]]) -> None:
        unset, configured = default_and_configured_propagators
        assert "tracecontext" in unset
        assert configured == unset

    @pytest.mark.parametrize("library_env", INVALID_VALUE)
    def test_invalid_is_ignored(self, default_and_configured_propagators: tuple[set[str], set[str]]) -> None:
        unset, configured = default_and_configured_propagators
        assert "tracecontext" in unset
        assert configured == unset

    @pytest.mark.parametrize("library_env", INVALID_VALUE)
    def test_invalid_value_logs_warning(self, test_library: APMLibrary) -> None:
        with test_library as library:
            logs = _diagnostic_logs(library).lower()
        assert any(
            "not-a-propagator" in line
            and any(word in line for word in ("warn", "invalid", "unsupported", "not supported"))
            for line in logs.splitlines()
        ), logs

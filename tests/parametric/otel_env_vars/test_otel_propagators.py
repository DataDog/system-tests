import json
import time

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.utils import has_warning_for_value
from utils import features, pytest, scenarios


VARIABLE = "OTEL_PROPAGATORS"

# https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/
BASE_ENV = {
    # Keep the .NET configuration and warning diagnostics in a known location.
    "DD_TRACE_LOG_DIRECTORY": "/tmp/otel-propagators",
    # Go starts metric and log providers eagerly; disable unrelated exporters.
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
    VARIABLE: None,
}

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
        success, logs = library.container_exec_run(
            "sh -c 'for log in /tmp/otel-propagators/dotnet-tracer-managed*; do "
            '[ -f "$log" ] || continue; cat "$log" || exit 1; done\''
        )
        assert success, f"Could not read the .NET diagnostic log files: {logs}"
        return logs
    return library.get_logs()


def _configured_baggage_propagators(library: APMLibrary) -> set[str]:
    if library.lang != "dotnet":
        return _configured_propagators(library)

    # .NET's manual span-context API discards baggage. Its published startup
    # configuration exposes the resolved propagators in both directions.
    with library.dd_start_span("otel-propagators-configuration"):
        pass
    library.dd_flush()
    deadline = time.monotonic() + 5
    marker = "DATADOG TRACER CONFIGURATION - "
    while True:
        logs = _diagnostic_logs(library)
        for line in logs.splitlines():
            if marker in line:
                # The logger appends metadata after the JSON configuration object.
                configuration, _ = json.JSONDecoder().raw_decode(line.split(marker, 1)[1].lstrip())
                inject = set(configuration["trace_propagation_style_inject"])
                extract = set(configuration["trace_propagation_style_extract"])
                assert inject == extract, f"Injection and extraction differ: {inject=}, {extract=}"
                return inject
        assert time.monotonic() < deadline, f"No published propagation configuration found: {logs}"
        time.sleep(0.1)


@scenarios.parametric
@features.otel_propagators
class Test_OTEL_PROPAGATORS:
    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "tracecontext"}, id="tracecontext")])
    def test_tracecontext(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "b3multi"}, id="b3multi")])
    def test_b3multi(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"b3multi"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "b3"}, id="b3")])
    def test_b3_single_header(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"b3"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "baggage"}, id="baggage")])
    def test_baggage(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_baggage_propagators(library) == {"baggage"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "xray"}, id="xray")])
    def test_xray(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"xray"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "none"}, id="none")])
    def test_none(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == set()

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**BASE_ENV, VARIABLE: "jaeger"}, {"jaeger"}, id="jaeger"),
            pytest.param({**BASE_ENV, VARIABLE: "ottrace"}, {"ottrace"}, id="ottrace"),
        ],
    )
    def test_deprecated_values(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            assert _configured_propagators(library) == expected

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, VARIABLE: "b3,tracecontext"}, id="b3,tracecontext")],
    )
    def test_multiple_trace_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"b3", "tracecontext"}

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, VARIABLE: "tracecontext,baggage"}, id="tracecontext,baggage")],
    )
    def test_composite_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_baggage_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {**BASE_ENV, VARIABLE: "tracecontext,b3multi,tracecontext,b3multi"},
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
        [pytest.param({**BASE_ENV, VARIABLE: "TRACEContext,B3MULTI"}, id="TRACEContext,B3MULTI")],
    )
    def test_case_insensitive_values(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_propagators(library) == {"tracecontext", "b3multi"}

    @pytest.mark.parametrize("library_env", [pytest.param(BASE_ENV, id="unset")])
    def test_default_matches_specification(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_baggage_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: ""}, id="empty")])
    def test_empty_is_treated_as_unset(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_baggage_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize(
        "library_env", [pytest.param({**BASE_ENV, VARIABLE: "not-a-propagator"}, id="not-a-propagator")]
    )
    def test_invalid_is_ignored(self, test_library: APMLibrary) -> None:
        with test_library as library:
            assert _configured_baggage_propagators(library) == {"tracecontext", "baggage"}

    @pytest.mark.parametrize(
        "library_env", [pytest.param({**BASE_ENV, VARIABLE: "not-a-propagator"}, id="not-a-propagator")]
    )
    def test_invalid_value_logs_warning(self, test_library: APMLibrary) -> None:
        with test_library as library:
            # Startup diagnostics can follow an asynchronous agent ping. One
            # flushed span and a bounded wait allow that diagnostic to arrive.
            with library.dd_start_span("otel-propagators-diagnostics"):
                pass
            library.dd_flush()
            deadline = time.monotonic() + 5
            while True:
                logs = _diagnostic_logs(library)
                if has_warning_for_value(library.lang, logs, "not-a-propagator"):
                    return
                assert time.monotonic() < deadline, logs
                time.sleep(0.1)

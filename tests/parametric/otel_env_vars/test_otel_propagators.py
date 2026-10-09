import json
import time

from tests.parametric.conftest import APMLibrary, APMLibraryFactory, nodejs_telemetry_value
from tests.parametric.otel_env_vars.utils import has_warning_for_value
from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI


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


def _assert_configured_propagators(library: APMLibrary, expected: set[str]) -> None:
    configured = _configured_baggage_propagators(library) if "baggage" in expected else _configured_propagators(library)
    assert configured == expected

    # Each carrier supplies the same trace ID through one selected format.
    # Only the low 64 bits matter here; 128-bit propagation has separate coverage.
    carriers = {
        "tracecontext": [("traceparent", "00-000000000000000000000000075bcd15-000000003ade68b1-01")],
        "b3": [("b3", "000000000000000000000000075bcd15-000000003ade68b1-1")],
        "b3multi": [
            ("x-b3-traceid", "000000000000000000000000075bcd15"),
            ("x-b3-spanid", "000000003ade68b1"),
            ("x-b3-sampled", "1"),
        ],
        "xray": [("x-amzn-trace-id", f"Root=1-67891233-{123456789:024x};Parent={987654321:016x};Sampled=1")],
        "jaeger": [("uber-trace-id", "000000000000000000000000075bcd15:000000003ade68b1:0:1")],
        "ottrace": [
            ("ot-tracer-traceid", "00000000075bcd15"),
            ("ot-tracer-spanid", "000000003ade68b1"),
            ("ot-tracer-sampled", "true"),
        ],
    }
    for propagator in sorted(expected & carriers.keys()):
        with library.dd_extract_headers_and_make_child_span(
            "otel-propagators-extraction", carriers[propagator]
        ) as span:
            assert int(span.trace_id) & ((1 << 64) - 1) == 123456789, (
                f"{propagator} did not extract the incoming trace ID"
            )

    if not expected:
        with library.dd_extract_headers_and_make_child_span("otel-propagators-none", carriers["tracecontext"]) as span:
            assert int(span.trace_id) & ((1 << 64) - 1) != 123456789, "none still extracts tracecontext"


def _assert_deduplicated_propagators(library: APMLibrary, test_agent: TestAgentAPI, expected: set[str]) -> None:
    if library.lang == "python":
        # The Python app collapses header writes, and its configuration adapter
        # uses private SDK fields. Only the observable effect is checked here.
        return

    if library.lang in {"java", "dotnet"}:
        # These apps preserve every public carrier setter call in the raw list.
        with library.dd_start_span("otel-propagators-deduplication") as span:
            headers = library.dd_inject_headers(span.span_id)
        for propagator in expected:
            header = PROPAGATOR_HEADERS[propagator]
            assert sum(name.lower() == header for name, _ in headers) == 1, headers
        return

    if library.lang == "nodejs":
        # The published extraction list directly drives the B3 extraction loop;
        # injection uses membership checks and cannot reveal repeated entries.
        styles = nodejs_telemetry_value(test_agent, "dd_trace_propagation_style_extract")
    else:
        # Go exposes registered injectors, PHP a resolved set, and Ruby/Rust the
        # public lists used to construct their propagators. Preserve duplicates.
        styles = library.config()["dd_trace_propagation_style"]
    assert isinstance(styles, str), styles
    resolved = styles.split(",")
    if library.lang == "golang":
        # Go names its B3 multi-header propagator "b3"; OTel calls it "b3multi".
        resolved = ["b3multi" if style == "b3" else style for style in resolved]
    assert sorted(resolved) == sorted(expected), resolved


@scenarios.parametric
@features.otel_propagators
class Test_OTEL_PROPAGATORS:
    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "tracecontext"}, id="tracecontext")])
    def test_tracecontext(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"tracecontext"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "b3multi"}, id="b3multi")])
    def test_b3multi(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"b3multi"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "b3"}, id="b3")])
    def test_b3_single_header(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"b3"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "baggage"}, id="baggage")])
    def test_baggage(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"baggage"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "xray"}, id="xray")])
    def test_xray(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"xray"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: "none"}, id="none")])
    def test_none(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, set())

    @pytest.mark.parametrize(
        ("library_env", "expected"),
        [
            pytest.param({**BASE_ENV, VARIABLE: "jaeger"}, {"jaeger"}, id="jaeger"),
            pytest.param({**BASE_ENV, VARIABLE: "ottrace"}, {"ottrace"}, id="ottrace"),
        ],
    )
    def test_deprecated_values(self, test_library: APMLibrary, expected: set[str]) -> None:
        with test_library as library:
            _assert_configured_propagators(library, expected)

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, VARIABLE: "b3,tracecontext"}, id="b3,tracecontext")],
    )
    def test_multiple_trace_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"b3", "tracecontext"})

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, VARIABLE: "tracecontext,baggage"}, id="tracecontext,baggage")],
    )
    def test_composite_propagators(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"tracecontext", "baggage"})

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {**BASE_ENV, VARIABLE: "tracecontext,b3multi,tracecontext,b3multi"},
                id="tracecontext,b3multi,tracecontext,b3multi",
            )
        ],
    )
    def test_duplicate_propagators(self, test_library: APMLibrary, test_agent: TestAgentAPI) -> None:
        expected = {"tracecontext", "b3multi"}
        with test_library as library:
            _assert_configured_propagators(library, expected)
            _assert_deduplicated_propagators(library, test_agent, expected)

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**BASE_ENV, VARIABLE: "TRACEContext,B3MULTI"}, id="TRACEContext,B3MULTI")],
    )
    def test_case_insensitive_values(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"tracecontext", "b3multi"})

    @pytest.mark.parametrize("library_env", [pytest.param(BASE_ENV, id="unset")])
    def test_default_matches_specification(self, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_configured_propagators(library, {"tracecontext", "baggage"})

    @pytest.mark.parametrize("library_env", [pytest.param({**BASE_ENV, VARIABLE: ""}, id="empty")])
    def test_empty_is_treated_as_unset(
        self, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory(BASE_ENV) as library:
            default = _configured_baggage_propagators(library)
        with test_library_factory(library_env) as library:
            assert _configured_baggage_propagators(library) == default

    @pytest.mark.parametrize(
        "library_env", [pytest.param({**BASE_ENV, VARIABLE: "not-a-propagator"}, id="not-a-propagator")]
    )
    def test_invalid_is_ignored(
        self, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory(BASE_ENV) as library:
            default = _configured_baggage_propagators(library)
        with test_library_factory(library_env) as library:
            assert _configured_baggage_propagators(library) == default

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

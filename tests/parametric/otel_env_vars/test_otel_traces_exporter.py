import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


SPAN_NAME = "otel-traces-exporter-span"
OTLP_TRACE_PATH = "/v1/traces"
ZIPKIN_TRACE_PATH = "/api/v2/spans"

OTLP_EXPORTER = "otlp"
ZIPKIN_EXPORTER = "zipkin"
CONSOLE_EXPORTER = "console"
NONE_EXPORTER = "none"
LOGGING_EXPORTER = "logging"
OTLP_STDOUT_EXPORTER = "otlp/stdout"

BASE_ENV = {
    "DD_TRACE_AGENT_PROTOCOL_VERSION": None,
    "DD_TRACE_DEBUG": "false",
    "DD_TRACE_ENABLED": None,
    "DD_TRACE_OTEL_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
}

STABLE_VALUES = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": OTLP_EXPORTER},
        OTLP_EXPORTER,
        id=OTLP_EXPORTER,
    ),
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": ZIPKIN_EXPORTER},
        ZIPKIN_EXPORTER,
        id=ZIPKIN_EXPORTER,
    ),
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": CONSOLE_EXPORTER},
        CONSOLE_EXPORTER,
        id=CONSOLE_EXPORTER,
    ),
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": NONE_EXPORTER},
        NONE_EXPORTER,
        id=NONE_EXPORTER,
    ),
]

DEPRECATED_VALUES = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": LOGGING_EXPORTER},
        id=LOGGING_EXPORTER,
    ),
]

DEVELOPMENT_VALUES = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": OTLP_STDOUT_EXPORTER},
        id=OTLP_STDOUT_EXPORTER,
    ),
]

UNSET_VALUE = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": None},
        id="unset",
    ),
]

EMPTY_VALUE = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": ""},
        id="empty",
    ),
]

INVALID_VALUE = [
    pytest.param(
        {**BASE_ENV, "OTEL_TRACES_EXPORTER": "invalid"},
        id="invalid",
    ),
]


@pytest.fixture(autouse=True)
def _exporter_endpoints(
    library_env: dict[str, str],
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
) -> None:
    library_env["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = (
        f"http://{test_agent.container_name}:{test_agent_otlp_http_port}{OTLP_TRACE_PATH}"
    )
    library_env["OTEL_EXPORTER_ZIPKIN_ENDPOINT"] = (
        f"http://{test_agent.container_name}:{test_agent.container_port}{ZIPKIN_TRACE_PATH}"
    )


def _emit_span(library: APMLibrary) -> str:
    with library.dd_start_span(name=SPAN_NAME):
        pass
    library.dd_flush()
    return library.get_logs()


def _assert_no_native_trace(test_agent: TestAgentAPI) -> None:
    with pytest.raises(ValueError):
        test_agent.wait_for_num_traces(num=1)


def _assert_otlp_export(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    with test_library as library:
        _emit_span(library)

    requests = test_agent.otlp_requests()
    assert any(request["url"].endswith(OTLP_TRACE_PATH) for request in requests)
    _assert_no_native_trace(test_agent)


def _assert_zipkin_export(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    with test_library as library:
        _emit_span(library)

    requests = test_agent.requests()
    assert any(request["url"].endswith(ZIPKIN_TRACE_PATH) for request in requests)
    _assert_no_native_trace(test_agent)


def _assert_stdout_export(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    with test_library as library:
        logs = _emit_span(library)

    assert SPAN_NAME in logs
    assert not any(request["url"].endswith(OTLP_TRACE_PATH) for request in test_agent.otlp_requests())
    _assert_no_native_trace(test_agent)


def _assert_no_export(test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    with test_library as library:
        if library.lang == "nodejs":
            _emit_span(library)
            _assert_no_native_trace(test_agent)
            return

        config = library.config()

    assert config["dd_trace_enabled"] == "false"


def _assert_exporter(exporter: str, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
    if exporter == OTLP_EXPORTER:
        _assert_otlp_export(test_agent, test_library)
        return

    if exporter == ZIPKIN_EXPORTER:
        _assert_zipkin_export(test_agent, test_library)
        return

    if exporter == CONSOLE_EXPORTER:
        _assert_stdout_export(test_agent, test_library)
        return

    if exporter == NONE_EXPORTER:
        _assert_no_export(test_agent, test_library)
        return

    raise AssertionError(f"Unknown exporter: {exporter}")


@scenarios.parametric
@features.otel_traces_exporter
class Test_OTEL_TRACES_EXPORTER:
    @pytest.mark.parametrize(("library_env", "exporter"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        exporter: str,
    ) -> None:
        _assert_exporter(exporter, test_agent, test_library)

    @pytest.mark.parametrize("library_env", DEPRECATED_VALUES)
    def test_deprecated_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_stdout_export(test_agent, test_library)

    @pytest.mark.parametrize("library_env", DEVELOPMENT_VALUES)
    def test_development_values(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_stdout_export(test_agent, test_library)

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp_export(test_agent, test_library)

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp_export(test_agent, test_library)

    @pytest.mark.parametrize("library_env", INVALID_VALUE)
    def test_invalid_is_ignored(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        _assert_otlp_export(test_agent, test_library)

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    **BASE_ENV,
                    "DD_TRACE_ENABLED": "true",
                    "OTEL_TRACES_EXPORTER": NONE_EXPORTER,
                },
                id="datadog-over-otel",
            )
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            _emit_span(library)

        assert test_agent.wait_for_num_traces(num=1)

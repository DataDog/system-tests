from utils import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.conftest import APMLibraryFactory
from tests.parametric.otel_env_vars.utils import generate_default_counter_data_point
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


COUNTER = "otel_sdk_disabled_probe"
LOGGER = "otel_sdk_disabled_probe"
LOG_MESSAGE = "Test log for OTEL_SDK_DISABLED"
SPAN_NAME = "otel-sdk-disabled-span"


@pytest.fixture
def otlp_endpoints(
    library_env: dict[str, str | None], test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> None:
    # A reachable collector keeps an ignored OTEL_SDK_DISABLED from passing as a failed export.
    collector = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
    for signal in ("traces", "metrics", "logs"):
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT"] = f"{collector}/v1/{signal}"


def _emit_log(library: APMLibrary) -> None:
    assert library.create_logger(LOGGER, LogLevel.INFO)
    assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
    # A disabled SDK may have no logger provider to flush.
    library.otel_logs_flush()


def _emit_span(library: APMLibrary) -> None:
    with library.dd_start_span(name=SPAN_NAME):
        pass
    library.dd_flush()


def _emit_otel_span(library: APMLibrary) -> None:
    with library.otel_start_span(SPAN_NAME):
        pass
    library.otel_flush(1)


def _otlp_trace_urls(test_agent: TestAgentAPI) -> list[str]:
    return [request["url"] for request in test_agent.otlp_requests() if request["url"].endswith("/v1/traces")]


def _assert_tracing_kept(
    test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
) -> None:
    # Control: OTEL_SDK_DISABLED=true disables tracing, so tracing below is kept by the tested
    # value rather than by a library that ignores the variable.
    with test_library_factory({**library_env, "OTEL_SDK_DISABLED": "true"}) as library:
        _emit_span(library)
    with pytest.raises(ValueError):
        test_agent.wait_for_num_traces(num=1)

    with test_library_factory(library_env) as library:
        _emit_span(library)
    assert test_agent.wait_for_num_traces(num=1)


UNSET_AND_EMPTY_VALUES = [
    pytest.param({}, id="unset"),
    pytest.param({"OTEL_SDK_DISABLED": ""}, id="empty"),
]


@scenarios.parametric
@features.otel_sdk_disabled
class Test_OTEL_SDK_DISABLED:
    # OTEL_SDK_DISABLED=true maps to DD_TRACE_ENABLED=false.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_ENABLED": None,
            }
        ],
    )
    def test_true_disables_tracing(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_span(library)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_ENABLED": "true",
            }
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: OTEL_SDK_DISABLED=true alone maps to DD_TRACE_ENABLED=false and disables
        # tracing, so DD_TRACE_ENABLED=true below overrides it rather than leaving tracing
        # that was never disabled.
        with test_library_factory({**library_env, "DD_TRACE_ENABLED": None}) as library:
            _emit_span(library)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)

        with test_library_factory(library_env) as library:
            _emit_span(library)
        assert test_agent.wait_for_num_traces(num=1)

    @pytest.mark.parametrize("library_env", [{"OTEL_SDK_DISABLED": "false"}])
    def test_stable_false(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        _assert_tracing_kept(test_agent, test_library_factory, library_env)

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_default_matches_specification(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        _assert_tracing_kept(test_agent, test_library_factory, library_env)

    # Each OpenTelemetry signal is opted in through its own setting, as an operator auto-install
    # would do. A control run without OTEL_SDK_DISABLED first proves that the signal is sent, so a
    # missing feature cannot pass as disabled. OTEL_SDK_DISABLED=true must then keep it off.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otel_metrics(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            generate_default_counter_data_point(library, COUNTER)
        test_agent.wait_for_num_otlp_metrics(num=1)

        with test_library_factory(library_env) as library:
            generate_default_counter_data_point(library, COUNTER)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otel_logs(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_log(library)
        test_agent.wait_for_num_log_payloads(1)

        with test_library_factory(library_env) as library:
            _emit_log(library)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_log_payloads(1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
            }
        ],
    )
    def test_true_disables_otel_traces(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        # Control: DD_TRACE_OTEL_ENABLED=true alone captures spans created through the OpenTelemetry API.
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_otel_span(library)
        assert test_agent.wait_for_num_traces(num=1)

        with test_library_factory(library_env) as library:
            _emit_otel_span(library)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_overrides_otel_traces_exporter(
        self, test_agent: TestAgentAPI, test_library_factory: APMLibraryFactory, library_env: dict[str, str | None]
    ) -> None:
        with test_library_factory({**library_env, "OTEL_SDK_DISABLED": None}) as library:
            _emit_span(library)
        assert _otlp_trace_urls(test_agent), "The control run did not export OTLP traces"

        with test_library_factory(library_env) as library:
            _emit_span(library)
        assert not _otlp_trace_urls(test_agent)

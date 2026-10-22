from utils import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
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


def _otel_sdk_disabled(test_agent: TestAgentAPI, library: APMLibrary) -> bool:
    if library.lang == "nodejs":
        value = nodejs_telemetry_value(test_agent, "otel_sdk_disabled")
        assert isinstance(value, bool)
        return value

    otel_enabled = library.config()["dd_trace_otel_enabled"]

    assert otel_enabled in ("true", "false")
    return otel_enabled == "false"


UNSET_AND_EMPTY_VALUES = [
    pytest.param(
        {
            "DD_TRACE_OTEL_ENABLED": None,
        },
        id="unset",
    ),
    pytest.param(
        {
            "OTEL_SDK_DISABLED": "",
            "DD_TRACE_OTEL_ENABLED": None,
        },
        id="empty",
    ),
]


@scenarios.parametric
@features.otel_sdk_disabled
class Test_OTEL_SDK_DISABLED:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": None,
            }
        ],
    )
    def test_stable_true(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is True

    # Each signal is opted in through its own setting, as an operator auto-install would do.
    # OTEL_SDK_DISABLED=true must still keep its OTLP export off.
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": None,
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otlp_metrics_export(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            generate_default_counter_data_point(library, COUNTER)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": None,
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otlp_logs_export(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert library.create_logger(LOGGER, LogLevel.INFO)
            assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
            # A disabled SDK may have no logger provider to flush.
            library.otel_logs_flush()

        with pytest.raises(ValueError):
            test_agent.wait_for_num_log_payloads(1)

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": None,
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL": "http/protobuf",
            }
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_true_disables_otlp_traces_export(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            with library.dd_start_span(name=SPAN_NAME):
                pass
            assert library.dd_flush()

        urls = [request["url"] for request in test_agent.otlp_requests()]
        assert not any(url.endswith("/v1/traces") for url in urls), urls

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "false",
                "DD_TRACE_OTEL_ENABLED": None,
            }
        ],
    )
    def test_stable_false(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is False

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_default_matches_specification(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is False

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SDK_DISABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
            }
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ):
        with test_library as library:
            assert _otel_sdk_disabled(test_agent, library) is False
            config = library.config()

        assert config["dd_trace_otel_enabled"] == "true"

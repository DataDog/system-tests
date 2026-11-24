"""DD_SDK_MODE selects how a Datadog SDK runs: "datadog" (the default) or "otel".

DD_SDK_MODE=otel replaces the settings that enable OpenTelemetry mode: it makes "otlp" the default of
OTEL_TRACES_EXPORTER, and true the default of DD_TRACE_OTEL_ENABLED, DD_TRACE_OTEL_SEMANTICS_ENABLED,
DD_METRICS_OTEL_ENABLED and DD_LOGS_OTEL_ENABLED. These settings still win when they're set explicitly.
"""

import time
from typing import Any, Final

from utils import features, pytest, scenarios

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.utils import generate_default_counter_data_point, wait_for_otlp_export_requests
from tests.parametric.utils import find_log_record
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


COUNTER: Final = "dd_sdk_mode_probe"
LOGGER: Final = "dd_sdk_mode_probe"
LOG_MESSAGE: Final = "Test log for DD_SDK_MODE"
SPAN_NAME: Final = "dd-sdk-mode-span"

# The test client enables the OpenTelemetry tracing API by default. Unset it, and the other settings that
# DD_SDK_MODE replaces, so that the mode alone decides their values.
MODE_SETTINGS_UNSET: Final[dict[str, str | None]] = {
    "DD_TRACE_OTEL_ENABLED": None,
    "DD_TRACE_OTEL_SEMANTICS_ENABLED": None,
    "DD_METRICS_OTEL_ENABLED": None,
    "DD_LOGS_OTEL_ENABLED": None,
    "OTEL_TRACES_EXPORTER": None,
}
OTEL_MODE_ENV: Final[dict[str, str | None]] = {**MODE_SETTINGS_UNSET, "DD_SDK_MODE": "otel"}


@pytest.fixture
def otlp_endpoints(
    library_env: dict[str, str | None], test_agent: TestAgentAPI, test_agent_otlp_http_port: int
) -> None:
    # A reachable collector keeps an ignored DD_SDK_MODE from passing as a failed export.
    collector = f"http://{test_agent.container_name}:{test_agent_otlp_http_port}"
    library_env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
    for signal in ("traces", "metrics", "logs"):
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT"] = f"{collector}/v1/{signal}"


def _emit_span(library: APMLibrary) -> None:
    with library.dd_start_span(name=SPAN_NAME):
        pass
    library.dd_flush()


def _emit_otel_span(library: APMLibrary) -> None:
    with library.otel_start_span(SPAN_NAME):
        pass
    library.otel_flush(1)


def _emit_log(library: APMLibrary) -> None:
    assert library.create_logger(LOGGER, LogLevel.INFO)
    assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
    library.otel_logs_flush()


def _has_metric(metric_payloads: list[dict[str, Any]], name: str) -> bool:
    return any(
        metric["name"] == name
        for payload in metric_payloads
        for resource_metrics in payload.get("resource_metrics", [])
        for scope_metrics in resource_metrics.get("scope_metrics", [])
        for metric in scope_metrics.get("metrics", [])
    )


def _wait_for_metric(test_agent: TestAgentAPI, name: str, timeout: float = 8) -> bool:
    # Other metrics can be exported first, so wait for this one rather than for any payload
    deadline = time.monotonic() + timeout
    while not _has_metric(test_agent.metrics(), name):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


def _wait_for_log_record(test_agent: TestAgentAPI, logger_name: str, message: str, timeout: float = 8) -> bool:
    # Other log records can be exported first, so wait for this one rather than for any payload
    deadline = time.monotonic() + timeout
    while find_log_record(test_agent.logs(), logger_name, message) is None:
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


@scenarios.parametric
@features.not_reported  # TODO: use the DD_SDK_MODE feature once it exists in the Feature Parity Dashboard
class Test_DD_SDK_MODE:
    @pytest.mark.parametrize("library_env", [OTEL_MODE_ENV])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_exports_traces_over_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_span(library)

        assert wait_for_otlp_export_requests(test_agent, "traces"), "DD_SDK_MODE=otel didn't export traces over OTLP"

    @pytest.mark.parametrize("library_env", [OTEL_MODE_ENV])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_tracing_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Without the OpenTelemetry tracing API, spans created with it are dropped, and nothing is exported
        with test_library as library:
            _emit_otel_span(library)

        assert wait_for_otlp_export_requests(test_agent, "traces"), (
            "DD_SDK_MODE=otel didn't capture OpenTelemetry spans"
        )

    @pytest.mark.parametrize("library_env", [OTEL_MODE_ENV])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_metrics_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Some SDKs also export runtime metrics in OpenTelemetry mode: look for the counter created with the API
        with test_library as library:
            generate_default_counter_data_point(library, COUNTER)

        assert _wait_for_metric(test_agent, COUNTER), (
            f"DD_SDK_MODE=otel didn't export the {COUNTER} counter created with the OpenTelemetry metrics API"
        )

    @pytest.mark.parametrize("library_env", [OTEL_MODE_ENV])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_logs_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Some SDKs also export the application's own logs in OpenTelemetry mode: look for the record written with the API
        with test_library as library:
            _emit_log(library)

        assert _wait_for_log_record(test_agent, LOGGER, LOG_MESSAGE), (
            "DD_SDK_MODE=otel didn't export the log record written with the OpenTelemetry logs API"
        )

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param({**MODE_SETTINGS_UNSET}, id="unset"),
            pytest.param({**MODE_SETTINGS_UNSET, "DD_SDK_MODE": "datadog"}, id="datadog"),
            pytest.param({**MODE_SETTINGS_UNSET, "DD_SDK_MODE": "DATADOG"}, id="datadog-uppercase"),
            pytest.param({**MODE_SETTINGS_UNSET, "DD_SDK_MODE": "invalid"}, id="invalid"),
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_datadog_mode_keeps_datadog_protocol(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_span(library)

        assert test_agent.wait_for_num_traces(num=1)
        assert not wait_for_otlp_export_requests(test_agent, "traces", timeout=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_METRICS_OTEL_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_metrics_setting_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        with test_library as library:
            generate_default_counter_data_point(library, COUNTER)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_LOGS_OTEL_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_logs_setting_takes_precedence(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert library.create_logger(LOGGER, LogLevel.INFO)
            assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_log_payloads(1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "OTEL_TRACES_EXPORTER": "none"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_traces_exporter_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        # OTEL_TRACES_EXPORTER=none disables trace export, so neither protocol sends the span
        with test_library as library:
            _emit_span(library)

        assert not wait_for_otlp_export_requests(test_agent, "traces", timeout=1)
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_TRACE_AGENT_PROTOCOL_VERSION": "0.4"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_mode_takes_precedence_over_agent_protocol_version(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        with test_library as library:
            _emit_span(library)

        assert wait_for_otlp_export_requests(test_agent, "traces"), (
            "DD_TRACE_AGENT_PROTOCOL_VERSION turned off the OTLP export that DD_SDK_MODE=otel enables"
        )

"""DD_SDK_MODE selects how a Datadog SDK runs: "datadog" (the default) or "otel".

DD_SDK_MODE=otel replaces the settings that enable OpenTelemetry mode: it makes "otlp" the default of
OTEL_TRACES_EXPORTER, and true the default of DD_TRACE_OTEL_ENABLED, DD_TRACE_OTEL_SEMANTICS_ENABLED,
DD_METRICS_OTEL_ENABLED and DD_LOGS_OTEL_ENABLED. These settings still win when they're set explicitly, and
OTEL_SDK_DISABLED=true still turns off OpenTelemetry mode.
"""

import base64
import json
from typing import Any, Final

from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from utils import features, pytest, scenarios

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.utils import (
    find_metric_by_name,
    generate_default_counter_data_point,
    wait_for_otlp_export_requests,
)
from tests.parametric.utils import find_log_record
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


COUNTER: Final = "dd_sdk_mode_probe"
LOGGER: Final = "dd_sdk_mode_probe"
LOG_MESSAGE: Final = "Test log for DD_SDK_MODE"
SPAN_NAME: Final = "dd-sdk-mode-span"
# Set on each span to the API that created it: "datadog" or "otel"
API_ATTRIBUTE: Final = "dd_sdk_mode.api"
# The resource attribute where the SDK records the semantics it applied to exported traces: "otel" or "datadog"
SEMANTICS_ATTRIBUTE: Final = "datadog.sdk.semantics"

# The test client sets DD_TRACE_OTEL_ENABLED=true by default. Unset it, and the other settings that DD_SDK_MODE
# replaces, so that the mode decides their values. Some test apps still enable the OpenTelemetry tracing API themselves.
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
    with library.dd_start_span(name=SPAN_NAME, tags=[(API_ATTRIBUTE, "datadog")]):
        pass
    library.dd_flush()


def _emit_otel_span(library: APMLibrary) -> None:
    with library.otel_start_span(SPAN_NAME, attributes={API_ATTRIBUTE: "otel"}):
        pass
    library.otel_flush(1)


def _emit_log(library: APMLibrary) -> None:
    assert library.create_logger(LOGGER, LogLevel.INFO)
    assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
    # A disabled SDK may have no logger provider to flush
    library.otel_logs_flush()


def _otlp_resource_spans(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    """The resource spans exported over OTLP, waiting for the first export."""
    requests = wait_for_otlp_export_requests(test_agent, "traces")
    assert requests, "DD_SDK_MODE=otel didn't export traces over OTLP"
    resource_spans: list[dict[str, Any]] = []
    for request in requests:
        body = base64.b64decode(request["body"])
        headers = {name.lower(): value for name, value in request["headers"].items()}
        if "json" in headers.get("content-type", ""):
            payload = json.loads(body)
        else:
            payload = MessageToDict(ExportTraceServiceRequest.FromString(body))
        resource_spans.extend(payload.get("resourceSpans", []))
    return resource_spans


def _string_attributes(item: dict[str, Any]) -> dict[str, str | None]:
    """The string attributes of an OTLP resource or span."""
    return {attribute["key"]: attribute["value"].get("stringValue") for attribute in item.get("attributes", [])}


def _exported_semantics(test_agent: TestAgentAPI) -> set[str | None]:
    """The semantics the SDK applied to the traces it exported over OTLP."""
    return {
        _string_attributes(resource_spans.get("resource", {})).get(SEMANTICS_ATTRIBUTE)
        for resource_spans in _otlp_resource_spans(test_agent)
    }


def _exported_span_apis(test_agent: TestAgentAPI) -> set[str | None]:
    """The API that created each span exported over OTLP."""
    return {
        _string_attributes(span).get(API_ATTRIBUTE)
        for resource_spans in _otlp_resource_spans(test_agent)
        for scope_spans in resource_spans.get("scopeSpans", [])
        for span in scope_spans.get("spans", [])
    }


def _telemetry_configurations(test_agent: TestAgentAPI) -> dict[str, list[dict[str, Any]]]:
    """The configurations reported in telemetry, each with the last reported entry first."""
    runtime_id = test_agent.wait_for_telemetry_runtime_id()
    return test_agent.wait_for_telemetry_configurations(runtime_id=runtime_id)


def _assert_reported(configurations: dict[str, list[dict[str, Any]]], name: str, value: str, origin: str) -> None:
    entries = configurations.get(name)
    assert entries, f"{name} isn't in the configuration telemetry"
    effective = entries[0]
    assert str(effective.get("value")).lower() == value, f"{name}: expected {value!r}, got {effective}"
    assert effective.get("origin") == origin, f"{name}: expected the {origin} origin, got {effective}"


def _assert_sdk_mode_supported(test_agent: TestAgentAPI) -> None:
    """Fail unless the SDK supports DD_SDK_MODE, which it then reports in its configuration telemetry.

    Tests that only check that the mode changes nothing would otherwise pass with an SDK that ignores DD_SDK_MODE.
    """
    configurations = _telemetry_configurations(test_agent)
    assert test_agent.get_telemetry_config_by_origin(configurations, "DD_SDK_MODE", "env_var") is not None, (
        "DD_SDK_MODE isn't in the configuration telemetry: the SDK doesn't support it"
    )


@scenarios.parametric
@features.not_reported  # TODO: use the DD_SDK_MODE feature once it exists in the Feature Parity Dashboard
class Test_DD_SDK_MODE:
    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param({**OTEL_MODE_ENV}, id="otel"),
            pytest.param({**OTEL_MODE_ENV, "DD_SDK_MODE": "OTEL"}, id="otel-uppercase"),
            pytest.param({**OTEL_MODE_ENV, "DD_SDK_MODE": " otel "}, id="otel-whitespace"),
        ],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_exports_traces_over_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_span(library)

        assert wait_for_otlp_export_requests(test_agent, "traces"), "DD_SDK_MODE=otel didn't export traces over OTLP"

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_tracing_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # Without DD_TRACE_OTEL_ENABLED, spans created with the OpenTelemetry tracing API are dropped, unless the
        # test app enables that API itself (see the manifests)
        with test_library as library:
            _emit_otel_span(library)

        assert wait_for_otlp_export_requests(test_agent, "traces"), (
            "DD_SDK_MODE=otel didn't capture OpenTelemetry spans"
        )

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_semantics(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_span(library)

        assert _exported_semantics(test_agent) == {"otel"}, "DD_SDK_MODE=otel didn't apply OpenTelemetry semantics"

    @pytest.mark.parametrize(
        "library_env",
        # Keep runtime metrics out, and leave the exports to the explicit flushes, as other OTel metrics tests do
        [{**OTEL_MODE_ENV, "DD_RUNTIME_METRICS_ENABLED": "false", "OTEL_METRIC_EXPORT_INTERVAL": "60000"}],
    )
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_metrics_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            generate_default_counter_data_point(library, COUNTER)

        metrics = test_agent.wait_for_num_otlp_metrics(num=1)
        find_metric_by_name(metrics[0]["resource_metrics"][0]["scope_metrics"][0], COUNTER)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_enables_otel_logs_api(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _emit_log(library)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, LOGGER, LOG_MESSAGE) is not None

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV}])
    def test_otel_mode_defaults_are_reported_as_calculated(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        with test_library:
            configurations = _telemetry_configurations(test_agent)

        _assert_reported(configurations, "OTEL_TRACES_EXPORTER", "otlp", "calculated")
        _assert_reported(configurations, "DD_TRACE_OTEL_ENABLED", "true", "calculated")
        _assert_reported(configurations, "DD_TRACE_OTEL_SEMANTICS_ENABLED", "true", "calculated")
        _assert_reported(configurations, "DD_METRICS_OTEL_ENABLED", "true", "calculated")
        _assert_reported(configurations, "DD_LOGS_OTEL_ENABLED", "true", "calculated")

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param({**MODE_SETTINGS_UNSET}, id="unset"),
            pytest.param({**MODE_SETTINGS_UNSET, "DD_SDK_MODE": ""}, id="empty"),
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

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_TRACE_OTEL_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_tracing_api_setting_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        # The Datadog span comes last, so an OpenTelemetry span would be exported with it or before it
        with test_library as library:
            _emit_otel_span(library)
            _emit_span(library)

        apis = _exported_span_apis(test_agent)
        # Control: the mode still exports Datadog spans over OTLP, so it isn't ignored
        assert "datadog" in apis, "DD_SDK_MODE=otel didn't export the Datadog span over OTLP"
        assert "otel" not in apis, "DD_TRACE_OTEL_ENABLED=false didn't turn off the OpenTelemetry tracing API"

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_TRACE_OTEL_SEMANTICS_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_semantics_setting_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        with test_library as library:
            _emit_span(library)

        # The mode still exports traces over OTLP, so it isn't ignored, but with Datadog semantics
        assert _exported_semantics(test_agent) == {"datadog"}, (
            "DD_TRACE_OTEL_SEMANTICS_ENABLED=false didn't turn off OpenTelemetry semantics"
        )

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_METRICS_OTEL_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_metrics_setting_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        with test_library as library:
            generate_default_counter_data_point(library, COUNTER)
            _emit_span(library)

        # Control: the mode still exports traces over OTLP, so it isn't ignored
        assert wait_for_otlp_export_requests(test_agent, "traces"), "DD_SDK_MODE=otel didn't export traces over OTLP"
        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "DD_LOGS_OTEL_ENABLED": "false"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_explicit_logs_setting_takes_precedence(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            assert library.create_logger(LOGGER, LogLevel.INFO)
            assert library.write_log(LOGGER, LogLevel.INFO, LOG_MESSAGE)
            _emit_span(library)

        # Control: the mode still exports traces over OTLP, so it isn't ignored
        assert wait_for_otlp_export_requests(test_agent, "traces"), "DD_SDK_MODE=otel didn't export traces over OTLP"
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
            _emit_log(library)

        # Control: the mode still exports OpenTelemetry logs, so it isn't ignored
        assert find_log_record(test_agent.wait_for_num_log_payloads(1), LOGGER, LOG_MESSAGE) is not None
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)
        assert not wait_for_otlp_export_requests(test_agent, "traces", timeout=1)

    # OTEL_SDK_DISABLED=true turns off OpenTelemetry mode for every signal, and maps to DD_TRACE_ENABLED=false.
    # DD_SDK_MODE=otel doesn't turn them back on. An SDK that ignores DD_SDK_MODE would pass these tests, so they first
    # check that the SDK supports it.
    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "OTEL_SDK_DISABLED": "true", "DD_TRACE_ENABLED": None}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_sdk_disabled_disables_tracing(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_sdk_mode_supported(test_agent)
            _emit_span(library)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)
        assert not wait_for_otlp_export_requests(test_agent, "traces", timeout=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "OTEL_SDK_DISABLED": "true"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_sdk_disabled_disables_otel_metrics(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_sdk_mode_supported(test_agent)
            generate_default_counter_data_point(library, COUNTER)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_otlp_metrics(num=1)

    @pytest.mark.parametrize("library_env", [{**OTEL_MODE_ENV, "OTEL_SDK_DISABLED": "true"}])
    @pytest.mark.usefixtures("otlp_endpoints")
    def test_otel_sdk_disabled_disables_otel_logs(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library as library:
            _assert_sdk_mode_supported(test_agent)
            _emit_log(library)

        with pytest.raises(ValueError):
            test_agent.wait_for_num_log_payloads(1)

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

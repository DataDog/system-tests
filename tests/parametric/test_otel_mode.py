"""Data created through the OpenTelemetry APIs is exported over OTLP when the tracer works in OpenTelemetry mode.

OpenTelemetry mode turns on semantics mode and every OpenTelemetry signal. Per the OTel semantics RFC,
DD_TRACE_OTEL_SEMANTICS_ENABLED sets OTEL_TRACES_EXPORTER=otlp, so it is left unset here.
"""

import base64
from collections.abc import Callable
import json
import time

from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from utils import pytest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel

from .conftest import APMLibrary
from .utils import find_log_record, generate_default_counter_data_point

pytestmark = pytest.mark.parametrize(
    "library_env",
    [
        {
            "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
            "DD_TRACE_OTEL_ENABLED": "true",
            "DD_METRICS_OTEL_ENABLED": "true",
            "DD_LOGS_OTEL_ENABLED": "true",
            # Only the metric created by the test is exported, when it is flushed.
            "DD_RUNTIME_METRICS_ENABLED": "false",
            "OTEL_METRIC_EXPORT_INTERVAL": "60000",
            "DD_TRACE_DEBUG": None,
            "CORECLR_ENABLE_PROFILING": "1",  # .NET instruments the OpenTelemetry APIs through the profiler
        }
    ],
)

SPAN_NAME = "otel_mode_span"
METRIC_NAME = "otel_mode_counter"
LOGGER_NAME = "otel_mode_logger"
LOG_MESSAGE = "otel_mode_log"


@pytest.fixture(autouse=True)
def _otlp_endpoints(library_env: dict[str, str], test_agent: TestAgentAPI, test_agent_otlp_http_port: int) -> None:
    # SDKs default to different OTLP protocols, so every signal is pinned to the test agent's HTTP port.
    for signal in ("traces", "metrics", "logs"):
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_PROTOCOL"] = "http/protobuf"
        library_env[f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT"] = (
            f"http://{test_agent.container_name}:{test_agent_otlp_http_port}/v1/{signal}"
        )


def _otlp_span_names(test_agent: TestAgentAPI) -> list[str]:
    names: list[str] = []
    for request in test_agent.otlp_requests():
        if not request["url"].endswith("/v1/traces"):
            continue
        body = base64.b64decode(request["body"])
        headers = {name.lower(): value for name, value in request["headers"].items()}
        if "json" in headers.get("content-type", ""):
            payload = json.loads(body)
        else:
            payload = MessageToDict(ExportTraceServiceRequest.FromString(body))
        for resource_spans in payload.get("resourceSpans", []):
            for scope_spans in resource_spans.get("scopeSpans", []):
                names.extend(span["name"] for span in scope_spans.get("spans", []))
    return names


def _otlp_metric_names(test_agent: TestAgentAPI) -> list[str]:
    return [
        metric["name"]
        for payload in test_agent.metrics()
        for resource_metrics in payload.get("resource_metrics", [])
        for scope_metrics in resource_metrics.get("scope_metrics", [])
        for metric in scope_metrics.get("metrics", [])
    ]


def _wait_for(name: str, get_names: Callable[[TestAgentAPI], list[str]], test_agent: TestAgentAPI) -> None:
    names: list[str] = []
    for _ in range(50):
        names = get_names(test_agent)
        if name in names:
            return
        time.sleep(0.1)
    pytest.fail(f"{name} was not exported over OTLP. Exported: {names}")


@scenarios.parametric
@features.otel_api
class Test_OTel_Mode_Traces:
    def test_span_is_exported_over_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            with test_library.otel_start_span(SPAN_NAME):
                pass
            assert test_library.otel_flush(timeout_sec=5)

        _wait_for(SPAN_NAME, _otlp_span_names, test_agent)
        # The span is exported over OTLP instead of the Datadog protocol.
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1)


@scenarios.parametric
@features.otel_metrics_api
class Test_OTel_Mode_Metrics:
    def test_metric_is_exported_over_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            generate_default_counter_data_point(test_library, METRIC_NAME)

        _wait_for(METRIC_NAME, _otlp_metric_names, test_agent)


@scenarios.parametric
@features.otel_logs_enabled
class Test_OTel_Mode_Logs:
    def test_log_is_exported_over_otlp(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        with test_library:
            test_library.create_logger(LOGGER_NAME, LogLevel.INFO)
            test_library.write_log(LOGGER_NAME, LogLevel.INFO, LOG_MESSAGE)

        log_payloads = test_agent.wait_for_num_log_payloads(1)
        assert find_log_record(log_payloads, LOGGER_NAME, LOG_MESSAGE) is not None

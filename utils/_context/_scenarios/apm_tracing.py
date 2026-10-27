from ._core import DdTraceEndToEndScenario
from utils.proxy.ports import ProxyPorts
import json


# APM tracing end-to-end scenarios
class ApmTracingE2eOtel(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APM_TRACING_E2E_OTEL",
            weblog_env={"DD_TRACE_OTEL_ENABLED": "true"},
            mocked_backend_v2=True,
            use_proxy_for_agent=False,
            doc="",
        )


class ApmTracingE2eSingleSpan(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APM_TRACING_E2E_SINGLE_SPAN",
            weblog_env={
                "DD_SPAN_SAMPLING_RULES": json.dumps(
                    [{"service": "weblog", "name": "*single_span_submitted", "sample_rate": 1.0, "max_per_second": 50}]
                ),
                "DD_TRACE_SAMPLE_RATE": "0",
            },
            mocked_backend_v2=True,
            use_proxy_for_agent=False,
            doc="",
        )


class ApmTracingOtlp(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APM_TRACING_OTLP",
            weblog_env={
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                "DD_TRACE_OTEL_ENABLED": "true",
            },
            backend_interface_timeout=5,
            include_opentelemetry=True,
            doc="",
        )


class ApmTracingEfficientPayload(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APM_TRACING_EFFICIENT_PAYLOAD",
            weblog_env={
                "DD_TRACE_SAMPLE_RATE": "1.0",
                "DD_TRACE_AGENT_PROTOCOL_VERSION": "1.0",
            },
            agent_env={
                "DD_APM_ENABLE_V1_TRACE_ENDPOINT": "true",
            },
            mocked_backend_v2=True,
            use_proxy_for_agent=False,
            doc="End-to-end testing scenario focused on efficient payload handling and v1 trace format validation",
        )

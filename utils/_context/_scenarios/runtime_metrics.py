from ._core import DdTraceEndToEndScenario
from utils.proxy.ports import ProxyPorts


class RuntimeMetricsEnabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "RUNTIME_METRICS_ENABLED",
            # Add environment variable DD_DOGSTATSD_START_DELAY=0 to avoid the default 30s startup delay in the Java
            # tracer. That delay is used in production to reduce the impact on startup and other side-effects on various
            # application servers. These considerations do not apply to the system-tests environment so we can reduce it
            # to 0s.
            weblog_env={"DD_DOGSTATSD_START_DELAY": "0"},
            runtime_metrics_enabled=True,
            library_interface_timeout=20,
            doc="Test runtime metrics",
        )


class OtlpRuntimeMetrics(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTLP_RUNTIME_METRICS",
            weblog_env={
                "DD_METRICS_OTEL_ENABLED": "true",
                "DD_DOGSTATSD_START_DELAY": "0",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/metrics",
                "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                "GOMEMLIMIT": "500MiB",
            },
            runtime_metrics_enabled=True,
            include_opentelemetry=True,
            library_interface_timeout=20,
            mocked_backend_v2=True,
            use_proxy_for_agent=False,
            doc="Test ddtrace runtime metrics exported via OTLP with OTel semantic convention names",
        )

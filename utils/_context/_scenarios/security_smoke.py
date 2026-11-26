"""AAP smoke coverage with native trace export and OTLP through bundled DDOT."""

from utils.proxy.ports import ProxyPorts

from ._core import DdTraceEndToEndScenario, scenario_groups


class SecuritySmoke(DdTraceEndToEndScenario):
    """AppSec payload carrier preservation through classic Agent infrastructure."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE",
            rc_api_enabled=True,
            weblog_env={
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            },
            scenario_groups=[scenario_groups.appsec],
        )


class SecuritySmokeOtlp(DdTraceEndToEndScenario):
    """Run the same security checks with Datadog API and OTLP export through bundled DDOT."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE_OTLP",
            rc_api_enabled=True,
            agent_image_variant="full",
            include_opentelemetry=True,
            open_telemetry_interface_timeout=5,
            weblog_env={
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
                "DD_TRACE_OTEL_ENABLED": "true",
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "false",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            },
            scenario_groups=[scenario_groups.appsec, scenario_groups.open_telemetry],
        )

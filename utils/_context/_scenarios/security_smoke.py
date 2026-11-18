"""AAP smoke coverage with native trace export and OTLP through bundled DDOT."""

import pytest

from utils._context.containers import DdotAgentContainer
from utils.proxy.ports import ProxyPorts

from ._core import DdTraceEndToEndScenario, scenario_groups


_SMOKE_WEBLOG_ENV: dict[str, str | None] = {
    "DD_TELEMETRY_METRICS_ENABLED": "true",
    "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
    "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
    "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
}


class SecuritySmoke(DdTraceEndToEndScenario):
    """AppSec payload carrier preservation through classic Agent infrastructure."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE",
            rc_api_enabled=True,
            weblog_env=_SMOKE_WEBLOG_ENV,
            scenario_groups=[scenario_groups.appsec],
        )


class SecuritySmokeOtlp(DdTraceEndToEndScenario):
    """Run the same security checks with Datadog API and OTLP export through bundled DDOT."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE_OTLP",
            # Keep the native smoke suite's Remote Config fixture; only traces go through DDOT.
            rc_api_enabled=True,
            agent_container_class=DdotAgentContainer,
            include_opentelemetry=True,
            library_interface_timeout=0,
            open_telemetry_interface_timeout=5,
            weblog_env={
                **_SMOKE_WEBLOG_ENV,
                "DD_TRACE_OTEL_ENABLED": "false",
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "false",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            },
            scenario_groups=[scenario_groups.appsec, scenario_groups.open_telemetry],
        )

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)
        environment = self.weblog_container.environment
        if self.weblog_infra.library_name == "java":
            # Java gates the OTEL_* aliases on the OTel API bridge.
            environment["DD_TRACE_OTEL_EXPORTER"] = "otlp"
            environment["DD_OTLP_TRACES_PROTOCOL"] = "HTTP_PROTOBUF"
            environment["DD_OTLP_TRACES_ENDPOINT"] = environment["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]
            environment["DD_OTLP_TRACES_HEADERS"] = environment["OTEL_EXPORTER_OTLP_TRACES_HEADERS"]
        elif self.weblog_infra.library_name in ("nodejs", "dotnet"):
            environment["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/json"

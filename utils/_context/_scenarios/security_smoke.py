"""The same backend security contracts through three SDK/Agent topologies."""

import pytest

from ._core import EndToEndScenario, FakeDatadogKey, scenario_groups
from utils._context.constants import ContainerPorts
from utils._context.containers import AgentContainer, DdotAgentContainer, VCRCassettesContainer
from utils.proxy.ports import ProxyPorts


class SecuritySmoke(EndToEndScenario):
    def __init__(
        self,
        name: str = "SECURITY_SMOKE",
        *,
        otel_api: bool = False,
        otlp: bool = False,
        runtime_activation: bool = False,
    ) -> None:
        self._otlp = otlp
        weblog_env: dict[str, str | None] = {
            "DD_TRACE_OTEL_ENABLED": str(otel_api).lower(),
        }
        if not runtime_activation:
            weblog_env.update(
                {
                    "DD_API_SECURITY_ENABLED": "true",
                    "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                    "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
                    "DD_APPSEC_SCA_ENABLED": "true",
                    "DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED": "true",
                    # Drain Java's class-loading queue within the smoke-test capture window.
                    "DD_TELEMETRY_DEPENDENCY_RESOLUTION_PERIOD_MILLIS": "1",
                    "DD_AI_GUARD_ENABLED": "true",
                    "DD_AI_GUARD_ENDPOINT": f"http://vcr_cassettes:{ContainerPorts.vcr_cassettes}/vcr/aiguard",
                    "DD_API_KEY": FakeDatadogKey.AI_GUARD_API,
                    "DD_APP_KEY": FakeDatadogKey.AI_GUARD_APP,
                }
            )
        if otlp:
            weblog_env.update(
                {
                    "OTEL_TRACES_EXPORTER": "otlp",
                    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                    "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                    "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
                }
            )
        if runtime_activation:
            # An explicit DD_APPSEC_ENABLED value takes precedence over ASM_FEATURES.
            weblog_env["DD_APPSEC_ENABLED"] = None
            weblog_env["DD_APPSEC_WAF_TIMEOUT"] = "10000000"
            weblog_env["DD_APPSEC_TRACE_RATE_LIMIT"] = "10000"
        super().__init__(
            name,
            # Explicit weblog metadata opts in one framework per language.
            weblog_categories=[],
            weblog_env=weblog_env,
            appsec_enabled=not runtime_activation,
            iast_enabled=not runtime_activation,
            agent_container_class=DdotAgentContainer if otlp else AgentContainer,
            include_opentelemetry=otlp,
            library_interface_timeout=0,
            agent_interface_timeout=10,
            open_telemetry_interface_timeout=5 if otlp else 0,
            tracer_sampling_rate=1.0,
            other_weblog_containers=() if runtime_activation else (VCRCassettesContainer,),
            scenario_groups=[scenario_groups.appsec, scenario_groups.open_telemetry],
            doc="Security smoke tests against backend intake with the regular Datadog SDK and Agent",
        )

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)
        if self._otlp and self.weblog_infra.library_name in ("nodejs", "dotnet"):
            # HTTP/JSON also covers .NET versions predating its protobuf exporter.
            self.weblog_container.environment["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/json"


class SecuritySmokeOtelApi(SecuritySmoke):
    def __init__(self) -> None:
        super().__init__("SECURITY_SMOKE_OTEL_API", otel_api=True)


class SecuritySmokeDdot(SecuritySmoke):
    def __init__(self) -> None:
        super().__init__("SECURITY_SMOKE_DDOT", otel_api=True, otlp=True)


class SecuritySmokeRuntimeActivation(SecuritySmoke):
    def __init__(self) -> None:
        super().__init__("SECURITY_SMOKE_RUNTIME_ACTIVATION", runtime_activation=True)


class SecuritySmokeOtelApiRuntimeActivation(SecuritySmoke):
    def __init__(self) -> None:
        super().__init__("SECURITY_SMOKE_OTEL_API_RUNTIME_ACTIVATION", otel_api=True, runtime_activation=True)


class SecuritySmokeDdotRuntimeActivation(SecuritySmoke):
    def __init__(self) -> None:
        super().__init__("SECURITY_SMOKE_DDOT_RUNTIME_ACTIVATION", otel_api=True, otlp=True, runtime_activation=True)

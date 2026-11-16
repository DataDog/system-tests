"""The same backend security contracts across API, export format and semantic-convention modes."""

from collections.abc import Callable
from functools import partial

import pytest

from ._core import EndToEndScenario, FakeDatadogKey, scenario_groups
from utils._context.constants import ContainerPorts, WeblogCategory
from utils._context.containers import AgentContainer, DdotAgentContainer, VCRCassettesContainer
from utils.proxy.ports import ProxyPorts


class SecuritySmoke(EndToEndScenario):
    def __init__(
        self,
        name: str = "SECURITY_SMOKE",
        *,
        otel_api: bool = False,
        otlp: bool = False,
        otel_semantics: bool = False,
        runtime_activation: bool = False,
    ) -> None:
        self.otel_api = otel_api
        self.otlp = otlp
        self.otel_semantics = otel_semantics
        weblog_env: dict[str, str | None] = {
            "DD_TRACE_OTEL_ENABLED": str(otel_api).lower(),
            "DD_TRACE_OTEL_SEMANTICS_ENABLED": str(otel_semantics).lower(),
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
                }
            )
        if runtime_activation:
            # An explicit DD_APPSEC_ENABLED value takes precedence over ASM_FEATURES.
            weblog_env["DD_APPSEC_ENABLED"] = None
            weblog_env["DD_APPSEC_WAF_TIMEOUT"] = "10000000"
            weblog_env["DD_APPSEC_TRACE_RATE_LIMIT"] = "10000"
        super().__init__(
            name,
            weblog_categories=[WeblogCategory.dd_trace],
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
            scenario_groups=[
                scenario_groups.appsec,
                scenario_groups.open_telemetry,
                scenario_groups.security_smoke_runtime_activation
                if runtime_activation
                else scenario_groups.security_smoke,
            ],
            doc=(
                f"Backend security smoke: {'OTel' if otel_api else 'Datadog'} API, "
                f"{'OTLP' if otlp else 'Datadog'} export, OTel semantics {otel_semantics}, "
                f"runtime activation {runtime_activation}"
            ),
        )

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)
        if self.otlp and self.weblog_infra.library_name == "java":
            # Java only reads OTEL_* aliases with its bridge enabled. Use its native
            # configuration keys so OTLP also works with the Datadog API selection.
            environment = self.weblog_container.environment
            environment["DD_TRACE_OTEL_EXPORTER"] = "otlp"
            environment["DD_OTLP_TRACES_PROTOCOL"] = "HTTP_PROTOBUF"
            environment["DD_OTLP_TRACES_ENDPOINT"] = environment["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"]
            environment["DD_OTLP_TRACES_HEADERS"] = environment["OTEL_EXPORTER_OTLP_TRACES_HEADERS"]
        if self.otlp and self.weblog_infra.library_name in ("nodejs", "dotnet"):
            # HTTP/JSON also covers .NET versions predating its protobuf exporter.
            self.weblog_container.environment["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/json"


def _create_scenarios() -> list[Callable[[], SecuritySmoke]]:
    constructors: list[Callable[[], SecuritySmoke]] = []
    for base_name, otel_api, otlp, otel_semantics in (
        ("SECURITY_SMOKE", False, False, False),
        ("SECURITY_SMOKE_OTEL_SEMANTICS", False, False, True),
        ("SECURITY_SMOKE_OTEL_API", True, False, False),
        ("SECURITY_SMOKE_OTEL_API_SEMANTICS", True, False, True),
        ("SECURITY_SMOKE_OTLP", False, True, False),
        ("SECURITY_SMOKE_OTLP_SEMANTICS", False, True, True),
        ("SECURITY_SMOKE_OTEL_API_OTLP", True, True, False),
        ("SECURITY_SMOKE_DDOT", True, True, True),
    ):
        for runtime_activation in (False, True):
            name = f"{base_name}_RUNTIME_ACTIVATION" if runtime_activation else base_name
            constructors.append(
                partial(
                    SecuritySmoke,
                    name,
                    otel_api=otel_api,
                    otlp=otlp,
                    otel_semantics=otel_semantics,
                    runtime_activation=runtime_activation,
                )
            )
    return constructors


(
    security_smoke,
    security_smoke_runtime_activation,
    security_smoke_otel_semantics,
    security_smoke_otel_semantics_runtime_activation,
    security_smoke_otel_api,
    security_smoke_otel_api_runtime_activation,
    security_smoke_otel_api_semantics,
    security_smoke_otel_api_semantics_runtime_activation,
    security_smoke_otlp,
    security_smoke_otlp_runtime_activation,
    security_smoke_otlp_semantics,
    security_smoke_otlp_semantics_runtime_activation,
    security_smoke_otel_api_otlp,
    security_smoke_otel_api_otlp_runtime_activation,
    security_smoke_ddot,
    security_smoke_ddot_runtime_activation,
) = _create_scenarios()

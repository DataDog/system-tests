"""Native AAP smoke coverage using the standard Agent and weblog selection."""

from ._core import DdTraceEndToEndScenario, scenario_groups


class SecuritySmoke(DdTraceEndToEndScenario):
    """AAP detection, metadata, user events, telemetry and remote configuration at backend intake."""

    def __init__(self) -> None:
        super().__init__(
            "SECURITY_SMOKE",
            appsec_enabled=True,
            iast_enabled=False,
            tracer_sampling_rate=1.0,
            weblog_env={
                "DD_TRACE_OTEL_ENABLED": "false",
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "false",
                "DD_API_SECURITY_ENABLED": "false",
                "DD_APPSEC_SCA_ENABLED": "false",
            },
            scenario_groups=[scenario_groups.appsec],
        )

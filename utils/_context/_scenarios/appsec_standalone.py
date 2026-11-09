from ._core import DdTraceEndToEndScenario, scenario_groups


class AppsecStandalone(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_STANDALONE",
            weblog_env={
                "DD_APPSEC_ENABLED": "true",
                "DD_APM_TRACING_ENABLED": "false",
                "DD_IAST_ENABLED": "false",
                "DD_API_SECURITY_ENABLED": "false",
                # added to test Test_ExtendedHeaderCollection
                "DD_APPSEC_COLLECT_ALL_HEADERS": "true",
                "DD_APPSEC_HEADER_COLLECTION_REDACTION_ENABLED": "false",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="Appsec standalone mode (APM opt out), with the infra product disabled on the agent",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecApmStandalone(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_APM_STANDALONE",
            rc_api_enabled=True,
            weblog_env={
                "DD_APM_TRACING_ENABLED": "true",
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="Appsec with APM Standalone (infra opt out)",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecStandaloneApmStandalone(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_STANDALONE_APM_STANDALONE",
            rc_api_enabled=True,
            weblog_env={
                "DD_APM_TRACING_ENABLED": "false",
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="Appsec standalone mode (APM opt out) with APM Standalone (infra opt out)",
            scenario_groups=[scenario_groups.appsec],
        )


# Combined scenario for API Security in standalone mode
class AppsecStandaloneApiSecurity(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_STANDALONE_API_SECURITY",
            appsec_enabled=True,
            weblog_env={
                "DD_APPSEC_ENABLED": "true",
                "DD_APM_TRACING_ENABLED": "false",
                "DD_IAST_ENABLED": "false",
                "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_SAMPLE_DELAY": "3",
            },
            doc="Scenario to test API Security in AppSec standalone mode",
            scenario_groups=[scenario_groups.appsec, scenario_groups.essentials],
        )


class IastStandalone(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "IAST_STANDALONE",
            weblog_env={
                "DD_APPSEC_ENABLED": "false",
                "DD_APM_TRACING_ENABLED": "false",
                "DD_IAST_ENABLED": "true",
                "DD_IAST_DETECTION_MODE": "FULL",
                "DD_IAST_DEDUPLICATION_ENABLED": "false",
                "DD_IAST_REQUEST_SAMPLING": "100",
                "DD_IAST_VULNERABILITIES_PER_REQUEST": "10",
                "DD_IAST_MAX_CONTEXT_OPERATIONS": "10",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="Source code vulnerability standalone mode (APM opt out), with the infra product disabled on the agent",
            scenario_groups=[scenario_groups.appsec],
        )


class ScaStandalone(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "SCA_STANDALONE",
            weblog_env={
                "DD_APPSEC_ENABLED": "false",
                "DD_APPSEC_SCA_ENABLED": "true",
                "DD_APM_TRACING_ENABLED": "false",
                "DD_IAST_ENABLED": "false",
                "DD_TELEMETRY_DEPENDENCY_RESOLUTION_PERIOD_MILLIS": "1",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            },
            agent_env={
                "DD_INFRASTRUCTURE_MODE": "none",
            },
            doc="SCA standalone mode (APM opt out), with the infra product disabled on the agent",
            scenario_groups=[scenario_groups.appsec],
        )

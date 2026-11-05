from ._core import DdTraceEndToEndScenario, scenario_groups


# Telemetry scenarios
class TelemetryDependencyLoadedTestForDependencyCollectionDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_DEPENDENCY_LOADED_TEST_FOR_DEPENDENCY_COLLECTION_DISABLED",
            weblog_env={"DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED": "false"},
            doc="Test DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED=false effect on tracers",
            scenario_groups=[scenario_groups.telemetry],
        )


class TelemetryAppStartedProductsDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_APP_STARTED_PRODUCTS_DISABLED",
            weblog_env={
                "DD_APPSEC_ENABLED": "false",
                "DD_PROFILING_ENABLED": "false",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "false",
                # RFC-1113: agentic-onboarding flag set while AppSec is disabled. The value is
                # reported verbatim ("true"), decoupled from AppSec state (no derived boolean).
                "DD_APPSEC_AGENTIC_ONBOARDING": "true",
            },
            appsec_enabled=False,
            doc="Disable all tracers products",
            scenario_groups=[scenario_groups.telemetry],
        )


class TelemetryEnhancedConfigReporting(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_ENHANCED_CONFIG_REPORTING",
            weblog_env={
                "DD_LOGS_INJECTION": "false",
                "CONFIG_CHAINING_TEST": "true",
                "DD_TRACE_CONFIG": "/app/ConfigChaining.properties",
                # RFC-1113: agentic-onboarding flag set while AppSec is enabled. The value is
                # reported verbatim; a mixed-case arbitrary value is intentional to prove it is a
                # pass-through of the configured value (not a boolean derived from AppSec being
                # active, and not lowercased/normalized by the tracer).
                "DD_APPSEC_AGENTIC_ONBOARDING": "MiXeD-Value_42",
            },
            doc="Test telemetry for environment variable configurations",
            scenario_groups=[scenario_groups.telemetry],
        )


class TelemetryLogGenerationDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_LOG_GENERATION_DISABLED",
            weblog_env={"DD_TELEMETRY_LOG_COLLECTION_ENABLED": "false"},
            doc="Test env var `DD_TELEMETRY_LOG_COLLECTION_ENABLED=false`",
            scenario_groups=[scenario_groups.telemetry],
        )


class TelemetryMetricGenerationDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_METRIC_GENERATION_DISABLED",
            weblog_env={"DD_TELEMETRY_METRICS_ENABLED": "false"},
            doc="Test env var `DD_TELEMETRY_METRICS_ENABLED=false`",
            scenario_groups=[scenario_groups.telemetry],
        )


class TelemetryExtendedHeartbeat(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TELEMETRY_EXTENDED_HEARTBEAT",
            weblog_env={
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "1",
                "DD_TELEMETRY_EXTENDED_HEARTBEAT_INTERVAL": "2",
                "_DD_TELEMETRY_EXTENDED_HEARTBEAT_INTERVAL": "2",
            },
            doc="Test app-extended-heartbeat telemetry event with a shortened interval",
            scenario_groups=[scenario_groups.telemetry],
        )

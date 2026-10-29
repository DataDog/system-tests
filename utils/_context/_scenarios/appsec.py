import pytest

from ._core import DdTraceEndToEndScenario, EndToEndScenario, scenario_groups
from utils._context.constants import WeblogCategory
from utils._context.containers import PostgresContainer


# ASM scenarios
class AppsecMissingRules(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_MISSING_RULES",
            weblog_env={"DD_APPSEC_RULES": "/donotexists"},
            doc="Test missing appsec rules file",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecCorruptedRules(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_CORRUPTED_RULES",
            weblog_env={"DD_APPSEC_RULES": "/appsec_corrupted_rules.json"},
            weblog_volumes={
                "./tests/appsec/appsec_corrupted_rules.json": {"bind": "/appsec_corrupted_rules.json", "mode": "ro"}
            },
            doc="Test corrupted appsec rules file",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecCustomRules(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_CUSTOM_RULES",
            weblog_env={
                "DD_APPSEC_RULES": "/appsec_custom_rules.json",
                "DD_APPSEC_RAW_RESPONSE_BODY_ENABLED": "1",
            },
            weblog_volumes={"./tests/appsec/custom_rules.json": {"bind": "/appsec_custom_rules.json", "mode": "ro"}},
            doc="Test custom appsec rules file",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecRulesMonitoringWithErrors(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RULES_MONITORING_WITH_ERRORS",
            weblog_env={"DD_APPSEC_RULES": "/appsec_custom_rules_with_errors.json"},
            weblog_volumes={
                "./tests/appsec/custom_rules_with_errors.json": {
                    "bind": "/appsec_custom_rules_with_errors.json",
                    "mode": "ro",
                }
            },
            doc="Appsec rule file with some errors",
            scenario_groups=[scenario_groups.appsec],
        )


class EverythingDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "EVERYTHING_DISABLED",
            weblog_env={"DD_APPSEC_ENABLED": "false", "DD_DBM_PROPAGATION_MODE": "disabled"},
            appsec_enabled=False,
            other_weblog_containers=(PostgresContainer,),
            doc="Disable appsec and test DBM setting integration outcome when disabled",
            scenario_groups=[scenario_groups.appsec, scenario_groups.end_to_end, scenario_groups.tracer_release],
        )


class AppsecLowWafTimeout(EndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_LOW_WAF_TIMEOUT",
            doc="Appsec with a very low WAF timeout",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_low_waf_timeout],
            weblog_categories=[WeblogCategory.dd_trace],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)
        library = self.weblog_infra.library_name
        # python lib use milliseconds for DD_APPSEC_WAF_TIMEOUT
        # and other libs use microseconds
        # see https://datadoghq.atlassian.net/wiki/spaces/SAAL/pages/2355333252/Environment+Variables
        self.weblog_container.environment["DD_APPSEC_WAF_TIMEOUT"] = "0.001" if library == "python" else "1"


class AppsecCustomObfuscation(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_CUSTOM_OBFUSCATION",
            weblog_env={
                "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
                "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
            },
            doc="Test custom appsec obfuscation parameters",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecRateLimiter(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RATE_LIMITER",
            weblog_env={"DD_APPSEC_TRACE_RATE_LIMIT": "1", "RAILS_MAX_THREADS": "1"},
            doc="Tests with a low rate trace limit for Appsec",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecWafTelemetry(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_WAF_TELEMETRY",
            weblog_env={
                "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "true",
                "DD_TELEMETRY_METRICS_ENABLED": "true",
                "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
            },
            doc="Enable Telemetry feature for WAF",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecRuntimeActivation(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RUNTIME_ACTIVATION",
            rc_api_enabled=True,
            appsec_enabled=False,
            iast_enabled=False,
            weblog_env={"DD_APPSEC_WAF_TIMEOUT": "10000000", "DD_APPSEC_TRACE_RATE_LIMIT": "10000"},  # 10 seconds
            doc="",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_rasp],
        )


class RuntimeScaReachability(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "RUNTIME_SCA_REACHABILITY",
            weblog_env={
                "DD_APPSEC_SCA_ENABLED": "true",
            },
            doc="""
            Scenario to test SCA telemetry events
        """,
            scenario_groups=[scenario_groups.appsec],
        )


class IastDeduplication(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "IAST_DEDUPLICATION",
            weblog_env={
                "DD_IAST_ENABLED": "true",
                "DD_IAST_DEDUPLICATION_ENABLED": "true",
                "DD_IAST_REQUEST_SAMPLING": "100",
                "DD_IAST_VULNERABILITIES_PER_REQUEST": "10",
                "DD_IAST_MAX_CONTEXT_OPERATIONS": "10",
            },
            doc="Iast scenario with deduplication enabled",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecMetaStructDisabled(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_META_STRUCT_DISABLED",
            weblog_env={"DD_APPSEC_ENABLED": "true", "DD_IAST_ENABLED": "true"},
            meta_structs_disabled=True,
            doc="Appsec tests with support for meta struct disabled in the agent configuration",
            scenario_groups=[scenario_groups.appsec],
        )

from ._core import DdTraceEndToEndScenario, scenario_groups


class AppsecBlocking(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_BLOCKING",
            weblog_env={
                "DD_APPSEC_RULES": "/appsec_blocking_rule.json",
                "DD_TRACE_RESOURCE_RENAMING_ALWAYS_SIMPLIFIED_ENDPOINT": "true",
                "DD_TRACE_COMPUTE_STATS": "true",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",
                "DD_IAST_WEAK_HASH_ALGORITHMS": "NOTexist",
            },
            weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
            doc="Misc tests for appsec blocking",
            scenario_groups=[scenario_groups.appsec, scenario_groups.essentials],
        )


class AppsecBlockingFullDenylist(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_BLOCKING_FULL_DENYLIST",
            rc_api_enabled=True,
            weblog_env={"DD_APPSEC_RULES": None},
            doc="""
            The spec says that if  DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, when remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
            scenario_groups=[scenario_groups.appsec],
        )

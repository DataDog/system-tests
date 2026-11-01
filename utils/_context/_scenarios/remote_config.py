from ._core import DdTraceEndToEndScenario, scenario_groups


class RemoteConfigMockedBackendAsmFeatures(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
            rc_api_enabled=True,
            appsec_enabled=False,
            weblog_env={"DD_REMOTE_CONFIGURATION_ENABLED": "true"},
            doc="",
            scenario_groups=[scenario_groups.appsec, scenario_groups.remote_config, scenario_groups.essentials],
        )


class RemoteConfigMockedBackendLiveDebugging(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
            rc_api_enabled=True,
            weblog_env={
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
                "DD_DEBUGGER_ENABLED": "1",
                "DD_REMOTE_CONFIG_ENABLED": "true",
                "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "1",
            },
            doc="",
            scenario_groups=[scenario_groups.remote_config, scenario_groups.essentials],
        )


class RemoteConfigMockedBackendAsmDd(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
            rc_api_enabled=True,
            weblog_env={"DD_APPSEC_RULES": None},
            doc="""
            The spec says that if DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, when remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
            scenario_groups=[
                scenario_groups.appsec,
                scenario_groups.appsec_rasp,
                scenario_groups.remote_config,
                scenario_groups.essentials,
            ],
        )


class RemoteConfigMockedBackendAsmFeaturesNocache(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
            rc_api_enabled=True,
            weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true"},
            doc="",
            scenario_groups=[scenario_groups.appsec, scenario_groups.remote_config],
        )

from ._core import DdTraceEndToEndScenario, scenario_groups


class AppsecApiSecurity(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_API_SECURITY",
            appsec_enabled=True,
            weblog_env={
                "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
                "DD_API_SECURITY_ENDPOINT_COLLECTION_ENABLED": "true",
                "DD_API_SECURITY_ENDPOINT_COLLECTION_MESSAGE_LIMIT": "30",
            },
            doc="""
        Scenario for API Security feature, testing schema types sent into span tags if
        DD_API_SECURITY_ENABLED is set to true.
        """,
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecApiSecurityRc(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_API_SECURITY_RC",
            weblog_env={
                "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
                "DD_APPSEC_WAF_TIMEOUT": "10000000",
                "DD_APPSEC_TRACE_RATE_LIMIT": "10000",
            },
            rc_api_enabled=True,
            doc="""
            Scenario to test API Security Remote config
        """,
            scenario_groups=[scenario_groups.appsec, scenario_groups.remote_config, scenario_groups.essentials],
        )


class AppsecApiSecurityNoResponseBody(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_API_SECURITY_NO_RESPONSE_BODY",
            appsec_enabled=True,
            weblog_env={
                "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
                "DD_API_SECURITY_PARSE_RESPONSE_BODY": "false",
            },
            doc="""
        Scenario for API Security feature, testing schema types sent into span tags if
        DD_API_SECURITY_ENABLED is set to true.
        """,
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecApiSecurityWithSampling(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_API_SECURITY_WITH_SAMPLING",
            appsec_enabled=True,
            weblog_env={
                "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_ENABLED": "true",
                "DD_API_SECURITY_SAMPLE_DELAY": "3",
                "DD_TRACE_RESOURCE_RENAMING_ENABLED": "false",
            },
            doc="""
        Scenario for API Security feature, testing api security sampling rate.
        """,
            scenario_groups=[scenario_groups.appsec, scenario_groups.essentials],
        )

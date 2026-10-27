from ._core import DdTraceEndToEndScenario, scenario_groups
from utils._context.containers import InternalServerContainer


class AppsecAutoEventsExtended(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_AUTO_EVENTS_EXTENDED",
            weblog_env={
                "DD_APPSEC_ENABLED": "true",
                "DD_APPSEC_AUTOMATED_USER_EVENTS_TRACKING": "extended",
                "DD_APPSEC_AUTO_USER_INSTRUMENTATION_MODE": "anonymization",
            },
            appsec_enabled=True,
            doc="Scenario for checking extended mode in automatic user events",
            scenario_groups=[scenario_groups.appsec],
        )


class AppsecAutoEventsRc(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_AUTO_EVENTS_RC",
            weblog_env={"DD_APPSEC_ENABLED": "true", "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5"},
            rc_api_enabled=True,
            doc="""
            Scenario to test User ID collection config change via Remote config
        """,
            scenario_groups=[scenario_groups.appsec],
            other_weblog_containers=(InternalServerContainer,),
        )


class AppsecAtoSdk(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_ATO_SDK",
            weblog_env={"DD_APPSEC_ENABLED": "true", "DD_APPSEC_RULES": "/appsec_ato_sdk.json"},
            weblog_volumes={
                "./tests/appsec/appsec_ato_sdk.json": {
                    "bind": "/appsec_ato_sdk.json",
                    "mode": "ro",
                }
            },
            doc="Rules file with unsafe login and user id",
            scenario_groups=[scenario_groups.appsec],
        )

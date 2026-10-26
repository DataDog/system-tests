from ._core import EndToEndScenario, scenario_groups
from utils._context.constants import WeblogCategory
from utils._context.containers import InternalServerContainer


class _AppsecRaspScenario(EndToEndScenario):
    def __init__(
        self,
        name: str,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict[str, dict[str, str]] | None = None,
    ):
        if weblog_env is None:
            weblog_env = {}
        if weblog_volumes is None:
            weblog_volumes = {}

        default_env: dict[str, str | None] = {
            "DD_APPSEC_RASP_ENABLED": "true",
            "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
            # added to test Test_ExtendedRequestBodyCollection
            "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
            "DD_API_SECURITY_DOWNSTREAM_BODY_ANALYSIS_SAMPLE_RATE": "1.0",
            "DD_API_SECURITY_MAX_DOWNSTREAM_BODY_BYTES": "128",
            "OPENAI_BASE_URL": "http://internal_server:8089",
        }
        merged_env = default_env | weblog_env

        super().__init__(
            name,
            weblog_env=merged_env,
            weblog_volumes={
                "./tests/appsec/rasp/rasp_ruleset.json": {"bind": "/appsec_rasp_ruleset.json", "mode": "ro"}
            }
            | weblog_volumes,
            doc="Enable APPSEC RASP",
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_rasp, scenario_groups.appsec_rasp_scenario],
            weblog_categories=[WeblogCategory.dd_trace],
            other_weblog_containers=(InternalServerContainer,),
        )


class AppsecRasp(_AppsecRaspScenario):
    def __init__(self) -> None:
        super().__init__("APPSEC_RASP")


class AppsecRaspWithoutDownstreamBodyAnalysisUsingSampleRate(_AppsecRaspScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RASP_WITHOUT_DOWNSTREAM_BODY_ANALYSIS_USING_SAMPLE_RATE",
            weblog_env={
                "DD_API_SECURITY_DOWNSTREAM_BODY_ANALYSIS_SAMPLE_RATE": "0",
            },
        )


class AppsecRaspWithoutDownstreamBodyAnalysisUsingMax(_AppsecRaspScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RASP_WITHOUT_DOWNSTREAM_BODY_ANALYSIS_USING_MAX",
            weblog_env={
                "DD_API_SECURITY_MAX_DOWNSTREAM_REQUEST_BODY_ANALYSIS": "0",
            },
        )


class AppsecStandaloneRasp(_AppsecRaspScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_STANDALONE_RASP",
            weblog_env={
                "DD_APM_TRACING_ENABLED": "false",
            },
        )


class AppsecRaspNonBlocking(_AppsecRaspScenario):
    def __init__(self) -> None:
        super().__init__(
            "APPSEC_RASP_NON_BLOCKING",
            weblog_env={"DD_APPSEC_RULES": "/appsec_rasp_non_blocking_ruleset.json"},
            weblog_volumes={
                "./tests/appsec/rasp/rasp_non_blocking_ruleset.json": {
                    "bind": "/appsec_rasp_non_blocking_ruleset.json",
                    "mode": "ro",
                }
            },
        )

import pytest

from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context._scenarios.core import scenario_groups
from utils._context.containers import InternalServerContainer


class AppsecRaspScenario(EndToEndScenario):
    def __init__(self, name: str, weblog_env: dict[str, str | None] | None = None):
        if weblog_env is None:
            weblog_env = {}

        super().__init__(
            name,
            weblog_env=weblog_env
            | {
                "DD_APPSEC_RASP_ENABLED": "true",
                "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
                # added to test Test_ExtendedRequestBodyCollection
                "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
                "DD_API_SECURITY_DOWNSTREAM_REQUEST_BODY_ANALYSIS_SAMPLE_RATE": "1.0",
            },
            weblog_volumes={
                "./tests/appsec/rasp/rasp_ruleset.json": {"bind": "/appsec_rasp_ruleset.json", "mode": "ro"}
            },
            doc="Enable APPSEC RASP",
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_rasp],
        )
        self._internal_server = InternalServerContainer()
        self.weblog_container.depends_on.append(self._internal_server)
        self._required_containers.append(self._internal_server)

    def configure(self, config: pytest.Config):
        super().configure(config)

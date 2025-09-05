import pytest

from utils._context._scenarios.endtoend import EndToEndScenario
from utils._context._scenarios.core import scenario_groups
from utils._context.containers import InternalServerContainer


class AppsecRaspScenario(EndToEndScenario):
    def __init__(self):
        super().__init__(
            "APPSEC_RASP",
            weblog_env={
                "DD_APPSEC_RASP_ENABLED": "true",
                "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
                # added to test Test_ExtendedRequestBodyCollection
                "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
            },
            weblog_volumes={
                "./tests/appsec/rasp/rasp_ruleset.json": {"bind": "/appsec_rasp_ruleset.json", "mode": "ro"}
            },
            doc="Enable APPSEC RASP",
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.appsec, scenario_groups.appsec_rasp],
        )
        self._internal_server = InternalServerContainer(self.host_log_folder)
        self.weblog_container.depends_on.append(self._internal_server)
        self._required_containers.append(self._internal_server)

    def configure(self, config: pytest.Config):
        super().configure(config)

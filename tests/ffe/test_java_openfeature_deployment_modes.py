"""Validate Java OpenFeature standalone and SSI deployment shapes."""

import json

from utils import context, features, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import JavaOpenFeatureAgentlessEndToEndScenario
from utils.mocked_backend.ffe import CONFIG_PATH


class JavaOpenFeatureDeploymentContract:
    deployment_mode: str

    def setup_deployment_mode(self) -> None:
        self.response = weblog.post(
            "/ffe",
            json={
                "flag": "empty-targeting-key-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "java-openfeature-user",
                "attributes": {},
            },
        )

    def test_deployment_mode(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"
        result = json.loads(self.response.text)
        assert result["value"] == "on-value"
        assert result["provider"] == "datadog-openfeature-provider"
        assert result["deploymentMode"] == self.deployment_mode

        scenario = context.scenario
        assert isinstance(scenario, JavaOpenFeatureAgentlessEndToEndScenario)
        backend_status = scenario.mock_backend_status()
        assert backend_status is not None
        assert backend_status["requests_total"] >= 1
        assert backend_status["last_path"] == CONFIG_PATH


@scenarios.feature_flagging_and_experimentation_java_standalone
@features.feature_flags_agentless
class Test_FFE_Java_OpenFeature_Standalone(JavaOpenFeatureDeploymentContract):
    deployment_mode = "standalone"


@scenarios.feature_flagging_and_experimentation_java_ssi
@features.feature_flags_agentless
class Test_FFE_Java_OpenFeature_SSI(JavaOpenFeatureDeploymentContract):
    deployment_mode = "ssi"

"""Test implicit and explicit agentless UFC delivery."""

import json

from utils import context, features, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingAgentlessEndToEndScenario
from utils.mocked_backend.ffe import CONFIG_PATH


class AgentlessConfigurationContract:
    def setup_agentless_source(self) -> None:
        self.response = weblog.post(
            "/ffe",
            json={
                "flag": "empty-targeting-key-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_agentless_source(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"
        assert json.loads(self.response.text)["value"] == "on-value"

        assert isinstance(context.scenario, FeatureFlaggingAgentlessEndToEndScenario)
        backend_status = context.scenario.mock_backend_status()
        assert backend_status is not None
        assert backend_status["requests_total"] >= 1
        assert backend_status["last_path"] == CONFIG_PATH


@scenarios.feature_flagging_and_experimentation_agentless
@features.feature_flags_agentless
class Test_FFE_Agentless_Configuration(AgentlessConfigurationContract):
    pass


@scenarios.feature_flagging_and_experimentation_agentless_direct
@features.feature_flags_agentless
class Test_FFE_Agentless_Explicit_Configuration(AgentlessConfigurationContract):
    pass

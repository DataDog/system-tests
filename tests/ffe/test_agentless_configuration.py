"""Test default agentless UFC delivery before FFE evaluation."""

import json

from utils import features, scenarios, weblog
from utils.docker_fixtures._mock_ffe_agentless_backend import CONFIG_PATH


@scenarios.feature_flagging_and_experimentation_agentless
@features.feature_flags_agentless
class Test_FFE_Agentless_Configuration:
    def setup_default_agentless_source(self) -> None:
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
        self.backend_status = scenarios.feature_flagging_and_experimentation_agentless.mock_backend_status()

    def test_default_agentless_source(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"
        assert json.loads(self.response.text)["value"] == "on-value"

        assert self.backend_status is not None
        assert self.backend_status["requests_total"] >= 1
        assert self.backend_status["last_path"] == CONFIG_PATH
        assert self.backend_status["last_auth_present"] is True

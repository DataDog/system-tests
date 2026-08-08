"""Test exposure delivery with agentless UFC through sidecar and direct routes."""

from tests.ffe.utils.exposures import assert_exposure_side_effects_contract, exposure_events_from_data
from utils import context, features, interfaces, scenarios, weblog
from utils._context._scenarios.endtoend import FeatureFlaggingAgentlessEndToEndScenario
from utils._context.component_version import Version


@scenarios.feature_flagging_and_experimentation_agentless_direct
@scenarios.feature_flagging_and_experimentation_agentless_serverless
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposures:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-serverless-exposure-user"

    def setup_agentless_exposure(self) -> None:
        self.responses = [
            weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": self.targeting_key,
                    "attributes": {},
                },
            )
            for _ in range(5)
        ]

    def test_agentless_exposure(self) -> None:
        scenario = context.scenario
        assert isinstance(scenario, FeatureFlaggingAgentlessEndToEndScenario)

        if scenario.exposure_egress == "sidecar":
            assert scenario.components["serverless-init"] == Version("1.9.13")
            selected_interface = interfaces.datadog_sidecar
            excluded_interface = interfaces.datadog_direct
        else:
            assert scenario.exposure_egress == "direct"
            assert "serverless-init" not in scenario.components
            selected_interface = interfaces.datadog_direct
            excluded_interface = interfaces.datadog_sidecar

        matching_requests = assert_exposure_side_effects_contract(
            selected_interface,
            self.responses,
            flag_key=self.flag_key,
            targeting_key=self.targeting_key,
            expected_value="on-value",
            expected_variant="on",
        )
        assert len(matching_requests) == 1
        request = matching_requests[0]
        assert request["host"] == "event-platform-intake.datad0g.com"
        assert request["response"]["status_code"] == 202

        headers = {name.lower(): value for name, value in request["request"]["headers"]}
        assert headers["dd-api-key"] == "--redacted--"

        assert not any(
            exposure_events_from_data(data, {self.flag_key}, self.targeting_key)
            for data in excluded_interface.get_data()
        )

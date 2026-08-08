"""Test exposure delivery with agentless UFC and serverless-init."""

from tests.ffe.utils.exposures import assert_exposure_side_effects_contract, exposure_events_from_data
from utils import features, interfaces, scenarios, weblog
from utils._context.component_version import Version


@scenarios.feature_flagging_and_experimentation_agentless_serverless
@features.feature_flags_exposures
class Test_FFE_Agentless_Serverless_Exposures:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-serverless-exposure-user"

    def setup_agentless_serverless_exposure(self) -> None:
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

    def test_agentless_serverless_exposure(self) -> None:
        scenario = scenarios.feature_flagging_and_experimentation_agentless_serverless
        assert scenario.components["serverless-init"] == Version("1.9.13")

        matching_requests = assert_exposure_side_effects_contract(
            interfaces.datadog_sidecar,
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
            for data in interfaces.datadog_direct.get_data()
        )

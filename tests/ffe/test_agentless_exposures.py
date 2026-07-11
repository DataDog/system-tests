"""Test exposure events when UFC is loaded through the default agentless source."""

from tests.ffe.test_exposures import find_exposure_events, wait_for_exposure_event
from tests.ffe.utils.evaluation import evaluate_flag
from utils import features, scenarios


@scenarios.feature_flagging_and_experimentation_agentless
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-exposure-user"

    def setup_agentless_exposure(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key=self.targeting_key)

    def test_agentless_exposure(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        wait_for_exposure_event({self.flag_key}, self.targeting_key)
        events = find_exposure_events(self.flag_key, self.targeting_key)
        assert events, f"No exposure event found for {self.flag_key} and {self.targeting_key}"

        event = events[0]
        assert event["flag"]["key"] == self.flag_key
        assert event["variant"]["key"] == "on"
        assert event["allocation"]["key"] == "default-allocation"
        assert event["subject"]["id"] == self.targeting_key

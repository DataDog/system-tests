"""Test exposure events when UFC is loaded through the default agentless source."""

from tests.ffe.test_exposures import EXPOSURES_PATH, exposure_events_from_data
from tests.ffe.utils.evaluation import evaluate_flag
from tests.ffe.utils.fixtures import JSON
from tests.ffe.utils.telemetry import (
    assert_expected_telemetry_route,
    matching_telemetry,
    wait_for_telemetry,
)
from utils import features, scenarios


@scenarios.feature_flagging_and_experimentation_agentless_sidecar
@scenarios.feature_flagging_and_experimentation_agentless_direct_fallback
@features.feature_flags_exposures
class Test_FFE_Agentless_Exposure:
    flag_key = "empty-targeting-key-flag"
    targeting_key = "agentless-exposure-user"

    def setup_agentless_exposure(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key=self.targeting_key)

    def test_agentless_exposure(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        def matcher(data: JSON) -> bool:
            return bool(exposure_events_from_data(data, {self.flag_key}, self.targeting_key))

        wait_for_telemetry(matcher, "exposure event")

        events = []
        for data in matching_telemetry(matcher):
            if data.get("path") == EXPOSURES_PATH:
                events.extend(exposure_events_from_data(data, {self.flag_key}, self.targeting_key))
        assert events, f"No exposure event found for {self.flag_key} and {self.targeting_key}"
        assert_expected_telemetry_route(matcher, "exposure event")

        event = events[0]
        assert event["flag"]["key"] == self.flag_key
        assert event["variant"]["key"] == "on"
        assert event["allocation"]["key"] == "default-allocation"
        assert event["subject"]["id"] == self.targeting_key

"""Test aggregate evaluation EVP when UFC is loaded through the default agentless source."""

import pytest

from tests.ffe.test_flag_eval_evp import (
    assert_batch_context,
    assert_event_contract,
    evp_flagevaluation_events_from_data,
    object_key,
)
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
@features.feature_flags_evp_flagevaluation
@pytest.mark.skip_if_xfail
class Test_FFE_Agentless_EVP_Flagevaluation:
    flag_key = "empty-targeting-key-flag"

    def setup_agentless_evp_flagevaluation(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key="agentless-evp-user")

    def test_agentless_evp_flagevaluation(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        def matcher(data: JSON) -> bool:
            return bool(evp_flagevaluation_events_from_data(data, self.flag_key))

        wait_for_telemetry(matcher, "aggregate flag-evaluation event")

        events = []
        for data in matching_telemetry(matcher):
            events.extend(evp_flagevaluation_events_from_data(data, self.flag_key))
        assert events, f"No EVP flagevaluation event found for {self.flag_key}"
        assert_expected_telemetry_route(matcher, "aggregate flag-evaluation event")

        batch, event = events[0]
        assert_batch_context(batch)
        assert_event_contract(event, self.flag_key)
        assert object_key(event.get("variant"), "variant") == "on"
        assert object_key(event.get("allocation"), "allocation") == "default-allocation"

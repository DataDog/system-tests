"""Test aggregate evaluation EVP when UFC is loaded through the default agentless source."""

import pytest

from tests.ffe.test_flag_eval_evp import (
    assert_batch_context,
    assert_event_contract,
    find_evp_flagevaluation_events,
    object_key,
    wait_for_evp_flagevaluation_event,
)
from tests.ffe.utils.evaluation import evaluate_flag
from utils import features, scenarios


@scenarios.feature_flagging_and_experimentation_agentless
@features.feature_flags_evp_flagevaluation
@pytest.mark.skip_if_xfail
class Test_FFE_Agentless_EVP_Flagevaluation:
    flag_key = "empty-targeting-key-flag"

    def setup_agentless_evp_flagevaluation(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key="agentless-evp-user")

    def test_agentless_evp_flagevaluation(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"No EVP flagevaluation event found for {self.flag_key}"

        batch, event = events[0]
        assert_batch_context(batch)
        assert_event_contract(event, self.flag_key)
        assert object_key(event.get("variant"), "variant") == "on"
        assert object_key(event.get("allocation"), "allocation") == "default-allocation"

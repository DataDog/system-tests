"""Ruby-specific server-side EVP flagevaluation system tests."""

import json
from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.ffe.test_flag_eval_evp import (
    RC_PATH,
    assert_batch_context,
    assert_event_contract,
    evp_flagevaluation_events_from_data,
    find_evp_flagevaluation_events,
    make_multi_flag_fixture,
)
from utils import HttpResponse
from utils import context
from utils import features
from utils import interfaces
from utils import irrelevant
from utils import remote_config as rc
from utils import scenarios
from utils import weblog


if TYPE_CHECKING:
    from tests.ffe.utils.fixtures import JSON


EVP_PREFORK_WAIT_TIMEOUT_SECONDS = 10


def evaluate_flags_across_fork(
    parent_flag_key: str,
    child_flag_key: str,
    *,
    parent_targeting_key: str,
    child_targeting_key: str,
) -> HttpResponse:
    return weblog.post(
        "/ffe/fork-isolation",
        json={
            "parentFlag": parent_flag_key,
            "childFlag": child_flag_key,
            "variationType": "STRING",
            "defaultValue": "default",
            "parentTargetingKey": parent_targeting_key,
            "childTargetingKey": child_targeting_key,
            "attributes": {},
        },
    )


def wait_for_prefork_child_event(flag_key: str) -> None:
    assert interfaces.agent.wait_for(
        lambda data: bool(evp_flagevaluation_events_from_data(cast("JSON", data), flag_key)),
        timeout=EVP_PREFORK_WAIT_TIMEOUT_SECONDS,
    ), f"Timed out waiting for forked Ruby EVP flagevaluation event for flag {flag_key}"


def flag_keys_from_flagevaluation_batch(batch: object) -> set[str]:
    if not isinstance(batch, dict):
        return set()

    events = batch.get("flagEvaluations")
    if not isinstance(events, list):
        return set()

    flag_keys = set()
    for event in events:
        if not isinstance(event, dict):
            continue

        flag = event.get("flag")
        if not isinstance(flag, dict):
            continue

        key = flag.get("key")
        if isinstance(key, str):
            flag_keys.add(key)

    return flag_keys


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@irrelevant(
    context.library != "ruby" or context.weblog_variant != "rails72",
    reason="Ruby Rails 7.2 fork isolation endpoint only",
)
@pytest.mark.skip_if_xfail
class Test_FFE_EVP_Flagevaluation_Ruby_Fork_Isolation:
    """Test that Ruby child processes do not flush parent EVP evaluation state."""

    def setup_ffe_evp_flagevaluation_ruby_fork_isolation(self) -> None:
        config_id = "ffe-evp-ruby-fork-isolation"
        self.parent_flag_key = "evp-ruby-fork-parent-flag"
        self.child_flag_key = "evp-ruby-fork-child-flag"
        self.parent_targeting_key = "evp-ruby-prefork-parent"
        self.child_targeting_key = "evp-ruby-prefork-child"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_multi_flag_fixture([self.parent_flag_key, self.child_flag_key]),
        ).apply()

        self.r = evaluate_flags_across_fork(
            self.parent_flag_key,
            self.child_flag_key,
            parent_targeting_key=self.parent_targeting_key,
            child_targeting_key=self.child_targeting_key,
        )

    def test_ffe_evp_flagevaluation_ruby_fork_isolation(self) -> None:
        assert self.r.status_code == 200, f"Fork isolation request failed: {self.r.text}"

        response = json.loads(self.r.text)
        assert response["parent"]["reason"] == "DEFAULT", f"Parent evaluation failed: {response}"
        assert response["child"]["reason"] == "DEFAULT", f"Child evaluation failed: {response}"
        assert response["diagnostics"]["evp_writer"], f"Parent process EVP writer is unavailable: {response}"
        assert response["child"]["diagnostics_before_flush"]["evp_writer"], (
            f"Child process EVP writer is unavailable: {response}"
        )

        wait_for_prefork_child_event(self.child_flag_key)
        child_events = find_evp_flagevaluation_events(self.child_flag_key)

        assert child_events, f"Expected child EVP flagevaluation event for flag {self.child_flag_key}"
        for batch, event in child_events:
            assert_batch_context(batch)
            assert_event_contract(event, self.child_flag_key)

        leaked_batches = [
            batch for batch, _ in child_events if self.parent_flag_key in flag_keys_from_flagevaluation_batch(batch)
        ]
        assert not leaked_batches, (
            f"Parent-process EVP flagevaluation state leaked into a forked child flush batch: {leaked_batches}"
        )

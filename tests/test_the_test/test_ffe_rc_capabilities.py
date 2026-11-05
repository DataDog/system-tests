"""Regressions for RC capability assertions, gated startup, and update acknowledgement."""

import base64
from threading import Event
from typing import Any
from unittest.mock import MagicMock, patch

from tests.parametric.test_ffe.dependent_flags_rc import deliver, ffe_requests, start_and_deliver
from tests.parametric.test_ffe.utils import assert_dependent_flag_capability
from utils import features, pytest, scenarios
from utils.dd_constants import Capabilities, RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI, ParametricTestClientApi

DEPENDENT_FLAG_MASK = 1 << Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1
FLAG_CONFIGURATION_MASK = 1 << Capabilities.FFE_FLAG_CONFIGURATION_RULES


def _request(mask: int, *, byte_array: bool) -> dict[str, Any]:
    raw = mask.to_bytes(7, byteorder="big")
    return {
        "body": {
            "client": {"id": "ffe-client", "capabilities": list(raw) if byte_array else base64.b64encode(raw).decode()}
        }
    }


@scenarios.test_the_test
@features.not_reported
class Test_FFE_RC_Capability_Assertion:
    @pytest.mark.parametrize("byte_array", [False, True])
    def test_supported_and_legacy(self, *, byte_array: bool) -> None:
        assert_dependent_flag_capability(
            [_request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=byte_array)], supported=True
        )
        assert_dependent_flag_capability([_request(FLAG_CONFIGURATION_MASK, byte_array=byte_array)], supported=False)

    @pytest.mark.parametrize("byte_array", [False, True])
    def test_missing_bit_fails_even_if_later_poll_recovers(self, *, byte_array: bool) -> None:
        requests = [
            _request(FLAG_CONFIGURATION_MASK, byte_array=byte_array),
            _request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=byte_array),
        ]
        with pytest.raises(AssertionError, match=f"bit {Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1}=True"):
            assert_dependent_flag_capability(requests, supported=True)

    def test_false_advertisement_fails(self) -> None:
        with pytest.raises(AssertionError, match=f"bit {Capabilities.FFE_FLAG_DEPENDENT_FLAG_VARIANT_KEY_V1}=False"):
            assert_dependent_flag_capability([_request(DEPENDENT_FLAG_MASK, byte_array=False)], supported=False)

    def test_no_traffic_is_not_a_pass(self) -> None:
        with pytest.raises(AssertionError, match="No FFE_FLAGS RC requests"):
            assert_dependent_flag_capability([], supported=False)


RC_PATH = "datadog/2/FFE_FLAGS/flags/config"


def _poll(*, content: str = "", acknowledged: bool = False, product: str = "FFE_FLAGS") -> dict[str, Any]:
    request = _request(FLAG_CONFIGURATION_MASK | DEPENDENT_FLAG_MASK, byte_array=False)
    request["method"] = "GET"
    request["body"]["client"].update(
        products=["FFE_FLAGS"],
        state={
            "config_states": [
                {
                    "id": "flags",
                    "product": product,
                    "apply_state": (
                        RemoteConfigApplyState.ACKNOWLEDGED.value
                        if acknowledged
                        else RemoteConfigApplyState.UNACKNOWLEDGED.value
                    ),
                }
            ]
        },
    )
    request["body"]["cached_target_files"] = (
        [{"path": RC_PATH, "hashes": [{"algorithm": "sha256", "hash": content}]}] if content else []
    )
    return request


@scenarios.test_the_test
@features.not_reported
class Test_FFE_RC_Delivery:
    def test_get_and_post_polls_keep_product_filter(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        get = _poll()
        post = _poll()
        post["method"] = "POST"
        unrelated = _poll()
        unrelated["body"]["client"]["products"] = ["APM_TRACING"]
        agent.rc_requests.side_effect = lambda *, post_only=False: ([post] if post_only else [get, unrelated, post])
        assert ffe_requests(agent) == [get, post]

    def test_update_requires_new_content_and_ack_in_same_poll(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        old = _poll(content="old", acknowledged=True)
        new_without_ack = _poll(content="new")
        wrong_product = _poll(content="new", acknowledged=True, product="APM_TRACING")
        new_ack = _poll(content="new", acknowledged=True)
        agent.rc_requests.side_effect = [
            [old],
            [old, old],
            [old, old, new_without_ack],
            [old, old, new_without_ack, wrong_product],
            [old, old, new_without_ack, wrong_product, new_ack],
        ]
        with patch("tests.parametric.test_ffe.dependent_flags_rc.time.sleep"):
            deliver(agent, config_id="flags", payload={"flags": {}})
        assert agent.rc_requests.call_count == 5
        agent.clear.assert_not_called()

    def test_stale_ack_times_out(self) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        old = _poll(content="old", acknowledged=True)
        agent.rc_requests.side_effect = [[old], [old, old]]
        with (
            patch("tests.parametric.test_ffe.dependent_flags_rc.time.monotonic", side_effect=[0, 0, 11]),
            patch("tests.parametric.test_ffe.dependent_flags_rc.time.sleep"),
            pytest.raises(AssertionError, match="did not acknowledge new configuration content"),
        ):
            deliver(agent, config_id="flags", payload={"flags": {}})

    @pytest.mark.parametrize("blocking", [True, False])
    @pytest.mark.parametrize("supported", [True, False])
    def test_cold_start_delivers_before_requiring_readiness(self, *, blocking: bool, supported: bool) -> None:
        agent = MagicMock(spec=TestAgentAPI)
        library = MagicMock(spec=ParametricTestClientApi)
        starting = Event()
        delivered = Event()
        observed: list[dict[str, Any]] = []

        def start() -> bool:
            starting.set()
            if blocking:
                assert delivered.wait(timeout=5), "Startup blocked waiting for configuration"
            return delivered.is_set()

        def polls() -> list[dict[str, Any]]:
            assert starting.wait(timeout=5), "Provider startup was never triggered"
            poll = _poll(content="new" if delivered.is_set() else "", acknowledged=delivered.is_set())
            poll["body"]["client"]["capabilities"] = _request(
                FLAG_CONFIGURATION_MASK | (DEPENDENT_FLAG_MASK if supported else 0), byte_array=False
            )["body"]["client"]["capabilities"]
            observed.append(poll)
            return list(observed)

        def configure(*, path: str, payload: dict[str, Any]) -> None:
            assert path == RC_PATH
            assert payload == {"flags": {}}
            assert len(observed) >= 3, "Configuration delivered before observing capabilities"
            delivered.set()

        library.ffe_start.side_effect = start
        agent.rc_requests.side_effect = polls
        agent.set_remote_config.side_effect = configure
        start_and_deliver(agent, library, config_id="flags", payload={"flags": {}}, supported=supported)
        assert delivered.is_set()
        assert library.ffe_start.call_count == (1 if blocking else 2)
        agent.clear.assert_not_called()

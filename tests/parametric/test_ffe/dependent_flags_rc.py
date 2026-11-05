"""Capability-gated RC delivery, including cold provider startup and content updates."""

from concurrent.futures import ThreadPoolExecutor
import time
from typing import Any

from tests.parametric.test_ffe.utils import assert_dependent_flag_capability
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import ParametricTestClientApi, TestAgentAPI

RC_PRODUCT = "FFE_FLAGS"


def ffe_requests(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    return [
        request for request in test_agent.rc_requests() if RC_PRODUCT in request["body"]["client"].get("products", [])
    ]


def observe_polls(test_agent: TestAgentAPI, *, supported: bool, minimum: int = 3) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        requests = ffe_requests(test_agent)
        if requests:
            assert_dependent_flag_capability(requests, supported=supported)
        if len(requests) >= minimum:
            return
        time.sleep(0.1)
    raise AssertionError(f"Expected at least {minimum} FFE_FLAGS RC polls, got {len(requests)}")


def deliver(test_agent: TestAgentAPI, *, config_id: str, payload: dict[str, Any]) -> None:
    path = f"datadog/2/{RC_PRODUCT}/{config_id}/config"
    previous_requests = test_agent.rc_requests()
    previous_target = next(
        (
            target
            for request in reversed(previous_requests)
            for target in request["body"].get("cached_target_files", [])
            if target["path"] == path
        ),
        None,
    )
    test_agent.set_remote_config(path=path, payload=payload)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        # A stale ACK for the same ID must not acknowledge new content. Keep all
        # requests for capability checks, but require a new target and ACK together.
        for request in test_agent.rc_requests()[len(previous_requests) :]:
            body = request["body"]
            changed = any(
                target["path"] == path and target != previous_target for target in body.get("cached_target_files", [])
            )
            acknowledged = any(
                state["product"] == RC_PRODUCT
                and state["id"] == config_id
                and state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
                for state in body["client"]["state"].get("config_states", [])
            )
            if changed and acknowledged:
                return
        time.sleep(0.05)
    raise AssertionError(f"The SDK did not acknowledge new configuration content for {config_id}")


def start_and_deliver(
    test_agent: TestAgentAPI,
    test_library: ParametricTestClientApi,
    *,
    config_id: str,
    payload: dict[str, Any],
    supported: bool,
) -> None:
    # .NET waits for configuration inside /ffe/start; Java can return not-ready
    # before delivery. Trigger startup without requiring readiness until after RC.
    with ThreadPoolExecutor(max_workers=1) as executor:
        started = executor.submit(test_library.ffe_start)
        observe_polls(test_agent, supported=supported)
        deliver(test_agent, config_id=config_id, payload=payload)
        if started.result(timeout=10):
            return
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if test_library.ffe_start():
                return
            time.sleep(0.1)
        raise AssertionError("Failed to initialize the provider after RC delivery")

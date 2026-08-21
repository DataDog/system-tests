"""Route-neutral Feature Flags exposure expectations."""

from collections.abc import Iterable
import json

from utils._weblog import HttpResponse
from utils.interfaces._core import ProxyBasedInterfaceValidator

EXPOSURES_PATH = "/api/v2/exposures"
EXPOSURE_WAIT_TIMEOUT_SECONDS = 30
EXPOSURE_CACHE_SETTLE_SECONDS = 3


def exposure_events_from_data(
    data: dict, flag_keys: set[str] | None = None, subject_id: str | None = None
) -> list[dict]:
    """Return matching exposure events from one captured request."""
    if data.get("path") != EXPOSURES_PATH:
        return []

    exposure_data = data.get("request", {}).get("content")
    if not isinstance(exposure_data, dict):
        return []

    exposures = exposure_data.get("exposures")
    if not isinstance(exposures, list):
        return []

    events = []
    for event in exposures:
        if not isinstance(event, dict):
            continue

        flag = event.get("flag")
        subject = event.get("subject")
        event_flag_key = flag.get("key") if isinstance(flag, dict) else None
        event_subject_id = subject.get("id") if isinstance(subject, dict) else None

        if flag_keys is not None and event_flag_key not in flag_keys:
            continue
        if subject_id is not None and event_subject_id != subject_id:
            continue
        events.append(event)
    return events


def wait_for_exposure_event(
    interface: ProxyBasedInterfaceValidator,
    *,
    flag_key: str,
    targeting_key: str,
) -> None:
    """Wait until the capture interface receives the expected exposure."""

    def matches_exposure(data: dict) -> bool:
        return bool(exposure_events_from_data(data, {flag_key}, targeting_key))

    assert interface.wait_for(
        matches_exposure,
        timeout=EXPOSURE_WAIT_TIMEOUT_SECONDS,
    ), f"Timed out waiting for exposure event for {flag_key!r} and {targeting_key!r}"


def assert_exposure_side_effects_contract(
    interface: ProxyBasedInterfaceValidator,
    responses: Iterable[HttpResponse],
    *,
    flag_key: str,
    targeting_key: str,
    expected_value: str,
    expected_variant: str,
    expected_allocation: str = "default-allocation",
) -> list[dict]:
    """Assert one exposure contract through Agent, sidecar, or direct intake capture."""
    for index, response in enumerate(responses, start=1):
        assert response.status_code == 200, f"Evaluation {index} failed: {response.text}"
        value = json.loads(response.text)["value"]
        assert value == expected_value, f"Evaluation {index} returned {value!r}"

    wait_for_exposure_event(interface, flag_key=flag_key, targeting_key=targeting_key)

    def matches_exposure(data: dict) -> bool:
        return bool(exposure_events_from_data(data, {flag_key}, targeting_key))

    if not interface.replay:
        interface.wait(EXPOSURE_CACHE_SETTLE_SECONDS)

    matching_requests = [data for data in interface.get_data() if matches_exposure(data)]
    events = [
        event
        for request in matching_requests
        for event in exposure_events_from_data(request, {flag_key}, targeting_key)
    ]
    assert len(events) == 1, f"The exposure cache produced {len(events)} matching events instead of one"

    for request in matching_requests:
        context = request["request"]["content"]["context"]
        assert context["service"] == "weblog"
        assert context["version"] == "1.0.0"
        assert context["env"] == "system-tests"

    event = events[0]
    assert event["flag"]["key"] == flag_key
    assert event["variant"]["key"] == expected_variant
    assert event["allocation"]["key"] == expected_allocation
    assert event["subject"]["id"] == targeting_key
    return matching_requests

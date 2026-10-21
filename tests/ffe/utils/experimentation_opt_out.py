"""Fixtures and exposure assertions for experimentation opt-out system tests."""

from collections import Counter
from collections.abc import Iterable
from typing import Any

from tests.ffe.utils.exposures import exposure_events_from_data
from tests.ffe.utils.fixtures import make_ufc_fixture


Exposure = tuple[str, str, str, str]  # flag, subject, allocation, variant


def opt_out_fixture(
    flag: str,
    activation: str | None = "2026-01-01T00:00:00Z",
    *,
    include_activation: bool = True,
    experiment: bool = True,
    fallback: bool = True,
) -> dict[str, Any]:
    fixture = make_ufc_fixture(flag, allocation_key="experiment", serial_id=101)
    allocation = fixture["flags"][flag]["allocations"][0]
    allocation["doLog"] = experiment
    if include_activation:
        allocation["randomizationActivatedAt"] = activation
    if fallback:
        ordinary = make_ufc_fixture(flag, "off", allocation_key="ordinary", serial_id=102)
        ordinary["flags"][flag]["allocations"][0]["doLog"] = False
        fixture["flags"][flag]["allocations"].extend(ordinary["flags"][flag]["allocations"])
    return fixture


def assert_exposures(captures: Iterable[dict[str, Any]], *, flags: set[str], expected: set[Exposure]) -> None:
    """Require the complete exposure set, including positive controls and deduplication."""
    events = [event for data in captures for event in exposure_events_from_data(data, flags)]
    actual = Counter(
        (event["flag"]["key"], event["subject"]["id"], event["allocation"]["key"], event["variant"]["key"])
        for event in events
    )
    assert actual == Counter(expected), f"Expected exposures {Counter(expected)}, got {actual}"

from datetime import datetime, timedelta, UTC
from typing import Any

import pytest

from tests._telemetry_heartbeat import heartbeat_delays_by_runtime


pytestmark = pytest.mark.scenario("TEST_THE_TEST")

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def _heartbeat(runtime_id: str, seq_id: int, offset: float) -> dict[str, Any]:
    timestamp = BASE_TIME + timedelta(seconds=offset)
    return {
        "request": {
            "timestamp_start": timestamp.isoformat(),
            "content": {
                "request_type": "app-heartbeat",
                "runtime_id": runtime_id,
                "seq_id": seq_id,
            },
        },
        "log_filename": f"{runtime_id}-{seq_id}-{offset}.json",
    }


def test_fork_duplicate_does_not_affect_parent_cadence() -> None:
    messages = [
        _heartbeat("parent", 1, 0),
        _heartbeat("parent", 2, 2),
        _heartbeat("parent", 2, 2.05),
        _heartbeat("parent", 3, 4),
        _heartbeat("parent", 4, 6),
        _heartbeat("child", 1, 2.1),
        _heartbeat("child", 2, 4.1),
    ]
    delays, heartbeat_counts = heartbeat_delays_by_runtime(messages)

    assert heartbeat_counts == {"parent": 4, "child": 2}
    assert set(delays) == {"parent"}
    assert delays["parent"] == pytest.approx([2.0, 2.0, 2.0])


def test_distinct_fast_heartbeats_remain_measurable() -> None:
    messages = [
        _heartbeat("parent", 1, 0),
        _heartbeat("parent", 2, 1),
        _heartbeat("parent", 3, 2),
        _heartbeat("parent", 4, 3),
    ]
    delays, heartbeat_counts = heartbeat_delays_by_runtime(messages)

    assert heartbeat_counts == {"parent": 4}
    assert delays["parent"] == pytest.approx([1.0, 1.0, 1.0])

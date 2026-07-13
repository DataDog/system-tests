import itertools
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from dateutil.parser import isoparse


def heartbeat_delays_by_runtime(
    telemetry_data: Iterable[dict[str, Any]],
) -> tuple[dict[str, list[float]], dict[str, int]]:
    """Return heartbeat delays and logical heartbeat counts grouped by runtime ID."""
    heartbeats_by_runtime: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)

    for data in telemetry_data:
        content: dict[str, Any] = data["request"]["content"]
        if content.get("request_type") != "app-heartbeat":
            continue

        runtime_id: str = content["runtime_id"]
        seq_id: int = content["seq_id"]

        # A retry or a fork clone can send the same logical heartbeat more than once.
        # It must contribute only once to the runtime's observed cadence.
        heartbeats_by_runtime[runtime_id].setdefault(seq_id, data)

    heartbeat_counts = {runtime_id: len(heartbeats) for runtime_id, heartbeats in heartbeats_by_runtime.items()}
    delays_by_runtime: dict[str, list[float]] = {}

    for runtime_id, heartbeats_by_seq_id in heartbeats_by_runtime.items():
        if len(heartbeats_by_seq_id) <= 2:
            continue

        heartbeats = sorted(
            heartbeats_by_seq_id.values(),
            key=lambda data: isoparse(data["request"]["timestamp_start"]),
        )
        times = [isoparse(data["request"]["timestamp_start"]) for data in heartbeats]
        delays_by_runtime[runtime_id] = [
            (current - previous).total_seconds() for previous, current in itertools.pairwise(times)
        ]

    return delays_by_runtime, heartbeat_counts

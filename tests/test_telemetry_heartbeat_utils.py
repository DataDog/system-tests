import itertools
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from dateutil.parser import isoparse


def heartbeat_delays_by_runtime(
    telemetry_data: Iterable[dict[str, Any]],
    *,
    min_lifespan: float = 0.0,
) -> tuple[dict[str, list[float]], dict[str, int]]:
    """Return heartbeat delays and heartbeat counts, grouped by runtime ID.

    Expects unflattened telemetry data (`get_telemetry_data(flatten_message_batches=False)`):
    a flattened message-batch entry inherits the outer batch's seq_id, so heartbeats packed
    in the same batch would otherwise collide on (runtime_id, seq_id) alone and get deduped
    into one.

    `min_lifespan` drops runtimes whose heartbeats span less time than that (e.g. a forked
    child that exits after only 2-3 heartbeats). With so few samples, a real (non-duplicate)
    heartbeat sent during shutdown can dominate the average delay -- dropping the runtime is
    the only way to avoid measuring it. A long-lived runtime with the same anomaly is still
    measured, and can still fail.
    """
    heartbeats_by_runtime: dict[str, dict[tuple[int, int], dict[str, Any]]] = defaultdict(dict)

    for data in telemetry_data:
        content: dict[str, Any] = data["request"]["content"]
        runtime_id: str = content.get("runtime_id", "")
        seq_id: int = content.get("seq_id", 0)

        if content.get("request_type") == "message-batch":
            entries = list(enumerate(content.get("payload", [])))
        else:
            entries = [(0, content)]

        for batch_index, entry in entries:
            if entry.get("request_type") != "app-heartbeat":
                continue

            # Dedup key (seq_id, batch_index) catches two cases: a real retry (identical
            # resend), and a forked child's clone heartbeat. A child briefly shares its
            # parent's runtime_id and copies its seq_id counter at fork time, so it can
            # independently emit a heartbeat with the same seq_id. Not a guaranteed
            # invariant, but the best signal we have to tell "fork clone" apart from
            # "genuinely fast heartbeat" without tracking PIDs.
            heartbeats_by_runtime[runtime_id].setdefault((seq_id, batch_index), data)

    heartbeat_counts = {runtime_id: len(heartbeats) for runtime_id, heartbeats in heartbeats_by_runtime.items()}
    delays_by_runtime: dict[str, list[float]] = {}

    for runtime_id, heartbeats_by_key in heartbeats_by_runtime.items():
        if len(heartbeats_by_key) <= 2:
            continue

        heartbeats = sorted(
            heartbeats_by_key.values(),
            key=lambda data: isoparse(data["request"]["timestamp_start"]),
        )
        times = [isoparse(data["request"]["timestamp_start"]) for data in heartbeats]
        lifespan = (times[-1] - times[0]).total_seconds()
        if lifespan < min_lifespan:
            continue

        delays_by_runtime[runtime_id] = [
            (current - previous).total_seconds() for previous, current in itertools.pairwise(times)
        ]

    return delays_by_runtime, heartbeat_counts

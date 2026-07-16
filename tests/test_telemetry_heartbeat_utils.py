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
    """Return heartbeat delays and logical heartbeat counts grouped by runtime ID.

    Expects unflattened telemetry data (`get_telemetry_data(flatten_message_batches=False)`)
    so that heartbeats packed inside a message-batch keep their position in the batch: a
    flattened message-batch entry inherits the outer batch's seq_id, so two distinct
    heartbeats sent in the same batch would otherwise collide on (runtime_id, seq_id) alone.

    `min_lifespan` excludes runtimes whose heartbeats span less than that many seconds
    (e.g. `telemetry_heartbeat_interval * 3`). A process that lived only a fraction of the
    heartbeat interval before exiting (e.g. a forked child spawned by the session-id tests)
    doesn't provide a reliable cadence sample: some tracers emit an extra, out-of-cadence
    heartbeat as part of their shutdown flush, and with only 2-3 total samples that single
    anomalous gap dominates the average delay. This is a real, distinct message (its own
    seq_id, not a retry/clone) so deduping can't catch it -- only requiring enough elapsed
    time to average it out can. A long-lived runtime with the same anomaly is still measured
    and can still fail: this only excludes runtimes too short-lived to measure at all.
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

            # A retry resends the same message unchanged (same seq_id, same position in its
            # batch, if any) and must contribute only once to the runtime's observed cadence.
            #
            # A forked child briefly shares its parent's runtime_id (until it regenerates its
            # own, per the Stable Service Instance Identifier RFC) but keeps its own seq_id
            # counter, copied from the parent's in-memory state at fork time. Since that
            # counter isn't coordinated across the fork boundary, parent and child can
            # independently emit a heartbeat with the same seq_id from that shared starting
            # value. Deduping on (seq_id, batch_index) catches this the same way it catches a
            # real retry -- it's a coincidence of the copied counter state, not a guaranteed
            # invariant, but it's what lets us tell "fork clone" apart from "genuinely fast
            # heartbeat" without tracking PIDs.
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

from ddsketch import DDSketch
from ddsketch.pb.proto import DDSketchProto
from utils.interfaces._core import BaseValidation

from typing import Dict, List, TypedDict


class AggrMetrics(TypedDict):
    name: str
    resource: str
    type: str
    synthetics: bool
    hits: int
    top_level_hits: int
    duration: int
    errors: int
    ok_summary: DDSketch
    error_summary: DDSketch


class StatsBucket(TypedDict):
    start: int
    duration: int
    stats: List[AggrMetrics]


def _deserialize_stats_payload_v06(raw_data: List) -> List[StatsBucket]:
    """Decode the protobuf stats payloads from the deserialized msgpack."""
    stats_buckets: List[StatsBucket] = []
    for raw_bucket in raw_data:
        stats: List[AggrMetrics] = []
        for raw_stats in raw_bucket["Stats"]:
            stat = AggrMetrics(
                name=raw_stats["Name"],
                resource=raw_stats["Resource"],
                type=raw_stats["Type"],
                synthetics=raw_stats["Synthetics"],
                hits=raw_stats["Hits"],
                top_level_hits=raw_stats["TopLevelHits"],
                duration=raw_stats["Duration"],
                errors=raw_stats["Errors"],
                ok_summary=DDSketchProto.from_proto(raw_stats["OkSummary"]),
                error_summary=DDSketchProto.from_proto(raw_stats["ErrorSummary"]),
            )
            stats.append(stat)

        bucket = StatsBucket(start=raw_bucket["Start"], duration=raw_bucket["Duration"], stats=stats,)
        stats_buckets.append(bucket)
    return stats_buckets


class _TraceStatsV06Valid(BaseValidation):
    """Validate trace stats requests from trace clients."""

    is_success_on_expiry = False
    path_filters = ["/v0.6/stats", "/v0.4/traces"]

    def __init__(self, num_traces):
        super().__init__()
        self.num_traces = num_traces
        self.traces = []
        self.stats = []
        # Stats are flushed by default every 10 seconds
        # Give a bit of additional wiggle room
        self.expected_timeout = 12

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            self.traces.extend(data["request"]["content"])
            if "Datadog-Client-Computed-Stats" not in data["request"]["headers"]:
                self.set_failure(
                    f"Datadog-Client-Computed-Stats header is missing on /v0.4/traces request number {data['log_filename']}"
                )
        elif data["path"] == "/v0.6/stats":
            self.stats.append(data["request"]["content"])
        self.log_info(self.traces)

    def final_check(self):
        if len(self.traces) != self.num_traces:
            self.set_failure(f"Expected {self.num_traces} traces, received {len(self.traces)}")

        self.set_status(True)

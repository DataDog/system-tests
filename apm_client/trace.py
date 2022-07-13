"""
Tracing constants, data structures and helper methods.
"""
from typing import List
from typing import Optional
from typing import TypedDict

from ddsketch.ddsketch import BaseDDSketch
from ddsketch.store import CollapsingLowestDenseStore
from ddsketch.pb.ddsketch_pb2 import DDSketch as DDSketchPb
from ddsketch.pb.ddsketch_pb2 import Store as StorePb
from ddsketch.pb.proto import KeyMappingProto
import msgpack


"""
Key used in the metrics map to toggle measuring a span.
"""
SPAN_MEASURED_KEY = "_dd.measured"


# Note that class attributes are golang style to match the payload.
class V06StatsAggr(TypedDict):
    """Stats aggregation data structure used in the v0.6/stats protocol."""

    Name: str
    Resource: str
    Type: str
    Service: str
    HTTPStatusCode: int
    Synthetics: bool
    Hits: int
    TopLevelHits: int
    Duration: int
    Errors: int
    OkSummary: BaseDDSketch
    ErrorSummary: BaseDDSketch


class V06StatsBucket(TypedDict):
    Start: int
    Duration: int
    Stats: List[V06StatsAggr]


class V06StatsPayload(TypedDict):
    Hostname: Optional[str]
    Env: Optional[str]
    Version: Optional[str]
    Stats: List[V06StatsBucket]


def _v06_store_from_proto(proto: StorePb) -> CollapsingLowestDenseStore:
    """Trace stats sketches use CollapsingLowestDenseStore for the store implementation.

    A bin limit of 2048 is used.
    """
    store = CollapsingLowestDenseStore(2048)
    index = proto.contiguousBinIndexOffset
    store.offset = index
    for count in proto.contiguousBinCounts:
        store.add(index, count)
        index += 1
    return store


def _v06_sketch_from_proto(proto: DDSketchPb) -> BaseDDSketch:
    mapping = KeyMappingProto.from_proto(proto.mapping)
    store = _v06_store_from_proto(proto.positiveValues)
    negative_store = _v06_store_from_proto(proto.negativeValues)
    return BaseDDSketch(
        mapping=mapping,
        store=store,
        negative_store=negative_store,
        zero_count=proto.zeroCount,
    )


def decode_v06_stats(data: bytes) -> V06StatsPayload:
    payload = msgpack.unpackb(data)
    stats_buckets: List[V06StatsBucket] = []
    for raw_bucket in payload["Stats"]:
        stats: List[V06StatsAggr] = []
        for raw_stats in raw_bucket["Stats"]:
            ok_summary = DDSketchPb()
            ok_summary.ParseFromString(raw_stats["OkSummary"])
            err_summary = DDSketchPb()
            err_summary.ParseFromString(raw_stats["ErrorSummary"])
            stat = V06StatsAggr(
                Name=raw_stats["Name"],
                Resource=raw_stats["Resource"],
                Service=raw_stats["Service"],
                Type=raw_stats.get("Type"),
                HTTPStatusCode=raw_stats.get("HTTPStatusCode"),
                Synthetics=raw_stats["Synthetics"],
                Hits=raw_stats["Hits"],
                TopLevelHits=raw_stats["TopLevelHits"],
                Duration=raw_stats["Duration"],
                Errors=raw_stats["Errors"],
                OkSummary=_v06_sketch_from_proto(ok_summary),
                ErrorSummary=_v06_sketch_from_proto(err_summary),
            )
            stats.append(stat)

        bucket = V06StatsBucket(
            Start=raw_bucket["Start"],
            Duration=raw_bucket["Duration"],
            Stats=stats,
        )
        stats_buckets.append(bucket)

    return V06StatsPayload(
        Hostname=payload.get("Hostname"),
        Env=payload.get("Env"),
        Version=payload.get("Version"),
        Stats=stats_buckets,
    )

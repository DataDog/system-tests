from typing import List
from typing import Optional
from typing import TypedDict

from google.protobuf.json_format import MessageToDict

from ddsketch import DDSketch
from ddsketch.pb.ddsketch_pb2 import DDSketch as DDSketchProto
import msgpack


# Note that class attributes are golang style to match the payload.
class V06StatsAggr(TypedDict):
    Name: str
    Resource: str
    Type: Optional[str]
    HTTPStatusCode: int
    Synthetics: bool
    Hits: int
    TopLevelHits: int
    Duration: int
    Errors: int
    OkSummary: DDSketch
    ErrorSummary: DDSketch


class V06StatsBucket(TypedDict):
    Start: int
    Duration: int
    Stats: List[V06StatsAggr]


class V06StatsPayload(TypedDict):
    Hostname: Optional[str]
    Env: Optional[str]
    Version: Optional[str]
    Stats: List[V06StatsBucket]


def decode_v06_stats(data: bytes) -> V06StatsPayload:
    payload = msgpack.unpackb(data)
    stats_buckets: List[V06StatsBucket] = []
    for raw_bucket in payload["Stats"]:
        stats: List[V06StatsAggr] = []
        for raw_stats in raw_bucket["Stats"]:
            ok_summary = DDSketchProto()
            ok_summary.ParseFromString(raw_stats["OkSummary"])
            err_summary = DDSketchProto()
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
                OkSummary=MessageToDict(ok_summary),
                ErrorSummary=MessageToDict(err_summary),
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

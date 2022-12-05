"""
Tracing constants, data structures and helper methods.

These are used to specify, test and work with trace data and protocols.
"""
import math
from typing import List
from typing import Optional
from typing import TypedDict

from ddapm_test_agent.trace import Span
from ddapm_test_agent.trace import Trace
from ddapm_test_agent.trace import root_span
import msgpack

from ddsketch.ddsketch import BaseDDSketch
from ddsketch.store import CollapsingLowestDenseStore
from ddsketch.pb.ddsketch_pb2 import DDSketch as DDSketchPb
from ddsketch.pb.ddsketch_pb2 import Store as StorePb
from ddsketch.pb.proto import KeyMappingProto

"""Key used in the meta map to indicate the span origin"""
ORIGIN = "_dd.origin"

"""Key used in the metrics map to indicate tracer sampling priority"""
SAMPLING_PRIORITY_KEY = "_sampling_priority_v1"

"""Value used in the metrics map to indicate tracer sampling priority as user keep"""
USER_KEEP = 2


"""
Key used in metrics to set manual drop decision.
"""
MANUAL_DROP_KEY = "manual.drop"

"""
Key used in metrics to set manual keep decision.
"""
MANUAL_KEEP_KEY = "manual.keep"

"""
Key used in metrics to set automatic tracer keep decision.
"""
AUTO_KEEP_KEY = "auto.keep"

"""
Key used in metrics to set automatic tracer drop decision.
"""
AUTO_DROP_KEY = "auto.drop"

"""
Key used in the metrics map to toggle measuring a span.
"""
SPAN_MEASURED_KEY = "_dd.measured"

"""
Key used in the metrics to map to single span sampling.
"""
SINGLE_SPAN_SAMPLING_MECHANISM = "_dd.span_sampling.mechanism"

"""
Value used in the metrics to map to single span sampling decision.
"""
SINGLE_SPAN_SAMPLING_MECHANISM_VALUE = 8

"""Key used in the metrics to map to single span sampling sample rate."""
SINGLE_SPAN_SAMPLING_RATE = "_dd.span_sampling.rule_rate"

"""Key used in the metrics to map to single span sampling max per second."""
SINGLE_SPAN_SAMPLING_MAX_PER_SEC = "_dd.span_sampling.max_per_second"

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
    # import pdb; pdb.set_trace()
    mapping = KeyMappingProto.from_proto(proto.mapping)
    store = _v06_store_from_proto(proto.positiveValues)
    negative_store = _v06_store_from_proto(proto.negativeValues)
    return BaseDDSketch(mapping=mapping, store=store, negative_store=negative_store, zero_count=proto.zeroCount,)


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
                OkSummary=_v06_sketch_from_proto(ok_summary) if ok_summary.mapping.gamma > 1 else None,
                ErrorSummary=_v06_sketch_from_proto(err_summary) if err_summary.mapping.gamma > 1 else None,
            )
            # FIXME: the go implementation sends uninitialized sketches for some reason
            if ok_summary.mapping.gamma > 1:
                stats.append(stat)

        bucket = V06StatsBucket(Start=raw_bucket["Start"], Duration=raw_bucket["Duration"], Stats=stats,)
        stats_buckets.append(bucket)

    return V06StatsPayload(
        Hostname=payload.get("Hostname"), Env=payload.get("Env"), Version=payload.get("Version"), Stats=stats_buckets,
    )


def _span_similarity(s1: Span, s2: Span) -> int:
    """Return a similarity rating for the two given spans."""
    score = 0

    for key in set(s1.keys() & s2.keys()):
        if s1[key] == s2[key]:
            score += 1

    s1_meta = s1.get("meta", {})
    s2_meta = s2.get("meta", {})
    for key in set(s1_meta.keys()) & set(s2_meta.keys()):
        if s1_meta[key] == s2_meta[key]:
            score += 1

    s1_metrics = s1.get("metrics", {})
    s2_metrics = s2.get("metrics", {})
    for key in set(s1_metrics.keys()) & set(s2_metrics.keys()):
        if s1_metrics[key] == s2_metrics[key]:
            score += 1
    return score


def find_trace_by_root(traces: List[Trace], span: Span) -> Trace:
    """Return the trace from `traces` with root span most similar to `span`."""
    assert len(traces) > 0

    max_similarity = -math.inf
    max_score_trace = traces[0]
    for trace in traces:
        root = root_span(trace)
        similarity = _span_similarity(root, span)
        if similarity > max_similarity:
            max_score_trace = trace
            max_similarity = similarity
    return max_score_trace


def find_span(trace: Trace, span: Span) -> Span:
    """Return a span from the trace which most closely matches `span`."""
    assert len(trace) > 0

    max_similarity = -math.inf
    max_similarity_span = trace[0]
    for other_span in trace:
        similarity = _span_similarity(span, other_span)
        if similarity > max_similarity:
            max_similarity = similarity
            max_similarity_span = other_span
    return max_similarity_span


def find_span_in_traces(traces: List[Trace], span: Span) -> Span:
    """Return a span from the traces which most closely matches `span`."""
    assert len(traces) > 0

    max_similarity = -math.inf
    max_similarity_span = None
    for trace in traces:
        similar_span = find_span(trace, span)
        if max_similarity_span is None:
            max_similarity_span = similar_span
        similarity = _span_similarity(span, max_similarity_span)
        if similarity > max_similarity:
            max_similarity_span = similar_span
            max_similarity = similarity
    return max_similarity_span


def span_has_no_parent(span: Span) -> bool:
    """Return if a span has a parent by checking the presence and value of the `parent_id`."""
    return "parent_id" not in span or span.get("parent_id") == 0 or span.get("parent_id") is None

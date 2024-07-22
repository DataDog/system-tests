"""
Tracing constants, data structures and helper methods.

These are used to specify, test and work with trace data and protocols.
"""
import json
from typing import Dict
from typing import List
from typing import Optional
from typing import TypedDict
from typing import Union

from ddapm_test_agent.trace import Span
from ddapm_test_agent.trace import Trace
from ddapm_test_agent.trace import root_span  # pylint: disable=unused-import
import msgpack

from ddsketch.ddsketch import BaseDDSketch
from ddsketch.store import CollapsingLowestDenseStore
from ddsketch.pb.ddsketch_pb2 import DDSketch as DDSketchPb
from ddsketch.pb.ddsketch_pb2 import Store as StorePb
from ddsketch.pb.proto import KeyMappingProto
from utils.parametric.spec.tracecontext import TRACECONTEXT_FLAGS_SET


# Key used in the meta map to indicate the span origin
ORIGIN = "_dd.origin"

# Key used in the metrics map to indicate tracer sampling priority
SAMPLING_PRIORITY_KEY = "_sampling_priority_v1"

# Value used in the metrics map to indicate tracer sampling priority as user keep
USER_KEEP = 2

# Key used in metrics to set manual drop decision.
MANUAL_DROP_KEY = "manual.drop"

# Key used in metrics to set manual keep decision.
MANUAL_KEEP_KEY = "manual.keep"

#  Key used in metrics to set automatic tracer keep decision.
AUTO_KEEP_KEY = "auto.keep"

# Key used in metrics to set automatic tracer drop decision.
AUTO_DROP_KEY = "auto.drop"

# Key used in the metrics map to toggle measuring a span.
SPAN_MEASURED_KEY = "_dd.measured"

# Key used in the metrics to map to single span sampling.
SINGLE_SPAN_SAMPLING_MECHANISM = "_dd.span_sampling.mechanism"

# Value used in the metrics to map to single span sampling decision.
SINGLE_SPAN_SAMPLING_MECHANISM_VALUE = 8

# Key used in the metrics to map to single span sampling sample rate.
SINGLE_SPAN_SAMPLING_RATE = "_dd.span_sampling.rule_rate"

# Key used in the metrics to map to single span sampling max per second.
SINGLE_SPAN_SAMPLING_MAX_PER_SEC = "_dd.span_sampling.max_per_second"

SAMPLING_DECISION_MAKER_KEY = "_dd.p.dm"
SAMPLING_AGENT_PRIORITY_RATE = "_dd.agent_psr"
SAMPLING_RULE_PRIORITY_RATE = "_dd.rule_psr"
SAMPLING_LIMIT_PRIORITY_RATE = "_dd.limit_psr"

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


def find_trace(traces: List[Trace], trace_id: int) -> Optional[Trace]:
    """Return the trace from `traces` with root span matching all fields of `span`."""
    trace_id = trace_id & (2 ^ 64 - 1)  # Use 64-bit trace id
    for trace in traces:
        # This check ignroes the high bits of the trace id
        # TODO: Check _dd.p.tid
        if trace and trace[0].get("trace_id") == trace_id:
            return trace


def find_span(trace: Trace, span_id: int) -> Optional[Span]:
    """Return a span from the trace matches all fields in `span`."""
    assert len(trace) > 0
    for span in trace:
        if span.get("span_id") == span_id:
            return span


def span_has_no_parent(span: Span) -> bool:
    """Return if a span has a parent by checking the presence and value of the `parent_id`."""
    return "parent_id" not in span or span.get("parent_id") == 0 or span.get("parent_id") is None


def assert_span_has_tags(span: Span, tags: Dict[str, Union[int, str, float, bool]]):
    """Assert that the span has the given tags."""
    for key, value in tags.items():
        assert key in span.get("meta", {}), f"Span missing expected tag {key}={value}"
        assert span.get("meta", {}).get(key) == value, f"Span incorrect tag value for {key}={value}"


def assert_trace_has_tags(trace: Trace, tags: Dict[str, Union[int, str, float, bool]]):
    """Assert that the trace has the given tags."""
    for span in trace:
        assert_span_has_tags(span, tags)


def retrieve_span_links(span):
    if span.get("span_links") is not None:
        return span["span_links"]

    if span["meta"].get("_dd.span_links") is not None:
        # Convert span_links tags into msgpack v0.4 format
        json_links = json.loads(span["meta"].get("_dd.span_links"))
        links = []
        for json_link in json_links:
            link = {}
            link["trace_id"] = int(json_link["trace_id"][-16:], base=16)
            link["span_id"] = int(json_link["span_id"], base=16)
            if len(json_link["trace_id"]) > 16:
                link["trace_id_high"] = int(json_link["trace_id"][:16], base=16)
            if "attributes" in json_link:
                link["attributes"] = json_link.get("attributes")
            if "tracestate" in json_link:
                link["tracestate"] = json_link.get("tracestate")
            elif "trace_state" in json_link:
                link["tracestate"] = json_link.get("trace_state")
            if "flags" in json_link:
                link["flags"] = json_link.get("flags") | TRACECONTEXT_FLAGS_SET
            else:
                link["flags"] = 0
            links.append(link)
        return links

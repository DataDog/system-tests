"""Tracing constants, data structures and helper methods.

These are used to specify, test and work with trace data and protocols.
"""

import json
from typing import TypedDict

from ddapm_test_agent.trace import Span
from ddapm_test_agent.trace import Trace
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

NUM_VALUES_IN_NATIVE_SPAN_ATTRIBUTE = 2


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
    Stats: list[V06StatsAggr]


class V06StatsPayload(TypedDict):
    Hostname: str | None
    Env: str | None
    Version: str | None
    Stats: list[V06StatsBucket]


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
    return BaseDDSketch(mapping=mapping, store=store, negative_store=negative_store, zero_count=proto.zeroCount)


def decode_v06_stats(data: bytes) -> V06StatsPayload:
    payload = msgpack.unpackb(data)
    stats_buckets: list[V06StatsBucket] = []
    for raw_bucket in payload["Stats"]:
        stats: list[V06StatsAggr] = []
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

        bucket = V06StatsBucket(Start=raw_bucket["Start"], Duration=raw_bucket["Duration"], Stats=stats)
        stats_buckets.append(bucket)

    return V06StatsPayload(
        Hostname=payload.get("Hostname"), Env=payload.get("Env"), Version=payload.get("Version"), Stats=stats_buckets
    )


def find_trace(traces: list[Trace], trace_id: int) -> Trace:
    """Return the trace from `traces` that match a `trace_id`."""
    # TODO: Ensure all parametric applications return uint64 trace ids (not strings or bigints)
    trace_id = ((1 << 64) - 1) & id_to_int(trace_id)  # Use 64-bit trace id
    for trace in traces:
        # This check ignores the high bits of the trace id
        # TODO: Check _dd.p.tid
        if trace and trace[0].get("trace_id") == trace_id:
            return trace
    raise AssertionError(f"Trace with 64bit trace_id={trace_id} not found. Traces={traces}")


def find_span(trace: Trace, span_id: int) -> Span:
    """Return a span from the trace matches a `span_id`."""
    assert len(trace) > 0
    # TODO: Ensure all parametric applications return uint64 span ids (not strings)
    span_id = id_to_int(span_id)
    for span in trace:
        if span.get("span_id") == span_id:
            return span
    raise AssertionError(f"Span with id={span_id} not found. Trace={trace}")


def find_span_in_traces(traces: list[Trace], trace_id: int, span_id: int) -> Span:
    """Return a span from a list of traces by `trace_id` and `span_id`."""
    trace = find_trace(traces, trace_id)
    return find_span(trace, span_id)


def find_only_span(traces: list[Trace]) -> Span:
    """Return the only span in a list of traces. Raises an error if there are no traces or more than one span."""
    assert len(traces) == 1, traces
    assert len(traces[0]) == 1, traces[0]
    return traces[0][0]


def find_first_span_in_trace_payload(trace: Trace) -> Span:
    """Return the first span recieved by the trace agent. This is not necessarily the root span."""
    # Note: Ensure traces are not sorted after receiving them from the agent.
    # This helper will be used to find spans with propagation tags and some trace level tags
    return trace[0]


def find_root_span(trace: Trace) -> Span | None:
    """Return the root span of the trace or None if no root span is found."""
    for span in trace:
        if not span.get("parent_id"):
            return span
    return None


def span_has_no_parent(span: Span) -> bool:
    """Return if a span has a parent by checking the presence and value of the `parent_id`."""
    return "parent_id" not in span or span.get("parent_id") == 0 or span.get("parent_id") is None


def assert_span_has_tags(span: Span, tags: dict[str, int | str | float | bool]) -> None:
    """Assert that the span has the given tags."""
    for key, value in tags.items():
        assert key in span.get("meta", {}), f"Span missing expected tag {key}={value}"
        assert span.get("meta", {}).get(key) == value, f"Span incorrect tag value for {key}={value}"


def assert_trace_has_tags(trace: Trace, tags: dict[str, int | str | float | bool]) -> None:
    """Assert that the trace has the given tags."""
    for span in trace:
        assert_span_has_tags(span, tags)


def retrieve_span_links(span: Span) -> list:
    """Retrieves span links from a span.
    raise an exception if the span links are not found, or if it's not a list
    """
    if span.get("span_links") is not None:
        result = span["span_links"]
        if not isinstance(result, list):
            raise TypeError(f"Span links must be a list, found {result}")
        return result

    if span["meta"].get("_dd.span_links") is None:
        raise ValueError("Span links not found in span")

    # Convert span_links tags into msgpack v0.4 format
    json_links = json.loads(span["meta"].get("_dd.span_links"))
    links = []
    for json_link in json_links:
        link = {}
        link["trace_id"] = int(json_link["trace_id"][-16:], base=16)
        link["span_id"] = int(json_link["span_id"], base=16)
        if len(json_link["trace_id"]) > 16:  # noqa: PLR2004
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


def retrieve_span_events(span: Span) -> list | None:
    if span.get("span_events") is not None:
        for event in span["span_events"]:
            for key, value in event.get("attributes", {}).items():
                if isinstance(value, dict):
                    # Flatten attributes dict into a single key-value pair
                    # This is for native span events
                    assert (
                        len(value) == NUM_VALUES_IN_NATIVE_SPAN_ATTRIBUTE
                    ), f"native span event has unexpected number of values: {event}"
                    value.pop("type")
                    event["attributes"][key] = next(iter(value.values()))
                else:
                    continue
        return span["span_events"]

    if span["meta"].get("events") is None:
        return None

    # Convert span_events tags into msgpack v0.4 format
    json_events = json.loads(span["meta"].get("events"))
    events = []
    for json_event in json_events:
        event = {}

        event["time_unix_nano"] = json_event["time_unix_nano"]
        event["name"] = json_event["name"]
        if "attributes" in json_event:
            event["attributes"] = json_event["attributes"]

        events.append(event)
    return events


def id_to_int(value: str | int) -> int:
    """Convert an id from hex or a base 10 string to an integer."""
    if isinstance(value, int):
        return value

    try:
        # This is a best effort to convert hex span/trace id to an integer.
        # This is temporary solution until all parametric applications return trace/span ids
        # as stringified integers (ids will be stringified to workaround percision issues in some languages)
        return int(value)
    except ValueError:
        return int(value, 16)

from typing import List
from typing import TypedDict


class OtelSpan(TypedDict):
    name: str


class OtelSpanContext(TypedDict):
    trace_id: str
    span_id: str
    trace_flags: str
    trace_state: str
    remote: bool


OtelTrace = List[OtelSpan]

# def find_otel_span_in_traces(traces: List[Trace], span: OtelSpan) -> OtelSpan:
#     """Return a span from the traces which most closely matches `span`."""
#     assert len(traces) > 0

#     max_similarity = -math.inf
#     max_similarity_span = None
#     for trace in traces:
#         similar_span = find_span(trace, span)
#         if max_similarity_span is None:
#             max_similarity_span = similar_span
#         similarity = _span_similarity(span, max_similarity_span)
#         if similarity > max_similarity:
#             max_similarity_span = similar_span
#             max_similarity = similarity
#     return max_similarity_span


# def _span_similarity(s1: OtelSpan, s2: OtelSpan) -> int:
#     """Return a similarity rating for the two given spans."""
#     score = 0

#     for key in set(s1.keys() & s2.keys()):
#         if s1[key] == s2[key]:
#             score += 1

#     s1_meta = s1.get("meta", {})
#     s2_meta = s2.get("meta", {})
#     for key in set(s1_meta.keys()) & set(s2_meta.keys()):
#         if s1_meta[key] == s2_meta[key]:
#             score += 1

#     s1_metrics = s1.get("metrics", {})
#     s2_metrics = s2.get("metrics", {})
#     for key in set(s1_metrics.keys()) & set(s2_metrics.keys()):
#         if s1_metrics[key] == s2_metrics[key]:
#             score += 1
#     return score


# def find_span(trace: Trace, span: OtelSpan) -> OtelSpan:
#     """Return a span from the trace which most closely matches `span`."""
#     assert len(trace) > 0

#     max_similarity = -math.inf
#     max_similarity_span = trace[0]
#     for other_span in trace:
#         similarity = _span_similarity(span, other_span)
#         if similarity > max_similarity:
#             max_similarity = similarity
#             max_similarity_span = other_span
#     return max_similarity_span

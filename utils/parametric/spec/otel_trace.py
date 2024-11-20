from typing import TypedDict


class OtelSpanContext(TypedDict):
    trace_id: str
    span_id: str
    trace_flags: str
    trace_state: str
    remote: bool

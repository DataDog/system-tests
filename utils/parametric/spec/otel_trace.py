from typing import TypedDict


OTEL_UNSET_CODE = "UNSET"
OTEL_ERROR_CODE = "ERROR"
OTEL_OK_CODE = "OK"

SK_UNSPECIFIED = 0
SK_INTERNAL = 1
SK_SERVER = 2
SK_CLIENT = 3
SK_PRODUCER = 4
SK_CONSUMER = 5


class OtelSpanContext(TypedDict):
    trace_id: str
    span_id: str
    trace_flags: str
    trace_state: str
    remote: bool

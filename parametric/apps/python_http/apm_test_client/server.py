from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel

import ddtrace
from ddtrace import Span
from ddtrace.context import Context
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator


spans: Dict[int, Span] = {}
app = FastAPI(
    title="APM library test server",
    description="""
The reference implementation of the APM Library test server.

Implement the API specified below to enable your library to run all of the shared tests.
""",
)


class StartSpanArgs(BaseModel):
    parent_id: int
    name: str
    service: str
    type: str
    resource: str
    origin: str
    http_headers: List[Tuple[str, str]]


class StartSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.post("/trace/span/start")
def trace_span_start(args: StartSpanArgs) -> StartSpanReturn:
    parent: Union[None, Span, Context]
    if args.parent_id:
        parent = spans[args.parent_id]
    else:
        parent = None

    if args.origin != "":
        trace_id = parent.trace_id if parent else None
        parent_id = parent.span_id if parent else None
        parent = Context(trace_id=trace_id, span_id=parent_id, dd_origin=args.origin)

    if len(args.http_headers) > 0:
        headers = {k: v for k, v in args.http_headers}
        parent = HTTPPropagator.extract(headers)

    span = ddtrace.tracer.start_span(
        args.name, service=args.service, span_type=args.type, resource=args.resource, child_of=parent, activate=True,
    )
    spans[span.span_id] = span
    return StartSpanReturn(span_id=span.span_id, trace_id=span.trace_id,)


class SpanFinishArgs(BaseModel):
    span_id: int


class SpanFinishReturn(BaseModel):
    pass


@app.post("/trace/span/finish")
def trace_span_finish(args: SpanFinishArgs) -> SpanFinishReturn:
    span = spans[args.span_id]
    span.finish()
    return SpanFinishReturn()


class SpanSetMetaArgs(BaseModel):
    span_id: int
    key: str
    value: str


class SpanSetMetaReturn(BaseModel):
    pass


@app.post("/trace/span/set_meta")
def trace_span_set_meta(args: SpanSetMetaArgs) -> SpanSetMetaReturn:
    span = spans[args.span_id]
    span.set_tag(args.key, args.value)
    return SpanSetMetaReturn()


class SpanSetMetricArgs(BaseModel):
    span_id: int
    key: str
    value: float


class SpanSetMetricReturn(BaseModel):
    pass


@app.post("/trace/span/set_metric")
def trace_span_set_metric(args: SpanSetMetricArgs) -> SpanSetMetricReturn:
    span = spans[args.span_id]
    span.set_metric(args.key, args.value)
    return SpanSetMetricReturn()


class SpanInjectArgs(BaseModel):
    span_id: int


class SpanInjectReturn(BaseModel):
    http_headers: List[Tuple[str, str]]


@app.post("/trace/span/inject_headers")
def trace_span_inject_headers(args: SpanInjectArgs) -> SpanInjectReturn:
    ctx = spans[args.span_id].context
    headers = {}
    HTTPPropagator.inject(ctx, headers)
    return SpanInjectReturn(http_headers=[(k, v) for k, v in headers.items()])


class TraceSpansFlushArgs(BaseModel):
    pass


class TraceSpansFlushReturn(BaseModel):
    pass


@app.post("/trace/span/flush")
def trace_spans_flush(args: TraceSpansFlushArgs) -> TraceSpansFlushReturn:
    ddtrace.tracer.flush()
    return TraceSpansFlushReturn()


class TraceStatsFlushArgs(BaseModel):
    pass


class TraceStatsFlushReturn(BaseModel):
    pass


@app.post("/trace/stats/flush")
def trace_stats_flush(args: TraceStatsFlushArgs) -> TraceStatsFlushReturn:
    stats_proc = [
        p
        for p in ddtrace.tracer._span_processors
        if hasattr(ddtrace.internal.processor, "stats")
        if isinstance(p, ddtrace.internal.processor.stats.SpanStatsProcessorV06)
    ]
    if len(stats_proc):
        stats_proc[0].periodic()
    return TraceStatsFlushReturn()


class TraceSpanErrorArgs(BaseModel):
    span_id: int
    type: str
    message: str
    stack: str


class TraceSpanErrorReturn(BaseModel):
    pass


@app.post("/trace/span/error")
def trace_span_error(args: TraceSpanErrorArgs) -> TraceSpanErrorReturn:
    span = spans[args.span_id]
    span.set_tag(ERROR_MSG, args.message)
    span.set_tag(ERROR_TYPE, args.type)
    span.set_tag(ERROR_STACK, args.stack)
    span.error = 1
    return TraceSpanErrorReturn()

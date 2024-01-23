from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

import os
from fastapi import FastAPI
from pydantic import BaseModel

import opentelemetry
from opentelemetry.trace import set_tracer_provider
from opentelemetry.trace.span import NonRecordingSpan as OtelNonRecordingSpan
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import Span as OtelSpan
from opentelemetry.trace.span import StatusCode
from opentelemetry.trace.span import TraceFlags
from opentelemetry.trace.span import TraceState
from opentelemetry.trace.span import SpanContext as OtelSpanContext
from opentelemetry.trace import set_span_in_context
from ddtrace.opentelemetry import TracerProvider

import ddtrace
from ddtrace import Span
from ddtrace import config
from ddtrace.contrib.trace_utils import set_http_meta
from ddtrace.context import Context
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator


spans: Dict[int, Span] = {}
otel_spans: Dict[int, OtelSpan] = {}
app = FastAPI(
    title="APM library test server",
    description="""
The reference implementation of the APM Library test server.

Implement the API specified below to enable your library to run all of the shared tests.
""",
)

opentelemetry.trace.set_tracer_provider(TracerProvider())
# Replaces the default otel api runtime context with DDRuntimeContext
# https://github.com/open-telemetry/opentelemetry-python/blob/v1.16.0/opentelemetry-api/src/opentelemetry/context/__init__.py#L53
os.environ["OTEL_PYTHON_CONTEXT"] = "ddcontextvars_context"


class StartSpanArgs(BaseModel):
    parent_id: int
    name: str
    service: str
    type: str
    resource: str
    origin: str
    http_headers: List[Tuple[str, str]]
    links: List[Dict]


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
    for link in args.links:
        link_parent_id = link["parent_id"]
        if link_parent_id != 0:  # we have a parent_id to create link instead
            link_parent = spans[link_parent_id]
            span.link_span(link_parent.context, link.get("attributes"))
        else:
            headers = {k: v for k, v in link["http_headers"]}
            context = HTTPPropagator.extract(headers)
            span.link_span(context, link.get("attributes"))

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


class TraceSpanAddLinksArgs(BaseModel):
    span_id: int
    parent_id: int
    attributes: dict


class TraceSpanAddLinkReturn(BaseModel):
    pass


@app.post("/trace/span/add_link")
def trace_span_add_link(args: TraceSpanAddLinksArgs) -> TraceSpanAddLinkReturn:
    span = spans[args.span_id]
    linked_span = spans[args.parent_id]
    span.link_span(linked_span.context, attributes=args.attributes)
    return TraceSpanAddLinkReturn()


class HttpClientRequestArgs(BaseModel):
    method: str
    url: str
    headers: List[Tuple[str, str]]
    body: str


class HttpClientRequestReturn(BaseModel):
    pass


@app.post("/http/client/request")
def http_client_request(args: HttpClientRequestArgs) -> HttpClientRequestReturn:
    # falcon config doesn't really matter here - any config object with http header tracing enabled will work
    integration_config = config.falcon
    request_headers = {k: v for k, v in args.headers}
    response_headers = {"Content-Length": "14"}
    with ddtrace.tracer.trace("fake-request") as request_span:
        set_http_meta(
            request_span, integration_config, request_headers=request_headers, response_headers=response_headers
        )
        spans[request_span.span_id] = request_span
    config.http._reset()
    config._header_tag_name.invalidate()
    return HttpClientRequestReturn()


class OtelStartSpanArgs(BaseModel):
    name: str
    parent_id: int
    span_kind: int
    service: str = ""  # Not used but defined in protos/apm-test-client.protos
    resource: str = ""  # Not used but defined in protos/apm-test-client.protos
    type: str = ""  # Not used but defined in protos/apm-test-client.protos
    links: List[Dict] = []  # Not used but defined in protos/apm-test-client.protos
    timestamp: int
    http_headers: List[Tuple[str, str]]
    attributes: dict


class OtelStartSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.post("/trace/otel/start_span")
def otel_start_span(args: OtelStartSpanArgs):
    otel_tracer = opentelemetry.trace.get_tracer(__name__)

    if args.parent_id:
        parent_span = otel_spans[args.parent_id]
    elif args.http_headers:
        headers = {k: v for k, v in args.http_headers}
        ddcontext = HTTPPropagator.extract(headers)
        parent_span = OtelNonRecordingSpan(
            OtelSpanContext(
                ddcontext.trace_id,
                ddcontext.span_id,
                True,
                TraceFlags.SAMPLED
                if ddcontext.sampling_priority and ddcontext.sampling_priority > 0
                else TraceFlags.DEFAULT,
                TraceState.from_header([ddcontext._tracestate]),
            )
        )
    else:
        parent_span = None

    links = []
    for link in args.links:
        parent_id = link.get("parent_id", 0)
        if parent_id > 0:
            span_context = otel_spans[parent_id].get_span_context()
        else:
            headers = {k: v for k, v in link["http_headers"]}
            ddcontext = HTTPPropagator.extract(headers)
            span_context = OtelSpanContext(
                ddcontext.trace_id,
                ddcontext.span_id,
                True,
                TraceFlags.SAMPLED
                if ddcontext.sampling_priority and ddcontext.sampling_priority > 0
                else TraceFlags.DEFAULT,
                TraceState.from_header([ddcontext._tracestate]),
            )
        links.append(opentelemetry.trace.Link(span_context, link.get("attributes")))

    otel_span = otel_tracer.start_span(
        args.name,
        context=set_span_in_context(parent_span),
        kind=SpanKind(args.span_kind),
        attributes=args.attributes,
        links=links,
        # parametric tests expect timestamps to be set in microseconds (required by go)
        # but the python implementation sets time nanoseconds.
        start_time=args.timestamp * 1e3 if args.timestamp else None,
        record_exception=True,
        set_status_on_exception=True,
    )

    ctx = otel_span.get_span_context()
    otel_spans[ctx.span_id] = otel_span
    return OtelStartSpanReturn(span_id=ctx.span_id, trace_id=ctx.trace_id)


class OtelEndSpanArgs(BaseModel):
    id: int
    timestamp: int


class OtelEndSpanReturn(BaseModel):
    pass


@app.post("/trace/otel/end_span")
def otel_end_span(args: OtelEndSpanArgs):
    span = otel_spans.get(args.id)
    st = args.timestamp
    if st is not None:
        # convert timestamp from microseconds to nanoseconds
        st = st * 1e3
    span.end(st)
    return OtelEndSpanReturn()


class OtelFlushSpansArgs(BaseModel):
    seconds: int = 1


class OtelFlushSpansReturn(BaseModel):
    success: bool = 1


@app.post("/trace/otel/flush")
def otel_flush_spans(args: OtelFlushSpansArgs):
    ddtrace.tracer.flush()
    spans.clear()
    otel_spans.clear()
    return OtelFlushSpansReturn(success=True)


class OtelIsRecordingArgs(BaseModel):
    span_id: int


class OtelIsRecordingReturn(BaseModel):
    is_recording: bool


@app.post("/trace/otel/is_recording")
def otel_is_recording(args: OtelIsRecordingArgs):
    span = otel_spans.get(args.span_id)
    return OtelIsRecordingReturn(is_recording=span.is_recording())


class OtelSpanContextArgs(BaseModel):
    span_id: int


class OtelSpanContextReturn(BaseModel):
    span_id: str
    trace_id: str
    trace_flags: str
    trace_state: str
    remote: bool


@app.post("/trace/otel/span_context")
def otel_span_context(args: OtelSpanContextArgs):
    span = otel_spans[args.span_id]
    ctx = span.get_span_context()
    # Some implementations of the opentelemetry-api expect SpanContext.trace_id and SpanContext.span_id
    # to be hex encoded strings (ex: go). So the system tests were defined with this implementation in mind.
    # However, this is not the case in python. SpanContext.trace_id and SpanContext.span_id are stored
    # as integers and are converted to hex when the trace is submitted to the collector.
    # https://github.com/open-telemetry/opentelemetry-python/blob/v1.17.0/opentelemetry-api/src/opentelemetry/trace/span.py#L424-L425
    return OtelSpanContextReturn(
        span_id="{:016x}".format(ctx.span_id),
        trace_id="{:032x}".format(ctx.trace_id),
        trace_flags="{:02x}".format(ctx.trace_flags),
        trace_state=ctx.trace_state.to_header(),
        remote=ctx.is_remote,
    )


class OtelSetStatusArgs(BaseModel):
    span_id: int
    code: str
    description: str


class OtelSetStatusReturn(BaseModel):
    pass


@app.post("/trace/otel/set_status")
def otel_set_status(args: OtelSetStatusArgs):
    span = otel_spans[args.span_id]
    status_code = getattr(StatusCode, args.code.upper())
    span.set_status(status_code, args.description)
    return OtelSetStatusReturn()


class OtelSetNameArgs(BaseModel):
    span_id: int
    name: str


class OtelSetNameReturn(BaseModel):
    pass


@app.post("/trace/otel/set_name")
def otel_set_name(args: OtelSetNameArgs):
    span = otel_spans[args.span_id]
    span.update_name(args.name)
    return OtelSetNameReturn()


class OtelSetAttributesArgs(BaseModel):
    span_id: int
    attributes: dict


class OtelSetAttributesReturn(BaseModel):
    pass


@app.post("/trace/otel/set_attributes")
def otel_set_attributes(args: OtelSetAttributesArgs):
    span = otel_spans[args.span_id]
    attributes = args.attributes
    span.set_attributes(attributes)
    return OtelSetAttributesReturn()


# TODO: Remove all unused otel types and endpoints from parametric tests
# Defined in apm_test_client.proto but not implemented in library clients (_library_client.py)
# class OtelFlushTraceStatsArgs(BaseModel):
#     seconds: int = 1


# class OtelFlushTraceStatsReturn(BaseModel):
#     success: int = 1


# @app.post("/trace/otel/flush_stats")
# def otel_flush_stats(args: OtelFlushTraceStatsArgs):
#     return trace_stats_flush(args)


# class OtelForceFlushArgs(BaseModel):
#     seconds: int


# class OtelForceFlushReturn(BaseModel):
#     success: bool


# class OtelStopTracerArgs(BaseModel):
#     pass


# class OtelStopTracerReturn(BaseModel):
#     pass

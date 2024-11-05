import signal
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import os
from fastapi import FastAPI
import opentelemetry.trace
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
from opentelemetry.baggage import set_baggage
from opentelemetry.baggage import get_baggage

import ddtrace
from ddtrace import Span
from ddtrace import config
from ddtrace.contrib.trace_utils import set_http_meta
from ddtrace.context import Context
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.internal.utils.version import parse_version


spans: Dict[int, Span] = {}
otel_spans: Dict[int, OtelSpan] = {}
# Store the active span for each tracer in an array to allow for easy global access
# FastAPI resets the contextvar containing the active span after each request
active_ddspan = [None]
active_otel_span = [None]
app = FastAPI(
    title="APM library test server",
    description="""
The reference implementation of the APM Library test server.

Implement the API specified below to enable your library to run all of the shared tests.
""",
)

# Ensures the Datadog and OpenTelemetry tracers are interoperable
opentelemetry.trace.set_tracer_provider(TracerProvider())


class StartSpanArgs(BaseModel):
    parent_id: int
    name: str
    service: str
    type: str
    resource: str
    origin: str
    http_headers: List[Tuple[str, str]]
    links: List[Dict]
    span_tags: List[Tuple[str, str]]


class StartSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.get("/trace/crash")
def trace_crash() -> None:
    os.kill(os.getpid(), signal.SIGSEGV.value)


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

    if args.service == "":
        args.service = None

    if len(args.http_headers) > 0:
        headers = {k: v for k, v in args.http_headers}
        parent = HTTPPropagator.extract(headers)

    span = ddtrace.tracer.start_span(
        args.name, service=args.service, span_type=args.type, resource=args.resource, child_of=parent, activate=True,
    )
    for link in args.links:
        link_parent_id = link.get("parent_id", 0)
        if link_parent_id > 0:  # we have a parent_id to create link instead
            link_parent = spans[link_parent_id]
            span.link_span(link_parent.context, link.get("attributes"))
        else:
            headers = {k: v for k, v in link["http_headers"]}
            context = HTTPPropagator.extract(headers)
            span.link_span(context, link.get("attributes"))

    for k, v in args.span_tags:
        span.set_tag(k, v)

    spans[span.span_id] = span
    active_ddspan[0] = ddtrace.tracer.current_span()
    return StartSpanReturn(span_id=span.span_id, trace_id=span.trace_id,)


class SpanFinishArgs(BaseModel):
    span_id: int


class SpanFinishReturn(BaseModel):
    pass


class TraceConfigReturn(BaseModel):
    config: dict[str, Optional[str]]


@app.get("/trace/config")
def trace_config() -> TraceConfigReturn:
    return TraceConfigReturn(
        config={
            "dd_service": config.service,
            "dd_log_level": None,
            "dd_trace_sample_rate": str(config._trace_sample_rate),
            "dd_trace_enabled": str(config._tracing_enabled).lower(),
            "dd_runtime_metrics_enabled": str(config._runtime_metrics_enabled).lower(),
            "dd_tags": ",".join(f"{k}:{v}" for k, v in config.tags.items()),
            "dd_trace_propagation_style": ",".join(config._propagation_style_extract),
            "dd_trace_debug": str(config._debug_mode).lower(),
            "dd_trace_otel_enabled": str(config._otel_enabled).lower(),
            "dd_trace_sample_ignore_parent": None,
            "dd_env": config.env,
            "dd_version": config.version,
            "dd_trace_rate_limit": str(config._trace_rate_limit),
            "dd_trace_agent_url": config._trace_agent_url,
        }
    )


@app.post("/trace/span/finish")
def trace_span_finish(args: SpanFinishArgs) -> SpanFinishReturn:
    span = spans[args.span_id]
    span.finish()
    active_ddspan[0] = span._parent
    return SpanFinishReturn()


class SpanSetMetaArgs(BaseModel):
    span_id: int
    key: str
    value: str


class SpanSetMetaReturn(BaseModel):
    pass


class SpanSetBaggageArgs(BaseModel):
    span_id: int
    key: str
    value: str


class SpanSetBaggageReturn(BaseModel):
    pass


class SpanGetBaggageArgs(BaseModel):
    span_id: int
    key: str


class SpanGetBaggageReturn(BaseModel):
    baggage: str


class SpanGetAllBaggageArgs(BaseModel):
    span_id: int


class SpanGetAllBaggageReturn(BaseModel):
    baggage: dict[str, str]


class SpanRemoveBaggageArgs(BaseModel):
    span_id: int
    key: str


class SpanRemoveBaggageReturn(BaseModel):
    pass


class SpanRemoveAllBaggageArgs(BaseModel):
    span_id: int


class SpanRemoveAllBaggageReturn(BaseModel):
    pass


@app.post("/trace/span/set_meta")
def trace_span_set_meta(args: SpanSetMetaArgs) -> SpanSetMetaReturn:
    span = spans[args.span_id]
    span.set_tag(args.key, args.value)
    return SpanSetMetaReturn()


class SpanSetResourceArgs(BaseModel):
    span_id: int
    resource: str


class SpanSetResourceReturn(BaseModel):
    pass


@app.post("/trace/span/set_resource")
def trace_span_set_resouce(args: SpanSetResourceArgs) -> SpanSetResourceReturn:
    span = spans[args.span_id]
    span.resource = args.resource
    return SpanSetResourceReturn()


@app.post("/trace/span/set_baggage")
def trace_set_baggage(args: SpanSetBaggageArgs) -> SpanSetBaggageReturn:
    span = spans[args.span_id]
    span.context.set_baggage_item(args.key, args.value)
    return SpanSetBaggageReturn()


@app.get("/trace/span/get_baggage")
def trace_get_baggage(args: SpanGetBaggageArgs) -> SpanGetBaggageReturn:
    span = spans[args.span_id]
    return SpanGetBaggageReturn(baggage=span.context.get_baggage_item(args.key))


@app.get("/trace/span/get_all_baggage")
def trace_get_all_baggage(args: SpanGetAllBaggageArgs) -> SpanGetAllBaggageReturn:
    span = spans[args.span_id]
    return SpanGetAllBaggageReturn(baggage=span.context.get_all_baggage_items())


@app.post("/trace/span/remove_baggage")
def trace_remove_baggage(args: SpanRemoveBaggageArgs) -> SpanRemoveBaggageReturn:
    span = spans[args.span_id]
    span.context.remove_baggage_item(args.key)
    return SpanRemoveBaggageReturn()


@app.post("/trace/span/remove_all_baggage")
def trace_remove_all_baggage(args: SpanRemoveAllBaggageArgs) -> SpanRemoveAllBaggageReturn:
    span = spans[args.span_id]
    span.context.remove_all_baggage_items()
    return SpanRemoveBaggageReturn()


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
    span = spans[args.span_id]
    headers = {}
    # span was added as a kwarg for inject in ddtrace 2.8
    if get_ddtrace_version() >= (2, 8, 0):
        HTTPPropagator.inject(span.context, headers, span)
    else:
        HTTPPropagator.inject(span.context, headers)
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


class TraceSpanCurrentReturn(BaseModel):
    span_id: int
    trace_id: int


@app.get("/trace/span/current")
def trace_span_current() -> TraceSpanCurrentReturn:
    span_id = 0
    trace_id = 0
    if active_ddspan[0]:
        span_id = active_ddspan[0].span_id
        trace_id = active_ddspan[0].trace_id
    return TraceSpanCurrentReturn(span_id=span_id, trace_id=trace_id)


class HttpClientRequestArgs(BaseModel):
    method: str
    url: str
    headers: List[Tuple[str, str]]
    body: str


class HttpClientRequestReturn(BaseModel):
    pass


@app.post("/http/client/request")
def http_client_request(args: HttpClientRequestArgs) -> HttpClientRequestReturn:
    """Creates and finishes a span similar to the ones created during HTTP request/response cycles"""
    # falcon config doesn't really matter here - any config object with http header tracing enabled will work
    integration_config = config.falcon
    request_headers = {k: v for k, v in args.headers}
    response_headers = {"Content-Length": "14"}
    with ddtrace.tracer.trace("fake-request") as request_span:
        set_http_meta(
            request_span, integration_config, request_headers=request_headers, response_headers=response_headers
        )
        spans[request_span.span_id] = request_span
    # this cache invalidation happens in most web frameworks as a side effect of their multithread design
    # it's made explicit here to allow test expectations to be precise
    config.http._reset()
    config._header_tag_name.invalidate()
    return HttpClientRequestReturn()


class OtelStartSpanArgs(BaseModel):
    name: str
    parent_id: int
    span_kind: int
    service: str = ""
    resource: str = ""
    type: str = ""
    links: List[Dict] = []
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
                (
                    TraceFlags.SAMPLED
                    if ddcontext.sampling_priority and ddcontext.sampling_priority > 0
                    else TraceFlags.DEFAULT
                ),
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
                (
                    TraceFlags.SAMPLED
                    if ddcontext.sampling_priority and ddcontext.sampling_priority > 0
                    else TraceFlags.DEFAULT
                ),
                TraceState.from_header([ddcontext._tracestate]),
            )
        links.append(opentelemetry.trace.Link(span_context, link.get("attributes")))

    # parametric tests expect span kind to be 0 for internal, 1 for server, 2 for client, ....
    # while parametric tests set 0 for unset, 1 internal, 2 for server, 3 for client, ....
    span_kind_int = max(0, args.span_kind - 1)
    with otel_tracer.start_as_current_span(
        args.name,
        context=set_span_in_context(parent_span),
        kind=SpanKind(span_kind_int),
        attributes=args.attributes,
        links=links,
        # parametric tests expect timestamps to be set in microseconds (required by go)
        # but the python implementation sets time nanoseconds.
        start_time=args.timestamp * 1e3 if args.timestamp else None,
        record_exception=True,
        set_status_on_exception=True,
        end_on_exit=False,
    ) as otel_span:
        # Store the active span for easy global access. This active span should be equal to the newly created span.
        active_otel_span[0] = opentelemetry.trace.get_current_span()
        active_ddspan[0] = ddtrace.tracer.current_span()

    ctx = otel_span.get_span_context()
    otel_spans[ctx.span_id] = otel_span
    return OtelStartSpanReturn(span_id=ctx.span_id, trace_id=ctx.trace_id)


class OtelAddEventReturn(BaseModel):
    pass


class OtelAddEventArgs(BaseModel):
    span_id: int
    name: str
    timestamp: Optional[int] = None
    attributes: Optional[dict] = None


@app.post("/trace/otel/add_event")
def otel_add_event(args: OtelAddEventArgs) -> OtelAddEventReturn:
    span = otel_spans[args.span_id]
    span.add_event(args.name, args.attributes, args.timestamp)
    return OtelAddEventReturn()


class OtelSetBaggageArgs(BaseModel):
    span_id: int
    key: str
    value: str


class OtelSetBaggageReturn(BaseModel):
    value: str


@app.post("/trace/otel/otel_set_baggage")
def otel_set_baggage(args: OtelSetBaggageArgs) -> OtelSetBaggageReturn:
    # span = otel_spans[args.span_id]
    headers = {}
    context = set_baggage(args.key, args.value)
    value = get_baggage(args.key, context)
    return OtelSetBaggageReturn(value=value)


class OtelRecordExceptionReturn(BaseModel):
    pass


class OtelRecordExceptionArgs(BaseModel):
    span_id: int
    message: str
    attributes: dict


@app.post("/trace/otel/record_exception")
def otel_record_exception(args: OtelRecordExceptionArgs) -> OtelRecordExceptionReturn:
    span = otel_spans[args.span_id]
    span.record_exception(Exception(args.message), args.attributes)
    return OtelRecordExceptionReturn()


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

    active_ddspan[0] = span._ddspan._parent
    active_otel_span[0] = otel_spans.get(active_ddspan[0].span_id) if active_ddspan[0] else None
    span.end(st)
    return OtelEndSpanReturn()


class OtelCurrentSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.get("/trace/otel/current_span")
def otel_current_span():
    trace_id = 0
    span_id = 0
    if active_otel_span[0]:
        ctx = active_otel_span[0].get_span_context()
        trace_id = ctx.trace_id
        span_id = ctx.span_id
    return OtelCurrentSpanReturn(trace_id=trace_id, span_id=span_id)


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


def get_ddtrace_version() -> Tuple[int, int, int]:
    return parse_version(getattr(ddtrace, "__version__", ""))


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

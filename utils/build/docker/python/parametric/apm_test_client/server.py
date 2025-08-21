import ctypes
from multiprocessing import context
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Any
import logging
import os
from fastapi import FastAPI
import opentelemetry.trace
from pydantic import BaseModel
from urllib.parse import urlparse

import opentelemetry
from opentelemetry.metrics import Meter
from opentelemetry.metrics import Instrument
from opentelemetry.metrics import get_meter_provider
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
from ddtrace import config
from ddtrace.settings.profiling import config as profiling_config
from ddtrace.contrib.trace_utils import set_http_meta
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator
from ddtrace.internal.utils.version import parse_version

try:
    from ddtrace.trace import Span
    from ddtrace.trace import Context
    from ddtrace._trace.sampling_rule import SamplingRule
except ImportError:
    from ddtrace import Span
    from ddtrace.context import Context
    from ddtrace.sampling_rule import SamplingRule

log = logging.getLogger(__name__)

spans: Dict[int, Span] = {}
ddcontexts: Dict[int, Context] = {}
otel_spans: Dict[int, OtelSpan] = {}
otel_meters: Dict[str, Meter] = {}
otel_meter_instruments: Dict[str, Instrument] = {}
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


try:
    # ddtrace.internal.agent.config is only available in ddtrace>=3.3.0
    from ddtrace.internal.agent import config as agent_config

    def trace_agent_url():
        return agent_config.trace_agent_url

    def dogstatsd_url():
        return agent_config.dogstatsd_url
except ImportError:
    # TODO: Remove this block once we stop running parametric tests for ddtrace<3.3.0
    def trace_agent_url():
        return ddtrace.tracer._agent_url

    def dogstatsd_url():
        return ddtrace.tracer._dogstatsd_url


class StartSpanArgs(BaseModel):
    name: str
    parent_id: Optional[int]
    service: Optional[str]
    type: Optional[str]
    resource: Optional[str]
    span_tags: List[Tuple[str, str]]


class StartSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.get("/trace/crash")
def trace_crash() -> None:
    ctypes.string_at(0)


@app.post("/trace/span/start")
def trace_span_start(args: StartSpanArgs) -> StartSpanReturn:
    parent = spans.get(args.parent_id, ddcontexts.get(args.parent_id))
    span = ddtrace.tracer.start_span(
        args.name, service=args.service, span_type=args.type, resource=args.resource, child_of=parent, activate=True
    )
    # TODO: add tags to tracer.start_span
    for k, v in args.span_tags:
        span.set_tag(k, v)
    spans[span.span_id] = span
    # Access the active span from the tracer, this allows us to test tracer's context management
    active_ddspan[0] = ddtrace.tracer.current_span()
    return StartSpanReturn(span_id=span.span_id, trace_id=span.trace_id)


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
            "dd_trace_sample_rate": str(_global_sampling_rate()),
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
            "dd_trace_agent_url": trace_agent_url(),
            "dd_dogstatsd_host": urlparse(dogstatsd_url()).hostname,
            "dd_dogstatsd_port": urlparse(dogstatsd_url()).port,
            "dd_logs_injection": str(config._logs_injection).lower(),
            "dd_profiling_enabled": str(profiling_config.enabled).lower(),
            "dd_data_streams_enabled": str(config._data_streams_enabled).lower(),
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


class SpanExtractArgs(BaseModel):
    http_headers: List[Tuple[str, str]]


class SpanExtractReturn(BaseModel):
    span_id: Optional[int]


@app.post("/trace/span/extract_headers")
def trace_span_extract_headers(args: SpanExtractArgs) -> SpanExtractReturn:
    headers = {k: v for k, v in args.http_headers}
    context = HTTPPropagator.extract(headers)
    if context:
        if context.span_id in ddcontexts:
            log.warning(
                "Duplicate span context detected. The following span context will be overwritten: %s",
                ddcontexts[context.span_id],
            )
        ddcontexts[context.span_id] = context
    return SpanExtractReturn(span_id=context.span_id)


class TraceSpansFlushArgs(BaseModel):
    pass


class TraceSpansFlushReturn(BaseModel):
    pass


@app.post("/trace/span/flush")
def trace_spans_flush(args: TraceSpansFlushArgs) -> TraceSpansFlushReturn:
    ddtrace.tracer.flush()
    spans.clear()
    ddcontexts.clear()
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


class TraceSpanAddEventsArgs(BaseModel):
    span_id: int
    name: str
    timestamp: int
    attributes: dict


class TraceSpanAddLinkReturn(BaseModel):
    pass


class TraceSpanAddEventReturn(BaseModel):
    pass


@app.post("/trace/span/add_link")
def trace_span_add_link(args: TraceSpanAddLinksArgs) -> TraceSpanAddLinkReturn:
    span = spans[args.span_id]
    if args.parent_id in spans:
        linked_context = spans[args.parent_id].context
    elif args.parent_id in ddcontexts:
        linked_context = ddcontexts[args.parent_id]
    else:
        raise ValueError(f"Parent span {args.parent_id} not found in {spans.keys()} or {ddcontexts.keys()}")
    span.link_span(linked_context, attributes=args.attributes)
    return TraceSpanAddLinkReturn()


@app.post("/trace/span/add_event")
def trace_span_add_event(args: TraceSpanAddEventsArgs) -> TraceSpanAddEventReturn:
    span = spans[args.span_id]
    span.add_event(args.name, args.attributes, args.timestamp)
    return TraceSpanAddEventReturn()


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


class OtelStartSpanArgs(BaseModel):
    name: str
    parent_id: Optional[int] = None
    span_kind: Optional[int] = None
    timestamp: Optional[int] = None
    links: List[Dict]
    events: List[Dict]
    attributes: dict


class OtelStartSpanReturn(BaseModel):
    span_id: int
    trace_id: int


@app.post("/trace/otel/start_span")
def otel_start_span(args: OtelStartSpanArgs):
    otel_tracer = opentelemetry.trace.get_tracer(__name__)

    parent_span = otel_spans.get(args.parent_id)
    links = []
    for link in args.links:
        parent_id = link["parent_id"]
        span_context = otel_spans[parent_id].get_span_context()
        links.append(opentelemetry.trace.Link(span_context, link.get("attributes")))

    with otel_tracer.start_as_current_span(
        args.name,
        context=set_span_in_context(parent_span),
        kind=SpanKind(args.span_kind or 0),
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
        for event in args.events:
            otel_span.add_event(event["name"], event.get("attributes"), event.get("timestamp"))

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
    timestamp: Optional[int]


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
    ddcontexts.clear()
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


class OtelGetMeterArgs(BaseModel):
    name: str
    version: Optional[str]
    schema_url: Optional[str]
    attributes: Optional[dict] = None


class OtelGetMeterReturn(BaseModel):
    pass


@app.post("/metrics/otel/get_meter")
def otel_get_meter(args: OtelGetMeterArgs):
    if args.name not in otel_meters:
        otel_meters[args.name] = get_meter_provider().get_meter(name=args.name, version=args.version, schema_url=args.schema_url, attributes=args.attributes)
    return OtelGetMeterReturn()


class OtelCreateCounterArgs(BaseModel):
    meter_name: str
    name: str
    description: str
    unit: str


class OtelCreateCounterReturn(BaseModel):
    pass


@app.post("/metrics/otel/create_counter")
def otel_create_counter(args: OtelCreateCounterArgs):
    if args.meter_name not in otel_meters:
        raise ValueError(f"Meter name {args.meter_name} not found in registered meters {otel_meters.keys()}")

    meter = otel_meters[args.meter_name]
    counter = meter.create_counter(args.name, args.unit, args.description)

    instrument_key = ",".join(
        [args.meter_name, args.name.strip().lower(), "counter", args.unit, args.description]
    )
    otel_meter_instruments[instrument_key] = counter
    return OtelCreateCounterReturn()


class OtelCounterAddArgs(BaseModel):
    meter_name: str
    name: str
    unit: str
    description: str
    value: float
    attributes: dict


class OtelCounterAddReturn(BaseModel):
    pass


@app.post("/metrics/otel/counter_add")
def otel_counter_add(args: OtelCounterAddArgs):
    if args.meter_name not in otel_meters:
        raise ValueError(f"Meter name {args.meter_name} not found in registered meters {otel_meters.keys()}")

    instrument_key = ",".join(
        [args.meter_name, args.name.strip().lower(), "counter", args.unit, args.description]
    )

    if instrument_key not in otel_meter_instruments:
        raise ValueError(f"Instrument with identifying fields Name={args.name},Kind=Counter,Unit={args.unit},Description={args.description} not found in registered instruments for Meter={args.meter_name}")

    counter = otel_meter_instruments[instrument_key]
    counter.add(args.value, args.attributes)
    return OtelCounterAddReturn()


def get_ddtrace_version() -> Tuple[int, int, int]:
    return parse_version(getattr(ddtrace, "__version__", ""))


def _global_sampling_rate():
    for rule in ddtrace.tracer._sampler.rules:
        if (
            # Note: SamplingRule.NO_RULE was removed in ddtrace v3.12.0
            # but we keep it here for compatibility with older versions
            rule.service == getattr(SamplingRule, "NO_RULE", None)
            and rule.name == getattr(SamplingRule, "NO_RULE", None)
            and rule.resource == getattr(SamplingRule, "NO_RULE", None)
            and rule.tags == getattr(SamplingRule, "NO_RULE", {})
            and rule.provenance in ("default", None)
        ):
            return rule.sample_rate
    return 1.0


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

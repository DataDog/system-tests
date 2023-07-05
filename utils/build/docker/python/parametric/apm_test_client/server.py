from concurrent import futures
from typing import Dict
from typing import Union
import os
import opentelemetry
from opentelemetry.trace import SpanKind
from opentelemetry.trace.span import StatusCode
from opentelemetry.trace.span import Span as OtelSpan
from opentelemetry.trace.span import TraceFlags
from opentelemetry.trace.span import TraceState
from opentelemetry.trace.span import SpanContext as OtelSpanContext
from opentelemetry.trace.span import NonRecordingSpan as OtelNonRecordingSpan
from opentelemetry.trace import set_span_in_context
from ddtrace.opentelemetry import TracerProvider

import ddtrace
from ddtrace import Span
from ddtrace.context import Context
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator
import grpc

from .protos import apm_test_client_pb2, apm_test_client_pb2_grpc


ddtrace.patch(requests=True)


class APMClientServicer(apm_test_client_pb2_grpc.APMClientServicer):
    def __init__(self):
        self._spans: Dict[int, Span] = {}
        self._otel_spans: Dict[int, OtelSpan] = {}
        super().__init__()

    def StartSpan(self, request, context):
        parent: Union[None, Span, Context]
        if request.parent_id:
            parent = self._spans[request.parent_id]
        else:
            parent = None

        if request.origin not in ["", None]:
            trace_id = parent.trace_id if parent else None
            parent_id = parent.span_id if parent else None
            parent = Context(trace_id=trace_id, span_id=parent_id, dd_origin=request.origin)

        if request.http_headers.ByteSize() > 0:
            headers = {}
            for header_tuple in request.http_headers.http_headers:
                headers[header_tuple.key] = header_tuple.value
            parent = HTTPPropagator.extract(headers)

        span = ddtrace.tracer.start_span(
            request.name,
            service=request.service,
            span_type=request.type,
            resource=request.resource,
            child_of=parent,
            activate=True,
        )
        self._spans[span.span_id] = span
        return apm_test_client_pb2.StartSpanReturn(span_id=span.span_id,)

    def InjectHeaders(self, request, context):
        ctx = self._spans[request.span_id].context
        headers = {}
        HTTPPropagator.inject(ctx, headers)
        distrib_headers = apm_test_client_pb2.DistributedHTTPHeaders()
        for k, v in headers.items():
            distrib_headers.http_headers.append(apm_test_client_pb2.HeaderTuple(key=k, value=v))

        return apm_test_client_pb2.InjectHeadersReturn(http_headers=distrib_headers,)

    def SpanSetMeta(self, request, context):
        span = self._spans[request.span_id]
        span.set_tag(request.key, request.value)
        return apm_test_client_pb2.SpanSetMetaReturn()

    def SpanSetMetric(self, request, context):
        span = self._spans[request.span_id]
        span.set_metric(request.key, request.value)
        return apm_test_client_pb2.SpanSetMetricReturn()

    def SpanSetError(self, request, context):
        span = self._spans[request.span_id]
        span.set_tag(ERROR_MSG, request.message)
        span.set_tag(ERROR_TYPE, request.type)
        span.set_tag(ERROR_STACK, request.stack)
        span.error = 1
        return apm_test_client_pb2.SpanSetErrorReturn()

    def FinishSpan(self, request, context):
        span = self._spans[request.id]
        span.finish()
        return apm_test_client_pb2.FinishSpanReturn()

    def FlushSpans(self, request, context):
        ddtrace.tracer.flush()
        self._spans.clear()
        return apm_test_client_pb2.FlushSpansReturn()

    def FlushTraceStats(self, request, context):
        stats_proc = [
            p
            for p in ddtrace.tracer._span_processors
            if hasattr(ddtrace.internal.processor, "stats")
            if isinstance(p, ddtrace.internal.processor.stats.SpanStatsProcessorV06)
        ]
        if len(stats_proc):
            stats_proc[0].periodic()
        return apm_test_client_pb2.FlushTraceStatsReturn()

    def HTTPClientRequest(self, request, context):
        import requests

        headers = {
            h.key: h.value for h in request.headers.http_headers
        }
        req = requests.request(
            method=request.method,
            url=request.url,
            headers=headers,
            data=request.body
        )
        return apm_test_client_pb2.HTTPRequestReturn(
            status_code=str(req.status_code),
        )

    def StopTracer(self, request, context):
        return apm_test_client_pb2.StopTracerReturn()

    def OtelStartSpan(self, request, context):
        # Note - request.resource, request.type, and request.new_root are not used.
        parent_span = None
        if request.parent_id:
            parent_span = self._otel_spans[request.parent_id]
        elif request.http_headers.ByteSize() > 0:
            headers = {}
            for header_tuple in request.http_headers.http_headers:
                headers[header_tuple.key] = header_tuple.value
            ddcontext = HTTPPropagator.extract(headers)
            parent_span = OtelNonRecordingSpan(
                OtelSpanContext(
                    trace_id=ddcontext.trace_id,
                    span_id=ddcontext.span_id,
                    is_remote=True,
                    trace_flags=TraceFlags.SAMPLED
                    if ddcontext.sampling_priority and ddcontext.sampling_priority > 0
                    else TraceFlags.DEFAULT,
                    trace_state=TraceState.from_header([ddcontext._tracestate]),
                )
            )

        otel_tracer = opentelemetry.trace.get_tracer(__name__)
        otel_span = otel_tracer.start_span(
            request.name,  # type: str
            context=set_span_in_context(parent_span),
            kind=SpanKind(request.span_kind),
            attributes=self._get_attributes_from_request(request),
            links=None,
            # parametric tests expect timestamps to be set in microseconds (required by go)
            # but the python implementation sets time nanoseconds.
            start_time=request.timestamp * 1e3 if request.timestamp else None,
            record_exception=True,
            set_status_on_exception=True,
        )

        ctx = otel_span.get_span_context()
        self._otel_spans[ctx.span_id] = otel_span
        return apm_test_client_pb2.OtelStartSpanReturn(span_id=ctx.span_id, trace_id=ctx.trace_id)

    def OtelEndSpan(self, request, context):
        span = self._otel_spans.get(request.id)
        st = request.timestamp
        if st is not None:
            # convert timestamp from microseconds to nanoseconds
            st = st * 1e3
        span.end(st)
        return apm_test_client_pb2.OtelEndSpanReturn()

    def OtelIsRecording(self, request, context):
        span = self._otel_spans.get(request.span_id)
        return apm_test_client_pb2.OtelIsRecordingReturn(is_recording=span.is_recording())

    def OtelSpanContext(self, request, context):
        span = self._otel_spans[request.span_id]
        ctx = span.get_span_context()
        # Some implementations of the opentelemetry-api expect SpanContext.trace_id and SpanContext.span_id
        # to be hex encoded strings (ex: go). So the system tests were defined with this implementation in mind.
        # However, this is not the case in python. SpanContext.trace_id and SpanContext.span_id are stored
        # as integers and are converted to hex when the trace is submitted to the collector.
        # https://github.com/open-telemetry/opentelemetry-python/blob/v1.17.0/opentelemetry-api/src/opentelemetry/trace/span.py#L424-L425
        return apm_test_client_pb2.OtelSpanContextReturn(
            span_id="{:016x}".format(ctx.span_id),
            trace_id="{:032x}".format(ctx.trace_id),
            trace_flags="{:02x}".format(ctx.trace_flags),
            trace_state=ctx.trace_state.to_header(),
            remote=ctx.is_remote,
        )

    def OtelSetStatus(self, request, context):
        span = self._otel_spans[request.span_id]
        status_code = getattr(StatusCode, request.code.upper())
        span.set_status(status_code, request.description)
        return apm_test_client_pb2.OtelSetStatusReturn()

    def OtelSetName(self, request, context):
        span = self._otel_spans[request.span_id]
        span.update_name(request.name)
        return apm_test_client_pb2.OtelSetNameReturn()

    def OtelSetAttributes(self, request, context):
        span = self._otel_spans[request.span_id]
        attributes = self._get_attributes_from_request(request)
        span.set_attributes(attributes)
        return apm_test_client_pb2.OtelSetAttributesReturn()

    def OtelFlushSpans(self, request, context):
        ddtrace.tracer.flush()
        self._spans.clear()
        self._otel_spans.clear()
        return apm_test_client_pb2.OtelFlushSpansReturn(success=True)

    def OtelFlushTraceStats(self, request, context):
        return self.FlushTraceStats(request, context)

    def _get_attributes_from_request(self, request):
        attributes = {}
        for k, v in request.attributes.key_vals.items():
            vals = [getattr(val, val.WhichOneof("val")) for val in v.val]
            attributes[k] = vals[0] if len(vals) == 1 else vals
        return attributes


def configure_otel_tracer():
    opentelemetry.trace.set_tracer_provider(TracerProvider())
    # Replaces the default otel api runtime context with DDRuntimeContext
    # https://github.com/open-telemetry/opentelemetry-python/blob/v1.16.0/opentelemetry-api/src/opentelemetry/context/__init__.py#L53
    os.environ["OTEL_PYTHON_CONTEXT"] = "ddcontextvars_context"


def serve(port: str):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    apm_test_client_pb2_grpc.add_APMClientServicer_to_server(APMClientServicer(), server)
    configure_otel_tracer()
    server.add_insecure_port("[::]:%s" % port)
    server.start()
    server.wait_for_termination()

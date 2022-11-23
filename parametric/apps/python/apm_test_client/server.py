from concurrent import futures
from typing import Dict
from typing import Union

import ddtrace
from ddtrace import Span
from ddtrace.context import Context
from ddtrace.constants import ERROR_MSG
from ddtrace.constants import ERROR_STACK
from ddtrace.constants import ERROR_TYPE
from ddtrace.propagation.http import HTTPPropagator
import grpc

from .protos import apm_test_client_pb2, apm_test_client_pb2_grpc


class APMClientServicer(apm_test_client_pb2_grpc.APMClientServicer):
    def __init__(self):
        self._spans: Dict[int, Span] = {}
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
            headers = dict(request.http_headers.http_headers)
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
        return apm_test_client_pb2.StartSpanReturn(
            span_id=span.span_id,
        )

    def InjectHeaders(self, request, context):
        ctx = self._spans[request.span_id].context
        headers = {}
        HTTPPropagator.inject(ctx, headers)
        distrib_headers = apm_test_client_pb2.DistributedHTTPHeaders()

        if headers["x-datadog-trace-id"]:
            for k,v in headers.items():
                distrib_headers.http_headers[k] = v

        return apm_test_client_pb2.InjectHeadersReturn(
           http_headers=distrib_headers,
        )

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

    def StopTracer(self, request, context):
        return apm_test_client_pb2.StopTracerReturn()


def serve(port: str):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    apm_test_client_pb2_grpc.add_APMClientServicer_to_server(APMClientServicer(), server)
    server.add_insecure_port("[::]:%s" % port)
    server.start()
    server.wait_for_termination()

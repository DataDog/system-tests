from concurrent import futures

import ddtrace
import grpc

from .pb import apm_test_client_pb2, apm_test_client_pb2_grpc


class APMClientServicer(apm_test_client_pb2_grpc.APMClientServicer):
    def __init__(self):
        self._spans: dict[int, ddtrace.Span] = {}
        super().__init__()

    def StartSpan(self, request, context):
        if request.parent_id:
            parent = self._spans[request.parent_id]
        else:
            parent = None
        span = ddtrace.tracer.start_span(request.name, service=request.service, child_of=parent, activate=True)
        self._spans[span.span_id] = span
        return apm_test_client_pb2.StartSpanReturn(
            id=span.span_id,
        )

    def FinishSpan(self, request, context):
        span = self._spans[request.id]
        del self._spans[request.id]
        span.finish()
        return apm_test_client_pb2.FinishSpanReturn()

    def FlushSpans(self, request, context):
        ddtrace.tracer.flush()
        return apm_test_client_pb2.FlushSpansReturn()


def serve(port: str):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    apm_test_client_pb2_grpc.add_APMClientServicer_to_server(APMClientServicer(), server)
    server.add_insecure_port("[::]:%s" % port)
    server.start()
    server.wait_for_termination()

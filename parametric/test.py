import grpc
from parametric.protos import apm_test_client_pb2 as pb
from parametric.protos import apm_test_client_pb2_grpc


channel = grpc.insecure_channel("localhost:50051")
grpc.channel_ready_future(channel).result(timeout=5)
client = apm_test_client_pb2_grpc.APMClientStub(channel)

resp = client.StartSpan(
    pb.StartSpanArgs(name="test", service="service", resource="/endspoint", parent_id=0, type="type",)
)
client.FinishSpan(pb.FinishSpanArgs(id=resp.span_id,))

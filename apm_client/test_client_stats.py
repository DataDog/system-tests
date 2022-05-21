import os

import grpc
import pytest

from apm_client.protos import apm_test_client_pb2 as pb
from apm_client.protos import apm_test_client_pb2_grpc


@pytest.fixture
def test_client_port():
    yield os.getenv("APM_TEST_CLIENT_SERVER_PORT") or "50051"


@pytest.fixture
def test_server():
    # test for open port
    # docker run -e ... ... ...
    yield
    # docker stop <id>


@pytest.fixture
def test_client(test_client_port):
    """
    """
    with grpc.insecure_channel("localhost:%s" % test_client_port) as channel:
        client = apm_test_client_pb2_grpc.APMClientStub(channel)
        yield client
        client.FlushSpans(pb.FlushSpansArgs())


@pytest.mark.parametrize("DD_TRACE_SAMPLE_RATE", [0.0, 1.0])  # => DD_TRACE_SAMPLE_RATE=...
@pytest.mark.snapshot(async_mode=False)
def test_client_trace(test_client):
    """
    """
    resp = test_client.StartSpan(pb.StartSpanArgs(
        name="web.request",
        service="webserver",
    ))
    resp2 = test_client.StartSpan(pb.StartSpanArgs(
        name="postgres.query",
        service="postgres2",
        parent_id=resp.id,
    ))
    test_client.FinishSpan(pb.FinishSpanArgs(id=resp2.id))
    test_client.FinishSpan(pb.FinishSpanArgs(id=resp.id))

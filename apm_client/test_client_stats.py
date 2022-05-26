import pytest

from apm_client.protos import apm_test_client_pb2 as pb


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


@snapshot
# @parametrize("lang", ["python", "nodejs"])
@parametrize(
    "apm_test_server_env",
    [
        {
            "DD_TRACE_COMPUTE_STATS": "1",
        }
    ],
)
def test_client_trace(test_agent, test_client, apm_test_server_env):
    """ """
    resp = test_client.StartSpan(
        pb.StartSpanArgs(
            name="web.request",
            service="webserver",
        )
    )
    resp2 = test_client.StartSpan(
        pb.StartSpanArgs(
            name="postgres.query",
            service="postgres",
            parent_id=resp.id,
        )
    )
    test_client.FinishSpan(pb.FinishSpanArgs(id=resp2.id))
    test_client.FinishSpan(pb.FinishSpanArgs(id=resp.id))

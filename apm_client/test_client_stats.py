import os
import shutil
import subprocess
import sys
import time

import grpc
import pytest

from apm_client.protos import apm_test_client_pb2 as pb
from apm_client.protos import apm_test_client_pb2_grpc


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


@pytest.fixture
def test_server_port():
    yield os.getenv("APM_TEST_CLIENT_SERVER_PORT") or "50051"


@pytest.fixture
def test_server_env():
    yield {}


@pytest.fixture
def test_server_container_tag():
    yield "py-test-client"


@pytest.fixture
def test_server_container_name():
    yield "python-test-client"


@pytest.fixture
def test_server(tmp_path, test_server_port, test_server_env, test_server_container_tag, test_server_container_name):
    env = {}
    if sys.platform == "darwin":
        env["DD_TRACE_AGENT_URL"] = "http://host.docker.internal:8126"
    else:
        env["DD_TRACE_AGENT_URL"] = "http://localhost:8126"
    env.update(test_server_env)
    # test for open port
    # docker run -e ... ... ...
    cmd = [
        shutil.which("docker"),
        "run",
        "--rm",
        "--name=%s" % test_server_container_name,
        "-p%s:%s" % (test_server_port, test_server_port),
        "-v",
        "%s:%s" % (os.path.join(os.getcwd(), "python", "run.sh"), "/client/run.sh"),
        "-v",
        "%s:%s" % (os.path.join(os.getcwd(), "python", "apm_test_client"), "/client/apm_test_client"),
    ]
    for k, v in env.items():
        cmd.extend(["-e", "%s=%s" % (k, v)])
    cmd += [test_server_container_tag]
    f = open(tmp_path / "server.out", "w")
    print(f)
    print(" ".join(cmd))
    f.write(" ".join(cmd))
    f.write("\n\n")
    f.flush()
    subprocess.Popen(
        cmd,
        stdout=f,
        stderr=f,
        close_fds=True,
        env=test_server_env,
    )
    yield
    subprocess.run(
        [
            shutil.which("docker"),
            "kill",
            test_server_container_name,
        ],
        stdout=f,
        stderr=f,
        check=True,
    )
    f.close()


@pytest.fixture
def test_client(test_server, test_server_port):
    # Try to establish a connection until it succeeds or number of tries
    # is exceeded.
    for i in range(100):
        try:
            with grpc.insecure_channel("localhost:%s" % test_server_port) as channel:
                client = apm_test_client_pb2_grpc.APMClientStub(channel)
                client.FlushSpans(pb.FlushSpansArgs())
                yield client
                client.FlushSpans(pb.FlushSpansArgs())
        except Exception:
            time.sleep(0.2)
        else:
            break
    else:
        assert 0


@snapshot(async_mode=False)
# @parametrize("lang", ["python", "nodejs"])
@parametrize(
    "test_server_env",
    [
        {
            "DD_TRACE_COMPUTE_STATS": "1",
        }
    ],
)
def test_client_trace(test_client, test_server_env):
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


# def test_client_top_level_stats(test_client):
#     # Should be top-level and have stats.
#     resp = test_client.StartSpan(pb.StartSpanArgs(
#         name="webserver.request",
#         service="webserver",
#     ))
#     # Should also be top-level and have stats.
#     resp2 = test_client.StartSpan(pb.StartSpanArgs(
#         name="db.query",
#         service="postgres",
#         parent_id=resp.id,
#     ))
#     test_client.FinishSpan(pb.FinishSpanArgs(id=resp2.id))
#     test_client.FinishSpan(pb.FinishSpanArgs(id=resp.id))

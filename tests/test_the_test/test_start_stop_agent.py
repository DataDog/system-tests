import pytest

pytestmark = pytest.mark.skipif(
    __import__("os").getenv("DOCKER_SMOKE") != "1",
    reason="Docker-backed; run with DOCKER_SMOKE=1",
)


def test_start_agent_then_stop(request):
    from utils._context._scenarios import scenarios

    factory = scenarios.parametric._test_agent_factory
    factory.configure("logs_parametric")
    factory.pull()

    network = __import__("utils.docker_fixtures._core", fromlist=["get_docker_client"])
    client = network.get_docker_client().networks.create(name="reuse_smoke_net", driver="bridge")
    try:
        api, stop = factory.start_agent(
            request=request,
            worker_id="gw0",
            container_name="ddapm-test-agent-reuse-smoke",
            docker_network=client.name,
            agent_env={},
            container_otlp_http_port=4318,
            container_otlp_grpc_port=4317,
        )
        try:
            assert api.info()["version"] == "test"  # agent answered → it is ready
        finally:
            stop()
    finally:
        client.remove()

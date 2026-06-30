import os

import pytest

from utils._context._scenarios import scenarios
from utils.docker_fixtures._core import get_docker_client
from utils.docker_fixtures._test_agent import DEFAULT_OTLP_HTTP_PORT, DEFAULT_OTLP_GRPC_PORT


def test_start_agent_then_stop(request: pytest.FixtureRequest):
    # Docker-backed smoke test. Gate at runtime rather than with a module-level
    # pytest.mark.skipif: the root conftest's _item_must_pass iterates skipif
    # marker.args[0] (all(marker.args[0])), which raises on a bool condition and
    # crashes collection for every session that collects this file.
    if os.getenv("DOCKER_SMOKE") != "1":
        pytest.skip("Docker-backed; run with DOCKER_SMOKE=1")

    factory = scenarios.parametric._test_agent_factory  # noqa: SLF001
    factory.configure("logs_parametric")
    factory.pull()

    client = get_docker_client().networks.create(name="reuse_smoke_net", driver="bridge")
    try:
        api, stop = factory.start_agent(
            request=request,
            worker_id="gw0",
            container_name="ddapm-test-agent-reuse-smoke",
            docker_network=client.name,
            agent_env={},
            container_otlp_http_port=DEFAULT_OTLP_HTTP_PORT,
            container_otlp_grpc_port=DEFAULT_OTLP_GRPC_PORT,
        )
        try:
            assert api.info()["version"] == "test"  # agent answered → it is ready
        finally:
            stop()
    finally:
        client.remove()

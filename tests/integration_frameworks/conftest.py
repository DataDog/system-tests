from collections.abc import Generator
from pathlib import Path
from typing import TextIO

import pytest

from utils.integration_frameworks import (
    FrameworkTestClient,
    _TestAgentAPI,
)


from utils import context, scenarios, logger

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    import uuid

    result = str(uuid.uuid4())[0:6]
    logger.info(f"Test {request.node.nodeid} ID: {result}")
    return result


@pytest.fixture
def library_env() -> dict[str, str]:
    return {}


@pytest.fixture
def test_server_log_file(request: pytest.FixtureRequest) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
    request.node.add_report_section(
        "teardown", f"{context.library.name.capitalize()} Library Output", f"Log file:\n./{log_path}"
    )


@pytest.fixture
def docker_network(test_id: str) -> Generator[str, None, None]:
    network = scenarios.integration_frameworks.create_docker_network(test_id)

    try:
        yield network.name
    finally:
        try:
            network.remove()
        except:
            # It's possible (why?) of having some container not stopped.
            # If it happens, failing here makes stdout tough to understand.
            # Let's ignore this, later calls will clean the mess
            logger.info("Failed to remove network, ignoring the error")


@pytest.fixture
def test_agent_port() -> int:
    """Returns the port exposed inside the agent container"""
    return 8126


@pytest.fixture
def test_agent_log_file(request: pytest.FixtureRequest) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/agent_log.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
    request.node.add_report_section("teardown", "Test Agent Output", f"Log file:\n./{log_path}")


@pytest.fixture
def test_agent_container_name(test_id: str) -> str:
    return f"ddapm-test-agent-{test_id}"


@pytest.fixture
def test_agent_hostname(test_agent_container_name: str) -> str:
    return test_agent_container_name


@pytest.fixture
def test_agent_otlp_http_port() -> int:
    return 4318


@pytest.fixture
def test_agent_otlp_grpc_port() -> int:
    return 4317


@pytest.fixture
def test_agent(
    worker_id: str,
    docker_network: str,
    request: pytest.FixtureRequest,
    test_agent_container_name: str,
    test_agent_port: int,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
    test_agent_log_file: TextIO,
) -> Generator[_TestAgentAPI, None, None]:
    with scenarios.integration_frameworks.test_agent_factory.get_agent(
        worker_id=worker_id,
        docker_network=docker_network,
        request=request,
        test_agent_container_name=test_agent_container_name,
        test_agent_port=test_agent_port,
        test_agent_otlp_http_port=test_agent_otlp_http_port,
        test_agent_otlp_grpc_port=test_agent_otlp_grpc_port,
        test_agent_log_file=test_agent_log_file,
    ) as result:
        yield result


@pytest.fixture
def test_client(
    request: pytest.FixtureRequest,
    library_env: dict[str, str],
    test_id: str,
    worker_id: str,
    docker_network: str,
    test_agent_port: int,
    test_agent_container_name: str,
    test_server_log_file: TextIO,
) -> Generator[FrameworkTestClient, None, None]:
    scenarios.integration_frameworks.parametrized_tests_metadata[request.node.nodeid] = dict(library_env)

    framework_test_server = scenarios.integration_frameworks.test_client_factory
    with framework_test_server.get_client(
        library_env=library_env,
        worker_id=worker_id,
        test_id=test_id,
        test_agent_container_name=test_agent_container_name,
        test_agent_port=test_agent_port,
        log_file=test_server_log_file,
        network=docker_network,
    ) as client:
        yield client

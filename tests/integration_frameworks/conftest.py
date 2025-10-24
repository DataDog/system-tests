from collections.abc import Generator
import os
from pathlib import Path
import time
from typing import TextIO

import pytest

from utils.integration_frameworks import (
    FrameworkTestContainer,
    FrameworkTestClient,
    _TestAgentAPI,
    docker_run,
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


def _request_token(request: pytest.FixtureRequest) -> str:
    token = ""
    token += request.module.__name__
    token += f".{request.cls.__name__}" if request.cls else ""
    token += f".{request.node.name}"
    return token


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
    env = {}
    if os.getenv("DEV_MODE") is not None:
        env["SNAPSHOT_CI"] = "0"

    # (meta_tracer_version_header) Not all clients (go for example) submit the tracer version
    # (trace_content_length) go client doesn't submit content length header
    env["ENABLED_CHECKS"] = "trace_count_header"
    env["OTLP_HTTP_PORT"] = str(test_agent_otlp_http_port)
    env["OTLP_GRPC_PORT"] = str(test_agent_otlp_grpc_port)

    # vcr environment variables
    env["VCR_CASSETTES_DIRECTORY"] = "/vcr-cassettes"

    client = _TestAgentAPI(
        scenarios.integration_frameworks.host_log_folder, "localhost", worker_id=worker_id, pytest_request=request
    )

    with docker_run(
        image=scenarios.integration_frameworks.TEST_AGENT_IMAGE,
        name=test_agent_container_name,
        command=[],
        env=env,
        volumes={
            f"{Path.cwd()!s}/snapshots": "/snapshots",
            f"{Path.cwd()!s}/tests/integration_frameworks/utils/vcr-cassettes": "/vcr-cassettes",
        },
        ports={f"{test_agent_port}/tcp": client.agent_port},
        log_file=test_agent_log_file,
        network=docker_network,
    ):
        time.sleep(0.2)  # initial wait time, the trace agent takes 200ms to start
        for _ in range(100):
            try:
                resp = client.info()
            except Exception as e:
                logger.debug(f"Wait for 0.1s for the test agent to be ready {e}")
                time.sleep(0.1)
            else:
                if resp["version"] != "test":
                    message = f"""Agent version {resp['version']} is running instead of the test agent.
                    Stop the agent on port {test_agent_port} and try again."""
                    pytest.fail(message, pytrace=False)

                logger.info("Test agent is ready")
                break
        else:
            logger.error("Could not connect to test agent")
            pytest.fail(
                f"Could not connect to test agent, check the log file {test_agent_log_file.name}.", pytrace=False
            )

        # If the snapshot mark is on the test case then do a snapshot test
        marks = [m for m in request.node.iter_markers(name="snapshot")]
        assert len(marks) < 2, "Multiple snapshot marks detected"
        if marks:
            snap = marks[0]
            assert len(snap.args) == 0, "only keyword arguments are supported by the snapshot decorator"
            if "token" not in snap.kwargs:
                snap.kwargs["token"] = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")
            with client.snapshot_context(**snap.kwargs):
                yield client
        else:
            yield client


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

    framework_test_server = scenarios.integration_frameworks.framework_test_server_definition
    container: FrameworkTestContainer = framework_test_server.get_container(
        worker_id=worker_id,
        test_id=test_id,
        test_agent_container_name=test_agent_container_name,
        test_agent_port=test_agent_port,
    )

    # overwrite env with the one provided by the test
    container.environment |= library_env

    with container.run(log_file=test_server_log_file, network=docker_network) as client:
        yield client

import base64
from collections.abc import Generator
import dataclasses
import shutil
import subprocess
from pathlib import Path
from typing import TextIO

import pytest
import yaml

from utils.parametric._library_client import APMLibrary, APMLibraryClient

from utils import context, scenarios, logger

from utils._context._scenarios.parametric import APMLibraryTestServer
from utils.docker_fixtures._test_agent import TestAgentAPI as _TestAgentAPI

# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    import uuid

    result = str(uuid.uuid4())[0:6]
    logger.info(f"Test {request.node.nodeid} ID: {result}")
    return result


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


@pytest.fixture
def library_env() -> dict[str, str]:
    return {}


@pytest.fixture
def library_extra_command_arguments() -> list[str]:
    return []


@pytest.fixture
def apm_test_server(
    request: pytest.FixtureRequest,
    library_env: dict[str, str],
    library_extra_command_arguments: list[str],
    test_id: str,
) -> APMLibraryTestServer:
    """Request level definition of the library test server with the session Docker image built"""
    apm_test_server_image = scenarios.parametric.apm_test_server_definition
    new_env = dict(library_env)
    scenarios.parametric.parametrized_tests_metadata[request.node.nodeid] = new_env

    new_env.update(apm_test_server_image.env)

    command = apm_test_server_image.container_cmd

    if len(library_extra_command_arguments) > 0:
        if apm_test_server_image.lang not in ("nodejs", "java", "php"):
            # TODO : all test server should call directly the target without using a sh script
            command += library_extra_command_arguments
        else:
            # temporary workaround for the test server to be able to run the command
            new_env["SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS"] = " ".join(library_extra_command_arguments)

    return dataclasses.replace(
        apm_test_server_image,
        container_name=f"{apm_test_server_image.container_name}-{test_id}",
        env=new_env,
    )


@pytest.fixture
def test_server_log_file(
    apm_test_server: APMLibraryTestServer, request: pytest.FixtureRequest
) -> Generator[TextIO, None, None]:
    log_path = f"{context.scenario.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w+", encoding="utf-8") as f:
        yield f
    request.node.add_report_section(
        "teardown", f"{apm_test_server.lang.capitalize()} Library Output", f"Log file:\n./{log_path}"
    )


@pytest.fixture(scope="session")
def docker() -> str | None:
    """Fixture to ensure docker is ready to use on the system."""
    # Redirect output to /dev/null since we just care if we get a successful response code.
    r = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=default_subprocess_run_timeout,
        check=False,
    )
    if r.returncode != 0:
        pytest.exit(
            "Docker is not running and is required to run the shared APM library tests. Start docker and try running the tests again.",
            returncode=1,
        )
    return shutil.which("docker")


@pytest.fixture
def test_agent_otlp_http_port() -> int:
    return 4318


@pytest.fixture
def test_agent_otlp_grpc_port() -> int:
    return 4317


@pytest.fixture
def test_agent(
    worker_id: str,
    test_id: str,
    request: pytest.FixtureRequest,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> Generator[_TestAgentAPI, None, None]:
    with scenarios.parametric.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
        container_otlp_http_port=test_agent_otlp_http_port,
        container_otlp_grpc_port=test_agent_otlp_grpc_port,
    ) as result:
        yield result


@pytest.fixture
def test_library(
    worker_id: str,
    test_agent: _TestAgentAPI,
    apm_test_server: APMLibraryTestServer,
    test_server_log_file: TextIO,
) -> Generator[APMLibrary, None, None]:
    env = {
        "DD_TRACE_DEBUG": "true",
        "DD_TRACE_AGENT_URL": f"http://{test_agent.container_name}:{test_agent.container_port}",
        "DD_AGENT_HOST": test_agent.container_name,
        "DD_TRACE_AGENT_PORT": str(test_agent.container_port),
        "APM_TEST_CLIENT_SERVER_PORT": str(apm_test_server.container_port),
        "DD_TRACE_OTEL_ENABLED": "true",
    }

    for k, v in apm_test_server.env.items():
        # Don't set env vars with a value of None
        if v is not None:
            env[k] = v
        elif k in env:
            del env[k]

    apm_test_server.host_port = scenarios.parametric.get_host_port(worker_id, 4500)

    with scenarios.parametric.docker_run(
        image=apm_test_server.container_tag,
        name=apm_test_server.container_name,
        command=apm_test_server.container_cmd,
        env=env,
        ports={f"{apm_test_server.container_port}/tcp": apm_test_server.host_port},
        volumes=apm_test_server.volumes,
        log_file=test_server_log_file,
        network=test_agent.network,
    ) as container:
        apm_test_server.container = container

        test_server_timeout = 60

        if apm_test_server.host_port is None:
            raise RuntimeError("Internal error, no port has been assigned", 1)

        client = APMLibraryClient(
            f"http://localhost:{apm_test_server.host_port}", test_server_timeout, apm_test_server.container
        )

        tracer = APMLibrary(client, apm_test_server.lang)
        yield tracer


class StableConfigWriter:
    def write_stable_config(self, stable_config: dict, path: str, test_library: APMLibrary) -> None:
        stable_config_content = yaml.dump(stable_config)
        self.write_stable_config_content(stable_config_content, path, test_library)

    def write_stable_config_content(self, stable_config_content: str, path: str, test_library: APMLibrary) -> None:
        # Base64 encode the YAML content to avoid shell issues
        encoded = base64.b64encode(stable_config_content.encode()).decode()

        # Now execute the shell command to decode and write to the file
        cmd = f'bash -c "mkdir -p {Path(path).parent!s} && echo {encoded} | base64 -d > {path}"'

        if test_library.lang == "php":
            cmd = "sudo " + cmd
        success, message = test_library.container_exec_run(cmd)
        assert success, message

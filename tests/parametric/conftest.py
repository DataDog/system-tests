import base64
from collections.abc import Generator
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from utils.parametric._library_client import APMLibrary

from utils import scenarios, logger

from utils.docker_fixtures import TestAgentAPI as _TestAgentAPI

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
    request: pytest.FixtureRequest,
    test_id: str,
    test_agent: _TestAgentAPI,
    library_env: dict[str, str],
    library_extra_command_arguments: list[str],
) -> Generator[APMLibrary, None, None]:
    scenarios.parametric.parametrized_tests_metadata[request.node.nodeid] = library_env

    with scenarios.parametric.get_apm_library(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
        test_agent=test_agent,
        library_env=library_env,
        library_extra_command_arguments=library_extra_command_arguments,
    ) as result:
        yield result


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

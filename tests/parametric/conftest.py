import base64
from collections.abc import Generator
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest
import yaml

from utils import scenarios, logger
from utils.docker_fixtures import TestAgentAPI, ParametricTestClientApi as APMLibrary


# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
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
def agent_env() -> dict[str, str]:
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


@pytest.fixture(scope="session")
def test_agent_pool(worker_id: str):
    # scope="session" under pytest-xdist == once per worker.
    pool = scenarios.parametric.get_agent_pool(worker_id)
    yield pool
    pool.shutdown()


@pytest.fixture
def test_agent(
    worker_id: str,
    test_id: str,
    request: pytest.FixtureRequest,
    agent_env: dict[str, str],
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
    test_agent_pool,
) -> Generator[TestAgentAPI, None, None]:
    # POC: pool only default-agent_env, non-snapshot tests. Snapshot-marked tests need
    # per-test snapshot_context lifecycle; non-default agent_env would require a second
    # pooled agent per worker (worker-keyed host ports would collide). Both fall back to
    # the fresh-per-test path. Pooled agents are reset with clear() between tests.
    poolable = request.node.get_closest_marker("snapshot") is None and not agent_env
    if poolable:
        api = test_agent_pool.acquire(request=request, agent_env=agent_env)
        api.clear()  # ensure a clean slate even on the very first acquire
        yield api
        return  # REQUIRED: do not fall through into the fresh-path agent below

    with scenarios.parametric.get_test_agent_api(
        request=request,
        worker_id=worker_id,
        test_id=test_id,
        agent_env=agent_env,
        container_otlp_http_port=test_agent_otlp_http_port,
        container_otlp_grpc_port=test_agent_otlp_grpc_port,
    ) as result:
        yield result


@pytest.fixture
def test_library(
    worker_id: str,
    request: pytest.FixtureRequest,
    test_id: str,
    test_agent: TestAgentAPI,
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


# dd_* keys whose canonical telemetry name is not simply the upper-cased key. The tracer
# reports the canonical name (e.g. DD_TRACE_LOG_LEVEL); DD_LOG_LEVEL is only an alias.
_TELEMETRY_NAME_OVERRIDES = {"dd_log_level": "DD_TRACE_LOG_LEVEL"}


def _telemetry_name(dd_key: str) -> str:
    return _TELEMETRY_NAME_OVERRIDES.get(dd_key, dd_key.upper())


def nodejs_telemetry_value(test_agent: TestAgentAPI, dd_key: str) -> str | int | float | bool | None:
    """Return the effective nodejs telemetry value for a dd_* config key.

    dd-trace-js builds /trace/config from internal property paths that a series of config
    PRs is renaming to canonical names; the telemetry keeps reporting the stable canonical
    names, so asserting there stays decoupled from those refactors. The effective value is
    the highest-seq_id entry (already sorted first).
    """
    name = _telemetry_name(dd_key)
    configuration_by_name = test_agent.wait_for_telemetry_configurations()
    entries = configuration_by_name.get(name)
    assert entries, f"No telemetry configuration '{name}'"
    return entries[0].get("value")


def assert_nodejs_telemetry_config(test_agent: TestAgentAPI, expected: dict) -> None:
    """Assert expected dd_* config values against the nodejs telemetry configuration."""
    configuration_by_name = test_agent.wait_for_telemetry_configurations()
    for dd_key, expected_value in expected.items():
        name = _telemetry_name(dd_key)
        entries = configuration_by_name.get(name)
        assert entries, f"No telemetry configuration '{name}'"
        actual = entries[0].get("value")
        if dd_key == "dd_tags":
            actual_tags = "" if actual is None else str(actual)
            expected_tags = expected_value if isinstance(expected_value, list) else str(expected_value).split(",")
            for tag in expected_tags:
                assert tag in actual_tags, f"Expected tag '{tag}' not found in telemetry tags: {actual_tags}"
        else:
            assert str(actual).lower() == str(expected_value).lower(), f"Expected {name}={expected_value}, got {actual}"


def nodejs_startup_config(test_library: APMLibrary) -> dict:
    """Parse the tracer's published `DATADOG TRACER CONFIGURATION - {json}` startup line.

    Some facts have no telemetry signal: an unreachable agent never delivers telemetry (so the
    resolved agent URL is unobservable that way), and OTEL_LOG_LEVEL=debug toggles debug logging
    without a DD_TRACE_DEBUG telemetry entry. The startup diagnostic is a published, user-facing
    log line that carries them, so it is the non-internal source for those cases.
    """
    marker = "DATADOG TRACER CONFIGURATION - "
    for line in test_library.get_logs().splitlines():
        index = line.find(marker)
        if index != -1:
            return json.loads(line[index + len(marker) :])
    raise AssertionError("No 'DATADOG TRACER CONFIGURATION' line found in container logs")

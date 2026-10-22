"""Reusable mocked backend implementations for system-test scenarios."""

from collections.abc import Generator
import pytest

from utils.docker_fixtures._core import get_host_port

from .backend_v2 import MockedBackendServer


@pytest.fixture
def mocked_backend(worker_id: str) -> Generator[MockedBackendServer, None, None]:
    port = get_host_port(worker_id, 4900)
    server = MockedBackendServer(port=port)
    try:
        yield server
    finally:
        server.close()

"""Shared fixtures for generic and signal-specific OTLP protocol selection."""

import pytest

from utils import context
from utils.docker_fixtures import TestAgentAPI


def _non_default_protocol(signal: str) -> str:
    """An uppercase transport distinguishable from this SDK's default."""
    if context.library == "nodejs" or (context.library == "php" and signal == "logs"):
        return "HTTP/JSON"
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "HTTP/PROTOBUF"
    return "GRPC"


def _default_protocol(signal: str) -> str:
    # OTel permits retaining a historical gRPC default. These defaults are
    # published by the SDKs; never derive the expectation from the tested input.
    if context.library in ("python", "rust") or (context.library == "dotnet" and signal == "logs"):
        return "grpc"
    if context.library == "golang" and signal == "logs":
        return "http/json"
    return "http/protobuf"


@pytest.fixture
def protocol(request: pytest.FixtureRequest, signal: str) -> str:
    value = _non_default_protocol(signal)
    return value.lower() if getattr(request, "param", None) == "nondefault" else value


@pytest.fixture
def generic_protocol(request: pytest.FixtureRequest, signal: str) -> str | None:
    selection = getattr(request, "param", None)
    if selection == "nondefault":
        return _non_default_protocol(signal).lower()
    if selection == "default":
        return _default_protocol(signal)
    return None


@pytest.fixture
def expected_protocol(generic_protocol: str | None, protocol: str | None, signal: str) -> str:
    if generic_protocol and not protocol:
        return generic_protocol
    if protocol and protocol != "unsupported":
        return protocol.lower()
    return _default_protocol(signal)


# The test matrix supplies the protocol value to exercise protocol selection.
# Default cases leave it unset; the endpoint selects the expected HTTP/gRPC
# listener so delivery proves the transport, including SDKs that default to gRPC.
# Use the generic endpoint so each SDK derives its HTTP or gRPC signal path.
@pytest.fixture
def library_env(
    protocol_variable: str,
    generic_protocol: str | None,
    protocol: str | None,
    signal: str,
    expected_protocol: str,
    test_agent: TestAgentAPI,
    test_agent_otlp_http_port: int,
    test_agent_otlp_grpc_port: int,
) -> dict[str, str | None]:
    port = test_agent_otlp_grpc_port if expected_protocol == "grpc" else test_agent_otlp_http_port
    env: dict[str, str | None] = {
        f"DD_{signal.upper()}_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://{test_agent.container_name}:{port}",
        protocol_variable: protocol,
    }
    if generic_protocol is not None:
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = generic_protocol
    return env

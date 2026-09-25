"""Shared helpers for generic and signal-specific OTLP protocol selection."""

from utils import context


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


def protocol(selection: str | None, signal: str) -> str:
    value = _non_default_protocol(signal)
    return value.lower() if selection == "nondefault" else value


def generic_protocol(selection: str | None, signal: str) -> str | None:
    if selection == "nondefault":
        return _non_default_protocol(signal).lower()
    if selection == "default":
        return _default_protocol(signal)
    return None


def expected_protocol(generic_protocol: str | None, protocol: str | None, signal: str) -> str:
    if generic_protocol and not protocol:
        return generic_protocol
    if protocol and protocol != "unsupported":
        return protocol.lower()
    return _default_protocol(signal)

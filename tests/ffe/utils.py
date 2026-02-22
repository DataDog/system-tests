"""FFE test utilities for handling both RC paths (tracer and backend)."""

from utils import remote_config as rc
from utils._context.core import context
from utils._remote_config import _RemoteConfigState
from utils.proxy.mocked_response import StaticJsonMockedTracerResponse, MockedBackendResponse


def get_ffe_rc_state() -> _RemoteConfigState:
    """Get appropriate RC state based on scenario (tracer or backend).

    Follows the same pattern as send_debugger_command() in _remote_config.py:
    target = "backend" if context.scenario.rc_backend_enabled else "tracer"

    Returns:
        tracer_rc_state for tracer scenarios (rc_backend_enabled=False)
        backend_rc_state for backend scenarios (rc_backend_enabled=True)

    """
    if context.scenario.rc_backend_enabled:
        return rc.backend_rc_state
    return rc.tracer_rc_state


def get_rc_config_path() -> str:
    """Get RC config endpoint path based on scenario.

    Returns:
        "/api/v0.1/configurations" for backend scenarios
        "/v0.7/config" for tracer scenarios

    """
    if context.scenario.rc_backend_enabled:
        return "/api/v0.1/configurations"
    return "/v0.7/config"


def mock_rc_unavailable() -> None:
    """Mock RC service as unavailable (503) for appropriate path.

    Uses MockedBackendResponse for backend scenarios (protobuf),
    StaticJsonMockedTracerResponse for tracer scenarios (JSON).
    """
    if context.scenario.rc_backend_enabled:
        MockedBackendResponse(
            path="/api/v0.1/configurations",
            content=b"",
            status_code=503,
        ).send()
    else:
        StaticJsonMockedTracerResponse(
            path="/v0.7/config",
            mocked_json={"error": "Service Unavailable"},
            status_code=503,
        ).send()


def restore_rc() -> None:
    """Restore normal RC behavior by clearing the mock."""
    if context.scenario.rc_backend_enabled:
        MockedBackendResponse(path="/api/v0.1/configurations", content=b"").send()
    else:
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()


def wait_for_rc_error(data: dict, status_code: int = 503) -> bool:
    """Wait condition for RC error response, path-aware.

    Args:
        data: The request/response data from the interface
        status_code: Expected HTTP status code (default 503)

    Returns:
        True if the data matches an RC error response on the correct path

    """
    path = get_rc_config_path()
    return data["path"] == path and data["response"]["status_code"] == status_code

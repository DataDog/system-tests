"""Assertions for serverless-sidecar-preferred and direct-fallback telemetry."""

from collections.abc import Callable
from typing import cast

from utils import context
from utils.docker_fixtures._mock_ffe_agentless_backend import EXPECTED_API_KEY
from utils.interfaces._feature_flag_telemetry import FeatureFlagTelemetryInterfaceValidator

from .fixtures import JSON


TELEMETRY_WAIT_TIMEOUT_SECONDS = 30
UNEXPECTED_ROUTE_WAIT_SECONDS = 2


def telemetry_interface() -> FeatureFlagTelemetryInterfaceValidator:
    interface = getattr(context.scenario, "telemetry_interface", None)
    assert isinstance(interface, FeatureFlagTelemetryInterfaceValidator), (
        f"Scenario {context.scenario.name} does not define a Feature Flags telemetry route"
    )
    return interface


def telemetry_route() -> str:
    route = getattr(context.scenario, "telemetry_route", None)
    assert route in ("sidecar", "direct"), f"Scenario {context.scenario.name} has no telemetry route"
    return route


def wait_for_telemetry(matcher: Callable[[JSON], bool], description: str) -> None:
    assert telemetry_interface().wait_for(
        lambda data: matcher(cast("JSON", data)), timeout=TELEMETRY_WAIT_TIMEOUT_SECONDS
    ), f"Timed out waiting for {description} through {telemetry_route()} telemetry"


def matching_telemetry(matcher: Callable[[JSON], bool]) -> list[JSON]:
    return [cast("JSON", data) for data in telemetry_interface().get_data() if matcher(cast("JSON", data))]


def assert_expected_telemetry_route(matcher: Callable[[JSON], bool], description: str) -> None:
    captured = matching_telemetry(matcher)
    assert captured, f"No {description} captured through {telemetry_route()} telemetry"

    if telemetry_route() == "direct":
        for data in captured:
            assert _request_header(data, "dd-api-key") == EXPECTED_API_KEY, (
                f"Direct {description} must carry the configured Datadog API key"
            )

    unexpected = getattr(context.scenario, "unexpected_telemetry_interface", None)
    assert isinstance(unexpected, FeatureFlagTelemetryInterfaceValidator)
    if unexpected.replay:
        duplicated = any(matcher(cast("JSON", data)) for data in unexpected.get_data())
    else:
        duplicated = unexpected.wait_for(
            lambda data: matcher(cast("JSON", data)), timeout=UNEXPECTED_ROUTE_WAIT_SECONDS
        )
    assert not duplicated, f"{description} was duplicated through the non-selected telemetry route"


def _request_header(data: JSON, name: str) -> str | None:
    request = data.get("request")
    if not isinstance(request, dict):
        return None

    headers = request.get("headers")
    if not isinstance(headers, list):
        return None

    for header in headers:
        if isinstance(header, list) and len(header) == 2 and str(header[0]).lower() == name.lower():
            return str(header[1])
        if isinstance(header, tuple) and len(header) == 2 and str(header[0]).lower() == name.lower():
            return str(header[1])

    return None

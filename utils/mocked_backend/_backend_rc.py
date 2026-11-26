"""Remote config backend, polled by the agent. Like the real backend, it serves no config by default: a test sends one
with ``mocked_backend.client.set_mocked_responses(...)``, which takes precedence over these routes.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
import threading

from ._utils import CONTROL_URL_PREFIX
from .rc_capabilities import CapabilityRoutingFixture

from utils.proxy.rc_response_builder import (
    build_org_data_protobuf,
    build_org_status_protobuf,
    build_rc_configurations_protobuf,
)


if TYPE_CHECKING:
    from collections.abc import Mapping
    from utils.mocked_backend._request_handler import HttpMethod, MockedBackendRequestHandler, MockedBackendServerCore

    _Base = MockedBackendServerCore
else:
    _Base = object


class MockedBackendServerRcMixin(_Base):
    # Endpoint contract:
    # - GET /api/v0.1/org
    # - GET /api/v0.1/status
    # - GET /api/v0.2/echo-test
    # - POST /api/v0.1/configurations

    def _rc_configure(self) -> None:
        self._rc_routing: CapabilityRoutingFixture | None = None
        self._rc_lock = threading.Lock()
        self.add_handler("POST", f"{CONTROL_URL_PREFIX}/rc/capability-routing", self._rc_publish)
        self.add_handler("GET", f"{CONTROL_URL_PREFIX}/rc/capability-routing", self._rc_status)
        self._rc_add_static_handler("GET", "/api/v0.1/org", build_org_data_protobuf(), "application/x-protobuf")
        self._rc_add_static_handler("GET", "/api/v0.1/status", build_org_status_protobuf(), "application/x-protobuf")
        self._rc_add_static_handler("GET", "/api/v0.2/echo-test", b"ok", "text/plain")
        self.add_handler("POST", "/api/v0.1/configurations", self._rc_poll)

    def _rc_publish(
        self, request: MockedBackendRequestHandler, payload: bytes | dict | None
    ) -> tuple[Mapping[str, Any], bytes]:
        if (
            not isinstance(payload, dict)
            or set(payload) != {"base", "dependent"}
            or not all(isinstance(value, dict) for value in payload.values())
        ):
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "Expected base and dependent configurations"})
        with self._rc_lock:
            if self._rc_routing is not None:
                return request.write_json(HTTPStatus.CONFLICT, {"error": "Configurations are already published"})
            self._rc_routing = CapabilityRoutingFixture(payload["base"], payload["dependent"])
        return request.write_json(HTTPStatus.OK, self._rc_routing.status())

    def _rc_status(
        self, request: MockedBackendRequestHandler, _: bytes | dict | None
    ) -> tuple[Mapping[str, Any], bytes]:
        return request.write_json(HTTPStatus.OK, self._rc_routing.status() if self._rc_routing else {})

    def _rc_poll(self, request: MockedBackendRequestHandler, payload: bytes | dict | None) -> tuple[bytes, bytes]:
        if self._rc_routing is None:
            content = build_rc_configurations_protobuf(None)
        else:
            if not isinstance(payload, dict):
                raise ValueError("Expected a decoded LatestConfigsRequest")
            content = self._rc_routing.respond(payload.get("active_clients", []))
        request.send_response(HTTPStatus.OK)
        request.send_header("Content-Type", "application/x-protobuf")
        return content, content

    def _rc_add_static_handler(self, method: HttpMethod, path: str, content: bytes, content_type: str) -> None:
        def handler(request: MockedBackendRequestHandler, _: bytes | dict | None) -> tuple[bytes, bytes]:
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", content_type)
            return content, content

        self.add_handler(method, path, handler)

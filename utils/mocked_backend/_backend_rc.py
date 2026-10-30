"""Remote config backend, polled by the agent. Like the real backend, it serves no config by default: a test sends one
with ``mocked_backend.client.set_mocked_responses(...)``, which takes precedence over these routes.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from utils.proxy.rc_response_builder import (
    build_org_data_protobuf,
    build_org_status_protobuf,
    build_rc_configurations_protobuf,
)


if TYPE_CHECKING:
    from utils.mocked_backend._request_handler import HttpMethod, MockBackendV2RequestHandler, MockedBackendServerCore

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
        self._rc_add_static_handler("GET", "/api/v0.1/org", build_org_data_protobuf(), "application/x-protobuf")
        self._rc_add_static_handler("GET", "/api/v0.1/status", build_org_status_protobuf(), "application/x-protobuf")
        self._rc_add_static_handler("GET", "/api/v0.2/echo-test", b"ok", "text/plain")
        self._rc_add_static_handler(
            "POST", "/api/v0.1/configurations", build_rc_configurations_protobuf(None), "application/x-protobuf"
        )

    def _rc_add_static_handler(self, method: HttpMethod, path: str, content: bytes, content_type: str) -> None:
        def handler(request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[bytes, bytes]:
            request.send_response(HTTPStatus.OK)
            request.send_header("Content-Type", content_type)
            return content, content

        self.add_handler(method, path, handler)

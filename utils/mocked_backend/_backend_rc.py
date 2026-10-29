"""Remote configuration for agentless clients: without an agent to relay it, the library's native RC client polls
the backend directly. Tests push the configuration with ``mocked_backend.client.rc_set_configurations(...)``, and
every poll gets the last one pushed.

The mocked backend only serves the bytes it is given: it signs nothing (its image has no TUF signing dependency).
A configuration is built and signed on the test runner side, e.g. with
``utils.proxy.rc_response_builder.build_rc_configurations_protobuf``.
"""

from __future__ import annotations

import base64
import binascii
from http import HTTPStatus
import threading
from typing import TYPE_CHECKING

from ._utils import CONTROL_URL_PREFIX


if TYPE_CHECKING:
    from collections.abc import Mapping

    from utils.mocked_backend._request_handler import MockBackendV2RequestHandler, MockedBackendServerCore

    _Base = MockedBackendServerCore
else:
    _Base = object

RC_CONFIGURATIONS_PATH = "/api/v0.1/configurations"
RC_CONTROL_PATH = f"{CONTROL_URL_PREFIX}/remote-config"


class MockedBackendServerRcMixin(_Base):
    def _rc_configure(self) -> None:
        self._rc_lock = threading.Lock()
        # until a test pushes one, an empty LatestConfigsResponse (all its fields are optional)
        self._rc_configurations = b""

        self.add_handler("POST", RC_CONFIGURATIONS_PATH, self._rc_handle_configurations)
        self.add_handler("POST", RC_CONTROL_PATH, self._rc_handle_control)

    def _rc_handle_configurations(
        self, request: MockBackendV2RequestHandler, _: bytes | dict | None
    ) -> tuple[bytes, bytes]:
        with self._rc_lock:
            body = self._rc_configurations

        request.send_response(HTTPStatus.OK)
        request.send_header("Content-Type", "application/x-protobuf")
        return body, body

    def _rc_handle_control(
        self, request: MockBackendV2RequestHandler, payload: bytes | dict | None
    ) -> tuple[Mapping, bytes]:
        if not isinstance(payload, dict) or not isinstance(payload.get("configurations"), str):
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "control body must contain configurations"})

        try:
            configurations = base64.b64decode(payload["configurations"], validate=True)
        except binascii.Error:
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "configurations must be base64"})

        with self._rc_lock:
            self._rc_configurations = configurations

        return request.write_json(HTTPStatus.OK, {})

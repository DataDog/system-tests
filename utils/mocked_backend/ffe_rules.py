"""Protobuf configuration endpoint for standalone server-side FFE helpers."""

from __future__ import annotations

import base64
from http import HTTPStatus
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from utils.docker_fixtures._core import get_host_port
from utils.mocked_backend.backend_v2 import MockBackendV2RequestHandler, MockBackendV2Server

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

# Shared portable protobuf fixture from openfeature-js-client's interoperability tests.
WIRE_FIXTURE = json.loads((Path(__file__).parents[2] / "tests/parametric/test_ffe/rules-wire.json").read_text())
CONFIG_PATH = "/api/v2/feature-flagging/config/rules-based"
RESPONSE_SECRET = "private-response-body"  # noqa: S105 - dummy body used to detect error-message leakage
BODY_PHASE_DELAY_SECONDS = 1.5


class MockFFERulesRequestHandler(MockBackendV2RequestHandler):
    server: MockFFERulesBackendServer

    def end_headers(self) -> None:
        response = self.server.response
        if response == "disconnect":
            self.connection.shutdown(socket.SHUT_RDWR)
            return

        super().end_headers()
        if response == "delayed_body":
            time.sleep(BODY_PHASE_DELAY_SECONDS)
        elif response == "truncated_body":
            self.wfile.write(RESPONSE_SECRET.encode())
            self.connection.shutdown(socket.SHUT_RDWR)


class MockFFERulesBackendServer(MockBackendV2Server):
    thread_name = "mock-ffe-rules-backend"

    def __init__(self, *, worker_id: str = "master", port: int | None = None) -> None:
        self.response = "valid"
        self._requests: list[dict[str, Any]] = []
        self._requests_lock = threading.Lock()
        super().__init__(port=get_host_port(worker_id, 4950) if port is None else port)
        self.RequestHandlerClass = MockFFERulesRequestHandler
        for channel in ("client", "server"):
            self.add_handler("GET", f"{CONFIG_PATH}/{channel}", self.handle_config)
        self.add_handler("GET", "/redirected", self.handle_config)

    @property
    def library_base_url(self) -> str:
        host = os.environ.get("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_HOST", "host.docker.internal")
        return f"http://{host}:{self.port}"

    @property
    def requests(self) -> list[dict[str, Any]]:
        with self._requests_lock:
            return list(self._requests)

    def handle_config(
        self, request: MockBackendV2RequestHandler, _: bytes | dict | None
    ) -> tuple[Mapping | bytes, bytes]:
        with self._requests_lock:
            self._requests.append(
                {"path": request.path, "headers": {key.lower(): value for key, value in request.headers.items()}}
            )
        status = HTTPStatus.OK
        headers = {"Content-Type": "application/protobuf", "ETag": WIRE_FIXTURE["rules"]["etag"]}
        body = base64.b64decode(WIRE_FIXTURE["rules"]["response"])
        if self.response == "delayed":
            time.sleep(4)
        elif self.response == "delayed_body":
            # Each phase fits within the test's deadline, but their combined duration does not.
            time.sleep(BODY_PHASE_DELAY_SECONDS)
        elif self.response in {"forbidden", "server_error"}:
            status = HTTPStatus.FORBIDDEN if self.response == "forbidden" else HTTPStatus.INTERNAL_SERVER_ERROR
            body = RESPONSE_SECRET.encode()
        elif self.response == "redirect":
            status = HTTPStatus.FOUND
            headers["Location"] = f"{self.library_base_url}/redirected"
        elif self.response == "malformed":
            body = b"\xff"
        elif self.response == "empty":
            body = b""
        elif self.response == "wrong_content_type":
            headers["Content-Type"] = "application/json"
            body = b"{}"
        elif self.response not in {"valid", "disconnect", "truncated_body"}:
            raise ValueError(f"Unknown rules response: {self.response}")

        request.send_response(status)
        for name, value in headers.items():
            request.send_header(name, value)
        return body, body


@pytest.fixture
def mock_ffe_rules_backend(worker_id: str) -> Generator[MockFFERulesBackendServer, None, None]:
    server = MockFFERulesBackendServer(worker_id=worker_id)
    try:
        yield server
    finally:
        server.close()

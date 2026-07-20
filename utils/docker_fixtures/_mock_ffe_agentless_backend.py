"""FFE UFC delivery fixture used to exercise agentless default configuration-source behavior.

Tests configure the response timeline with ``mock_ffe_agentless_backend.set_response(...)`` or
``mock_ffe_agentless_backend.set_responses([...])`` before starting the test library. They can
then call ``mock_ffe_agentless_backend.status()`` to assert request counts, auth, ETag, response
codes, and paths observed by the mock server.
"""

from __future__ import annotations

import contextlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import TYPE_CHECKING, Any, TypedDict, cast
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
import requests

from utils.docker_fixtures._core import get_host_port

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

VALID_RESPONSE_IDS = frozenset(
    {
        "valid",
        "unauthorized",
        "malformed",
        "not_modified",
        "server_error",
        "delayed_valid",
        "timeout",
    }
)
DEFAULT_RESPONSE = "valid"
UFC_ETAG = '"ufc-v1"'
EXPECTED_API_KEY = "system-tests-mock-api-key"
DELAYED_RESPONSE_SECONDS = 0.5
TIMEOUT_RESPONSE_SECONDS = 1.5
MAX_CONTROL_BODY_BYTES = 512
CONFIG_PATH = "/api/v2/feature-flagging/config/rules-based/server"
EXPECTED_DD_ENV = "test"
CONFIG_QUERY = urlencode({"dd_env": EXPECTED_DD_ENV})
REPO_ROOT = Path(__file__).parents[2]
UFC_FIXTURE_PATH = REPO_ROOT / "tests" / "parametric" / "test_ffe" / "ffe-system-test-data" / "ufc-config.json"
MALFORMED_UFC_BYTES = b'{"flags": ['
UFC_RESPONSE_TYPE = "universal-flag-configuration"


class MockFFEAgentlessBackendStatus(TypedDict):
    requests_total: int
    in_flight: int
    max_in_flight: int
    last_path: str | None
    last_if_none_match: str | None
    last_auth_present: bool
    last_status_code: int | None
    status_codes: list[int]


class MockFFEAgentlessBackendState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.responses = [DEFAULT_RESPONSE]
        self.requests_total = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.last_path: str | None = None
        self.last_if_none_match: str | None = None
        self.last_auth_present = False
        self.last_status_code: int | None = None
        self.status_codes: list[int] = []

    def reset(self) -> None:
        with self._lock:
            self.responses = [DEFAULT_RESPONSE]
            self.requests_total = 0
            self.in_flight = 0
            self.max_in_flight = 0
            self.last_path = None
            self.last_if_none_match = None
            self.last_auth_present = False
            self.last_status_code = None
            self.status_codes = []

    def set_responses(self, responses: object) -> None:
        validated_responses = validate_responses(responses)
        with self._lock:
            self.responses = list(validated_responses)
            self.last_if_none_match = None
            self.last_status_code = None
            self.status_codes = []

    def record_request(self, headers: Mapping[str, str], path: str) -> str:
        parsed = urlparse(path)
        normalized_headers = {key.lower(): value for key, value in headers.items()}

        with self._lock:
            self.requests_total += 1
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            self.last_path = parsed.path
            self.last_if_none_match = normalized_headers.get("if-none-match")
            self.last_auth_present = _has_auth(headers)
            response = self.responses[0]
            if len(self.responses) > 1:
                self.responses.pop(0)
            return response

    def record_response(self, status_code: int) -> None:
        with self._lock:
            self.last_status_code = status_code
            self.status_codes.append(status_code)

    def finish_request(self) -> None:
        with self._lock:
            self.in_flight = max(0, self.in_flight - 1)

    def status(self) -> MockFFEAgentlessBackendStatus:
        with self._lock:
            return {
                "requests_total": self.requests_total,
                "in_flight": self.in_flight,
                "max_in_flight": self.max_in_flight,
                "last_path": self.last_path,
                "last_if_none_match": self.last_if_none_match,
                "last_auth_present": self.last_auth_present,
                "last_status_code": self.last_status_code,
                "status_codes": list(self.status_codes),
            }


class MockFFEAgentlessBackendHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, MockFFEAgentlessBackendRequestHandler)
        self.state = MockFFEAgentlessBackendState()


class MockFFEAgentlessBackendRequestHandler(BaseHTTPRequestHandler):
    # Endpoint contract:
    # - GET /api/v2/feature-flagging/config/rules-based/server?dd_env=test
    # - GET /status
    # - POST /control/responses
    # - POST /control/reset
    server: MockFFEAgentlessBackendHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == CONFIG_PATH and parse_qs(parsed.query, keep_blank_values=True) == {
            "dd_env": [EXPECTED_DD_ENV]
        }:
            self._handle_config()
            return
        if parsed.path == "/status":
            self._write_json(HTTPStatus.OK, self.server.state.status())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/control/responses":
            self._handle_responses_control()
            return
        if path == "/control/reset":
            self.server.state.reset()
            self._write_json(HTTPStatus.OK, self.server.state.status())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _handle_config(self) -> None:
        request_headers = dict(self.headers)
        response = self.server.state.record_request(request_headers, self.path)
        try:
            if response in {"delayed_valid", "timeout"}:
                time.sleep(TIMEOUT_RESPONSE_SECONDS if response == "timeout" else DELAYED_RESPONSE_SECONDS)

            status_code, body, headers = _response_for_response(
                response=response,
                has_auth=_has_auth(request_headers),
            )
            self.server.state.record_response(status_code)
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                self.send_response(status_code)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                if body:
                    self.wfile.write(body)
        finally:
            self.server.state.finish_request()

    def _handle_responses_control(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > MAX_CONTROL_BODY_BYTES:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "control body too large"})
            return

        try:
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid control JSON"})
            return

        if not isinstance(payload, dict) or set(payload) != {"responses"}:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "control body must contain only responses"})
            return

        responses = payload["responses"]
        try:
            validated_responses = validate_responses(responses)
        except ValueError as error:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        self.server.state.set_responses(validated_responses)
        self._write_json(HTTPStatus.OK, self.server.state.status())

    def _write_json(self, status_code: HTTPStatus, payload: dict[str, Any] | MockFFEAgentlessBackendStatus) -> None:
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))


def _has_auth(headers: Mapping[str, str]) -> bool:
    normalized = {key.lower(): value for key, value in headers.items()}
    return normalized.get("dd-api-key") == EXPECTED_API_KEY


def _valid_ufc_bytes() -> bytes:
    attributes = json.loads(UFC_FIXTURE_PATH.read_text())
    return json.dumps(
        {
            "data": {
                "id": "1",
                "type": UFC_RESPONSE_TYPE,
                "attributes": attributes,
            }
        }
    ).encode("utf-8")


def validate_responses(responses: object) -> list[str]:
    if not isinstance(responses, list) or not responses:
        raise ValueError("responses must be a non-empty list")

    if any(not isinstance(response, str) for response in responses):
        raise ValueError("responses must contain only strings")

    unknown_responses = sorted({response for response in responses if response not in VALID_RESPONSE_IDS})
    if unknown_responses:
        raise ValueError(f"unknown response: {', '.join(unknown_responses)}")

    return responses


def _response_for_response(response: str, *, has_auth: bool) -> tuple[int, bytes, dict[str, str]]:
    if not has_auth:
        return HTTPStatus.UNAUTHORIZED, b"", {}

    if response == "unauthorized":
        return HTTPStatus.UNAUTHORIZED, b"", {}
    if response == "malformed":
        return HTTPStatus.OK, MALFORMED_UFC_BYTES, {"Content-Type": "application/json"}
    if response == "not_modified":
        return HTTPStatus.NOT_MODIFIED, b"", {"ETag": UFC_ETAG}
    if response == "server_error":
        return HTTPStatus.INTERNAL_SERVER_ERROR, b"", {}
    return HTTPStatus.OK, _valid_ufc_bytes(), {"Content-Type": "application/json", "ETag": UFC_ETAG}


def _strip_config_path(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.path.endswith(CONFIG_PATH):
        return url

    base_path = parsed.path.removesuffix(CONFIG_PATH).rstrip("/")
    return parsed._replace(path=base_path, params="", query="", fragment="").geturl().rstrip("/")


class MockFFEAgentlessBackendServer:
    def __init__(self, worker_id: str, *, port: int | None = None) -> None:
        self.port = get_host_port(worker_id, 4900) if port is None else port
        self._server = MockFFEAgentlessBackendHTTPServer(("0.0.0.0", self.port))  # noqa: S104 - test fixture must be container-reachable.
        self.port = self._server.server_port
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="mock-ffe-agentless-backend", daemon=True
        )
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def library_base_url(self) -> str:
        configured_url = os.environ.get("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_BASE_URL") or os.environ.get(
            "SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_BASE_URL"
        )
        if configured_url is not None:
            return _strip_config_path(configured_url.rstrip("/"))

        host = os.environ.get("SYSTEM_TESTS_MOCK_FFE_AGENTLESS_BACKEND_HOST") or os.environ.get(
            "SYSTEM_TESTS_MOCK_AGENTLESS_BACKEND_HOST", "host.docker.internal"
        )
        return f"http://{host}:{self.port}"

    @property
    def library_config_url(self) -> str:
        return f"{self.library_base_url}{CONFIG_PATH}?{CONFIG_QUERY}"

    def reset(self) -> None:
        response = requests.post(f"{self.base_url}/control/reset", timeout=5)
        response.raise_for_status()

    def set_response(self, response_id: str) -> None:
        self.set_responses([response_id])

    def set_responses(self, responses: object) -> None:
        validated_responses = validate_responses(responses)
        response = requests.post(
            f"{self.base_url}/control/responses", json={"responses": validated_responses}, timeout=5
        )
        response.raise_for_status()

    def status(self) -> MockFFEAgentlessBackendStatus:
        response = requests.get(f"{self.base_url}/status", timeout=5)
        response.raise_for_status()
        return cast("MockFFEAgentlessBackendStatus", response.json())

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def mock_ffe_agentless_backend(worker_id: str) -> Generator[MockFFEAgentlessBackendServer, None, None]:
    server = MockFFEAgentlessBackendServer(worker_id)
    try:
        server.reset()
        yield server
    finally:
        server.close()

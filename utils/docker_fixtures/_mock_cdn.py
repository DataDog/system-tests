from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, ClassVar, TypedDict, cast
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from utils.docker_fixtures._core import get_host_port

FIXTURE_IDS = {
    "valid_control",
    "missing_auth_cold",
    "missing_auth_warm",
    "malformed_cold",
    "malformed_warm",
    "unchanged_etag_304",
    "explicit_source_mode",
    "delayed_no_overlap",
}
DEFAULT_FIXTURE = "valid_control"
UFC_ETAG = '"ufc-v1"'
DELAYED_RESPONSE_SECONDS = 0.5
MAX_CONTROL_BODY_BYTES = 512
REPO_ROOT = Path(__file__).parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "parametric" / "test_ffe" / "fixtures"


class MockCDNStatus(TypedDict):
    fixture: str
    requests_total: int
    in_flight: int
    max_in_flight: int
    last_if_none_match: str | None
    last_auth_present: bool
    last_source_mode: str | None
    last_status_code: int | None


class MockCDNState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.fixture = DEFAULT_FIXTURE
        self.requests_total = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.last_if_none_match: str | None = None
        self.last_auth_present = False
        self.last_source_mode: str | None = None
        self.last_status_code: int | None = None

    def reset(self) -> None:
        with self._lock:
            self.fixture = DEFAULT_FIXTURE
            self.requests_total = 0
            self.in_flight = 0
            self.max_in_flight = 0
            self.last_if_none_match = None
            self.last_auth_present = False
            self.last_source_mode = None
            self.last_status_code = None

    def set_fixture(self, fixture: str) -> None:
        with self._lock:
            if fixture not in FIXTURE_IDS:
                raise ValueError(f"unknown mock CDN fixture: {fixture}")
            self.fixture = fixture

    def record_request(self, headers: dict[str, str], path: str) -> str:
        parsed = urlparse(path)
        source_mode = headers.get("DD-Flagging-Source-Mode") or headers.get(
            "X-Datadog-Flagging-Source-Mode"
        )
        if source_mode is None:
            values = parse_qs(parsed.query).get("source_mode")
            source_mode = values[0] if values else None

        with self._lock:
            self.requests_total += 1
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            self.last_if_none_match = headers.get("If-None-Match")
            self.last_auth_present = _has_auth(headers)
            self.last_source_mode = source_mode
            return self.fixture

    def record_response(self, status_code: int) -> None:
        with self._lock:
            self.last_status_code = status_code

    def finish_request(self) -> None:
        with self._lock:
            self.in_flight = max(0, self.in_flight - 1)

    def status(self) -> MockCDNStatus:
        with self._lock:
            return {
                "fixture": self.fixture,
                "requests_total": self.requests_total,
                "in_flight": self.in_flight,
                "max_in_flight": self.max_in_flight,
                "last_if_none_match": self.last_if_none_match,
                "last_auth_present": self.last_auth_present,
                "last_source_mode": self.last_source_mode,
                "last_status_code": self.last_status_code,
            }


class MockCDNHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, MockCDNRequestHandler)
        self.state = MockCDNState()


class MockCDNRequestHandler(BaseHTTPRequestHandler):
    # Endpoint contract:
    # - GET /mock/ufc/config
    # - GET /status
    # - POST /control/fixture
    # - POST /control/reset
    server: ClassVar[MockCDNHTTPServer]

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/mock/ufc/config":
            self._handle_config()
            return
        if path == "/status":
            self._write_json(HTTPStatus.OK, self.server.state.status())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/control/fixture":
            self._handle_fixture_control()
            return
        if path == "/control/reset":
            self.server.state.reset()
            self._write_json(HTTPStatus.OK, self.server.state.status())
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _handle_config(self) -> None:
        fixture = self.server.state.record_request(dict(self.headers), self.path)
        try:
            if fixture == "delayed_no_overlap":
                time.sleep(DELAYED_RESPONSE_SECONDS)

            status_code, body, headers = _response_for_fixture(
                fixture=fixture,
                has_auth=_has_auth(dict(self.headers)),
                if_none_match=self.headers.get("If-None-Match"),
            )
            self.server.state.record_response(status_code)
            self.send_response(status_code)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            if body:
                self.wfile.write(body)
        finally:
            self.server.state.finish_request()

    def _handle_fixture_control(self) -> None:
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

        if not isinstance(payload, dict) or set(payload) != {"fixture"}:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "control body must contain only fixture"})
            return

        fixture = payload["fixture"]
        if not isinstance(fixture, str) or fixture not in FIXTURE_IDS:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "unknown fixture"})
            return

        self.server.state.set_fixture(fixture)
        self._write_json(HTTPStatus.OK, self.server.state.status())

    def _write_json(self, status_code: HTTPStatus, payload: dict[str, Any] | MockCDNStatus) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))


def _has_auth(headers: dict[str, str]) -> bool:
    return any(
        bool(headers.get(header))
        for header in ("DD-API-KEY", "X-Datadog-API-Key", "Authorization", "DD-Api-Key")
    )


def _fixture_bytes(filename: str) -> bytes:
    return (FIXTURE_DIR / filename).read_bytes()


def _response_for_fixture(fixture: str, has_auth: bool, if_none_match: str | None) -> tuple[int, bytes, dict[str, str]]:
    if fixture in {"missing_auth_cold", "missing_auth_warm"}:
        return HTTPStatus.UNAUTHORIZED, b"", {}

    if not has_auth:
        return HTTPStatus.UNAUTHORIZED, b"", {}

    if fixture == "unchanged_etag_304" and if_none_match == UFC_ETAG:
        return HTTPStatus.NOT_MODIFIED, b"", {"ETag": UFC_ETAG}

    if fixture in {"malformed_cold", "malformed_warm"}:
        return HTTPStatus.OK, _fixture_bytes("ufc_malformed.json"), {"Content-Type": "application/json"}

    return HTTPStatus.OK, _fixture_bytes("ufc_valid.json"), {"Content-Type": "application/json", "ETag": UFC_ETAG}


class MockCDNServer:
    def __init__(self, worker_id: str) -> None:
        self.port = get_host_port(worker_id, 4900)
        self._server = MockCDNHTTPServer(("0.0.0.0", self.port))
        self._thread = threading.Thread(target=self._server.serve_forever, name="mock-cdn", daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def library_base_url(self) -> str:
        host = os.environ.get("SYSTEM_TESTS_MOCK_CDN_HOST", "host.docker.internal")
        return f"http://{host}:{self.port}"

    def reset(self) -> None:
        response = requests.post(f"{self.base_url}/control/reset", timeout=5)
        response.raise_for_status()

    def set_fixture(self, fixture: str) -> None:
        response = requests.post(f"{self.base_url}/control/fixture", json={"fixture": fixture}, timeout=5)
        response.raise_for_status()

    def status(self) -> MockCDNStatus:
        response = requests.get(f"{self.base_url}/status", timeout=5)
        response.raise_for_status()
        return cast("MockCDNStatus", response.json())

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def mock_cdn(worker_id: str) -> Generator[MockCDNServer, None, None]:
    server = MockCDNServer(worker_id)
    try:
        server.reset()
        yield server
    finally:
        server.close()

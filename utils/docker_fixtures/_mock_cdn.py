from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import TYPE_CHECKING, Any, TypedDict, cast
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from utils.docker_fixtures._core import get_host_port

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

FIXTURE_IDS = {
    "valid_control",
    "missing_auth_cold",
    "missing_auth_warm",
    "malformed_cold",
    "malformed_warm",
    "unchanged_etag_304",
    "explicit_source_mode",
    "delayed_no_overlap",
    "bad_to_good",
    "bad_to_unchanged",
    "good_to_bad",
    "good_to_unchanged",
}
DEFAULT_FIXTURE = "valid_control"
UFC_ETAG = '"ufc-v1"'
EXPECTED_API_KEY = "system-tests-mock-api-key"
DELAYED_RESPONSE_SECONDS = 0.5
MAX_CONTROL_BODY_BYTES = 512
CONFIG_PATH = "/mock/ufc/config"
RETRYABLE_STATUS_CODE = 509
REPO_ROOT = Path(__file__).parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "parametric" / "test_ffe" / "fixtures"
RESPONSE_SEQUENCES = {
    "bad_to_good": (RETRYABLE_STATUS_CODE, HTTPStatus.OK),
    "bad_to_unchanged": (RETRYABLE_STATUS_CODE, HTTPStatus.NOT_MODIFIED),
    "good_to_bad": (HTTPStatus.OK, RETRYABLE_STATUS_CODE),
    "good_to_unchanged": (HTTPStatus.OK, HTTPStatus.NOT_MODIFIED),
}


class MockCDNStatus(TypedDict):
    fixture: str
    requests_total: int
    in_flight: int
    max_in_flight: int
    last_if_none_match: str | None
    last_auth_present: bool
    last_source_mode: str | None
    last_status_code: int | None
    status_codes: list[int]


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
        self.status_codes: list[int] = []
        self._sequence_index = 0

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
            self.status_codes = []
            self._sequence_index = 0

    def set_fixture(self, fixture: str) -> None:
        with self._lock:
            if fixture not in FIXTURE_IDS:
                raise ValueError(f"unknown mock CDN fixture: {fixture}")
            self.fixture = fixture
            self.last_if_none_match = None
            self.last_source_mode = None
            self.last_status_code = None
            self.status_codes = []
            self._sequence_index = 0

    def record_request(self, headers: Mapping[str, str], path: str) -> tuple[str, int]:
        parsed = urlparse(path)
        source_mode = headers.get("DD-Flagging-Source-Mode") or headers.get("X-Datadog-Flagging-Source-Mode")
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
            sequence_index = self._sequence_index
            self._sequence_index += 1
            return self.fixture, sequence_index

    def record_response(self, status_code: int) -> None:
        with self._lock:
            self.last_status_code = status_code
            self.status_codes.append(status_code)

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
                "status_codes": list(self.status_codes),
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
    server: MockCDNHTTPServer

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == CONFIG_PATH:
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

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _handle_config(self) -> None:
        fixture, sequence_index = self.server.state.record_request(dict(self.headers), self.path)
        try:
            if fixture == "delayed_no_overlap":
                time.sleep(DELAYED_RESPONSE_SECONDS)

            status_code, body, headers = _response_for_fixture(
                fixture=fixture,
                has_auth=_has_auth(self.headers),
                if_none_match=self.headers.get("If-None-Match"),
                sequence_index=sequence_index,
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


def _has_auth(headers: Mapping[str, str]) -> bool:
    normalized = {key.lower(): value for key, value in headers.items()}
    return any(normalized.get(header) == EXPECTED_API_KEY for header in ("dd-api-key", "x-datadog-api-key"))


def _fixture_bytes(filename: str) -> bytes:
    return (FIXTURE_DIR / filename).read_bytes()


def _response_for_fixture(
    fixture: str, *, has_auth: bool, if_none_match: str | None, sequence_index: int
) -> tuple[int, bytes, dict[str, str]]:
    if fixture in {"missing_auth_cold", "missing_auth_warm"}:
        return HTTPStatus.UNAUTHORIZED, b"", {}

    if not has_auth:
        return HTTPStatus.UNAUTHORIZED, b"", {}

    if fixture in RESPONSE_SEQUENCES:
        return _response_for_sequence(fixture, if_none_match, sequence_index)

    if fixture == "unchanged_etag_304" and if_none_match == UFC_ETAG:
        return HTTPStatus.NOT_MODIFIED, b"", {"ETag": UFC_ETAG}

    if fixture in {"malformed_cold", "malformed_warm"}:
        return HTTPStatus.OK, _fixture_bytes("ufc_malformed.json"), {"Content-Type": "application/json"}

    return HTTPStatus.OK, _fixture_bytes("ufc_valid.json"), {"Content-Type": "application/json", "ETag": UFC_ETAG}


def _response_for_sequence(
    fixture: str, if_none_match: str | None, sequence_index: int
) -> tuple[int, bytes, dict[str, str]]:
    sequence = RESPONSE_SEQUENCES[fixture]
    status_code = sequence[min(sequence_index, len(sequence) - 1)]

    if fixture == "good_to_unchanged" and status_code == HTTPStatus.NOT_MODIFIED and if_none_match != UFC_ETAG:
        status_code = HTTPStatus.OK

    if status_code == HTTPStatus.OK:
        return HTTPStatus.OK, _fixture_bytes("ufc_valid.json"), {"Content-Type": "application/json", "ETag": UFC_ETAG}

    if status_code == HTTPStatus.NOT_MODIFIED:
        return HTTPStatus.NOT_MODIFIED, b"", {"ETag": UFC_ETAG}

    return RETRYABLE_STATUS_CODE, b"", {"Retry-After": "0"}


def _strip_config_path(url: str) -> str:
    return url.removesuffix(CONFIG_PATH)


class MockCDNServer:
    def __init__(self, worker_id: str) -> None:
        self.port = get_host_port(worker_id, 4900)
        self._server = MockCDNHTTPServer(("0.0.0.0", self.port))  # noqa: S104 - test fixture must be container-reachable.
        self._thread = threading.Thread(target=self._server.serve_forever, name="mock-cdn", daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def library_base_url(self) -> str:
        configured_url = os.environ.get("SYSTEM_TESTS_MOCK_CDN_BASE_URL")
        if configured_url is not None:
            return _strip_config_path(configured_url.rstrip("/"))

        host = os.environ.get("SYSTEM_TESTS_MOCK_CDN_HOST", "host.docker.internal")
        return f"http://{host}:{self.port}"

    @property
    def library_config_url(self) -> str:
        return f"{self.library_base_url}{CONFIG_PATH}"

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

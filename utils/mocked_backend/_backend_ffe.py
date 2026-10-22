"""FFE UFC delivery fixture used to exercise agentless default configuration-source behavior.

Tests configure the response timeline with ``mocked_backend.set_response(...)`` or
``mocked_backend.set_responses([...])`` before starting the test library. They can
then call ``mocked_backend.status()`` to assert request counts, auth, ETag, response
codes, and paths observed by the mock server.
"""

from __future__ import annotations

import contextlib
from http import HTTPStatus
import json
import os
from pathlib import Path
import threading
import time
from typing import TYPE_CHECKING, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse

from ._utils import CONTROL_URL_PREFIX


if TYPE_CHECKING:
    from utils.mocked_backend._request_handler import MockBackendV2RequestHandler, MockedBackendServerCore
    from collections.abc import Mapping

    _Base = MockedBackendServerCore
else:
    _Base = object

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
DELAYED_RESPONSE_SECONDS = 1.5
TIMEOUT_RESPONSE_SECONDS = 1.5
MAX_CONTROL_BODY_BYTES = 512
CONFIG_PATH = "/api/v2/feature-flagging/config/rules-based/server"
EXPECTED_DD_ENV = "test"
CONFIG_QUERY = urlencode({"dd_env": EXPECTED_DD_ENV})
REPO_ROOT = Path(__file__).parents[2]
UFC_FIXTURE_PATH = REPO_ROOT / "tests" / "parametric" / "test_ffe" / "flags-v1.json"
MALFORMED_UFC_BYTES = b'{"flags": ['
UFC_RESPONSE_TYPE = "universal-flag-configuration"


class MockedBackendFFEStatus(TypedDict):
    requests_total: int
    in_flight: int
    max_in_flight: int
    last_path: str | None
    last_if_none_match: str | None
    observed_dd_api_key: str | None
    last_status_code: int | None
    status_codes: list[int]


class _MockedBackendFFEState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.responses = [DEFAULT_RESPONSE]
        self.requests_total = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.last_path: str | None = None
        self.last_if_none_match: str | None = None
        self.observed_dd_api_key: str | None = None
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
            self.observed_dd_api_key = None
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
            self.observed_dd_api_key = _get_dd_api_key(headers)
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

    def status(self) -> MockedBackendFFEStatus:
        with self._lock:
            return {
                "requests_total": self.requests_total,
                "in_flight": self.in_flight,
                "max_in_flight": self.max_in_flight,
                "last_path": self.last_path,
                "last_if_none_match": self.last_if_none_match,
                "observed_dd_api_key": self.observed_dd_api_key,
                "last_status_code": self.last_status_code,
                "status_codes": list(self.status_codes),
            }


def _get_dd_api_key(headers: Mapping[str, str]) -> str | None:
    normalized = {key.lower(): value for key, value in headers.items()}
    return normalized.get("dd-api-key")


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


def _response_for_response(response: str) -> tuple[int, bytes, dict[str, str]]:
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


class MockedBackendServerFfeMixin(_Base):
    # Endpoint contract:
    # - GET /api/v2/feature-flagging/config/rules-based/server?dd_env=test
    # - GET /system-tests/ffe/status
    # - POST /system-tests/ffe/responses
    # - POST /system-tests/ffe/reset

    def _ffe_configure(self) -> None:
        self._ffe_state = _MockedBackendFFEState()
        self._ffe_control_path = f"{CONTROL_URL_PREFIX}/ffe"

        self.add_handler("GET", CONFIG_PATH, self._ffe_handle_config)

        self.add_handler("GET", f"{self._ffe_control_path}/status", self._ffe_handle_status)
        self.add_handler("POST", f"{self._ffe_control_path}/responses", self._ffe_handle_control_responses)
        self.add_handler("POST", f"{self._ffe_control_path}/reset", self._ffe_handle_control_reset)

    @property
    def _ffe_library_base_url(self) -> str:
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
    def ffe_library_config_url(self) -> str:
        return f"{self._ffe_library_base_url}{CONFIG_PATH}?{CONFIG_QUERY}"

    def _ffe_handle_status(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, self._ffe_state.status())

    def _ffe_handle_config(
        self, request: MockBackendV2RequestHandler, _: bytes | dict | None
    ) -> tuple[Mapping | bytes, bytes]:
        parsed = urlparse(request.path)
        if parse_qs(parsed.query, keep_blank_values=True) == {"dd_env": [EXPECTED_DD_ENV]}:
            return self._ffe_handle_config_exec(request)

        return request.write_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def _ffe_handle_config_exec(self, request: MockBackendV2RequestHandler) -> tuple[bytes, bytes]:
        request_headers = dict(request.headers)
        response = self._ffe_state.record_request(request_headers, request.path)
        try:
            if response in {"delayed_valid", "timeout"}:
                time.sleep(TIMEOUT_RESPONSE_SECONDS if response == "timeout" else DELAYED_RESPONSE_SECONDS)

            status_code, body, headers = _response_for_response(response)
            self._ffe_state.record_response(status_code)
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                request.send_response(status_code)
                for key, value in headers.items():
                    request.send_header(key, value)

        finally:
            self._ffe_state.finish_request()

        return body, body

    def _ffe_handle_control_responses(
        self, request: MockBackendV2RequestHandler, payload: bytes | dict | None
    ) -> tuple[Mapping, bytes]:
        content_length = int(request.headers.get("Content-Length", "0"))
        if content_length > MAX_CONTROL_BODY_BYTES:
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "control body too large"})

        if not isinstance(payload, dict) or set(payload) != {"responses"}:
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "control body must contain only responses"})

        responses = payload["responses"]
        try:
            validated_responses = validate_responses(responses)
        except ValueError as error:
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        self._ffe_state.set_responses(validated_responses)
        return request.write_json(HTTPStatus.OK, self._ffe_state.status())

    def _ffe_handle_control_reset(
        self, request: MockBackendV2RequestHandler, _: bytes | dict | None
    ) -> tuple[Mapping, bytes]:
        self._ffe_state.reset()
        return request.write_json(HTTPStatus.OK, self._ffe_state.status())

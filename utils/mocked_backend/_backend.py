"""MockedBackendServer: the base class for every mocked HTTP backend, and, used as-is, the generic
mocked backend standing in for the real Datadog backend API used by ``interfaces.backend_v2``
(``utils/interfaces/_backend.py``).

Used directly, its only job is to record every request it receives into the interface's log folder
(``logs/interfaces/backend_v2``), the same way every other interface persists what it observes.
"""

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import ssl
import threading
from typing import TYPE_CHECKING

from ._request_handler import MockedBackendServerCore, MockBackendV2RequestHandler, HttpMethod, RouteHandler
from ._backend_ffe import MockedBackendServerFfeMixin
from ._client import MockedBackendClient
from ._utils import CONTROL_URL_PREFIX, HOST_DOCKER_INTERNAL, logger

# from utils/proxy, also mounted in the mocked backend container
from utils.proxy.mocked_response import MockedBackendResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class MockedBackendServer(MockedBackendServerFfeMixin, MockedBackendServerCore):
    """Base HTTP server for every mocked backend, and, used as-is, a local HTTP server standing in
    for the Datadog backend API: it binds on every interface (not just loopback) so containers can
    reach it through host.docker.internal, runs requests on daemon threads, starts itself on its
    own background thread, and records every request/response it receives into ``log_folder``.

    Subclasses that need different per-path behavior (see ``utils.mocked_backend.ffe``) pass their
    own ``request_handler_cls`` and override that handler's do_GET/do_POST/do_PUT.
    """

    _DEFAULT_PORT = 4900

    daemon_threads = True
    thread_name = "mock-backend-v2"

    def __init__(
        self,
        log_folder: str | None = None,
        on_message: Callable[[dict], None] | None = None,
        *,
        port: int = _DEFAULT_PORT,
        tls_cert_file: str | None = None,
        internal_mocked_responses_file: str | None = None,
    ) -> None:
        """With tls_cert_file (a certificate and its key), it serves HTTPS instead of HTTP: for senders that only speak
        HTTPS to the intake hostnames derived from DD_SITE.

        HTTPS is meant for the mocked backend container (MockedBackendContainer(tls=True)): the certificate covers its
        hostnames, not host.docker.internal, so the URLs this server advertises to containers can't be verified.
        """
        super().__init__(("0.0.0.0", port), MockBackendV2RequestHandler)  # noqa: S104
        self.scheme = "https" if tls_cert_file else "http"
        if tls_cert_file:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(tls_cert_file)
                # the handshake runs in each request thread, not in the accepting one: an idle client blocks nothing
                self.socket = context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)
            except Exception:
                # the caller never gets a server to close: release the port now
                self.server_close()
                raise
        self.log_folder = log_folder
        self.on_message = on_message if on_message else lambda _: None
        self.message_count = 0
        self._count_lock = threading.Lock()
        self._routes: dict[tuple[HttpMethod, str], RouteHandler] = {}
        self.port = self.server_port

        # Like the proxy (see utils/proxy/mocked_response.py): a request matching a mocked response gets it, runtime
        # ones (set by tests) first, then internal ones (set by the scenario, for the whole session)
        self._mocked_responses_lock = threading.Lock()
        self._mocked_responses: list[MockedBackendResponse] = []
        self._internal_mocked_responses: list[MockedBackendResponse] = []
        if internal_mocked_responses_file:
            data = json.loads(Path(internal_mocked_responses_file).read_text(encoding="utf-8"))
            self._internal_mocked_responses = MockedBackendResponse.from_dicts(data)

        self.add_handler("GET", f"{CONTROL_URL_PREFIX}/health", self._handle_health)
        self.add_handler("PUT", f"{CONTROL_URL_PREFIX}/mocked-responses", self._handle_mocked_responses)
        self._ffe_configure()

        self._thread = threading.Thread(target=self.serve_forever, name=self.thread_name, daemon=True)
        self._thread.start()
        logging_into = f"logging into {log_folder}" if log_folder else "not logging to disk"
        logger.debug(f"{self.thread_name} server started on {self.base_url}, {logging_into}")

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://127.0.0.1:{self.port}"

    @property
    def client(self) -> MockedBackendClient:
        """Client of the control endpoints of this server"""
        # over HTTPS, it only talks to itself on the loopback: nothing to verify
        return MockedBackendClient(self.base_url, verify=self.scheme == "http")

    @property
    def container_url(self) -> str:
        """The URL a container can use to reach the mock server on the docker host."""
        return f"{self.scheme}://{HOST_DOCKER_INTERNAL}:{self.port}"

    def add_handler(self, method: HttpMethod, path: str, handler: RouteHandler) -> None:
        """Register a handler for an exact (method, path) pair. ``path`` is matched without its
        query string; the handler is responsible for validating query params/headers/body itself
        (e.g. by writing a 404 through ``request._write_json`` when they don't match).
        """
        self._routes[(method, path)] = handler

    def get_handler(self, method: HttpMethod, path: str) -> tuple[RouteHandler, str | None, str | None]:
        handler = self._get_mocked_response_handler(path) or self._routes.get((method, path), self._default_handler)

        if path.startswith(CONTROL_URL_PREFIX):
            # requests controlling the mock are not traffic it stands in for: never record them
            return handler, None, None

        with self._count_lock:
            message_count = self.message_count
            self.message_count += 1

        if self.log_folder:
            log_filename = f"{self.log_folder}/{message_count:03d}_{path.replace('/', '_')}.json"
            export_content_files_to = f"{self.log_folder}/files"
        else:
            log_filename = None
            export_content_files_to = None

        return handler, log_filename, export_content_files_to

    def _get_mocked_response_handler(self, path: str) -> RouteHandler | None:
        if path.startswith(CONTROL_URL_PREFIX):
            return None

        with self._mocked_responses_lock:
            mocks = self._mocked_responses + self._internal_mocked_responses

        mock = next((mock for mock in mocks if mock.path == path), None)
        if mock is None:
            return None

        def handler(request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[bytes, bytes]:
            request.send_response(mock.status_code)
            request.send_header("Content-Type", mock.content_type)
            return mock.content, mock.content

        return handler

    def _handle_mocked_responses(
        self, request: MockBackendV2RequestHandler, payload: bytes | dict | None
    ) -> tuple[Mapping, bytes]:
        """Replace the runtime mocked responses, like the proxy's /mocked_backend_responses endpoint"""
        if not isinstance(payload, dict) or not isinstance(payload.get("responses"), list):
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": "body must contain a list of responses"})

        try:
            mocks = MockedBackendResponse.from_dicts(payload["responses"])
        except (KeyError, TypeError, ValueError) as error:
            return request.write_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})

        with self._mocked_responses_lock:
            self._mocked_responses = mocks

        return request.write_json(HTTPStatus.OK, {})

    def _handle_health(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, {"status": "ok"})

    def _default_handler(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, {})

    def close(self) -> None:
        logger.debug(f"Stopping {self.thread_name} server on {self.base_url}")
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

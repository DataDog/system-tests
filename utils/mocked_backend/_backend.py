"""MockedBackendServer: the base class for every mocked HTTP backend, and, used as-is, the generic
mocked backend standing in for the real Datadog backend API used by ``interfaces.backend_v2``
(``utils/interfaces/_backend.py``).

Used directly, its only job is to record every request it receives into the interface's log folder
(``logs/interfaces/backend_v2``), the same way every other interface persists what it observes.
"""

from __future__ import annotations

from http import HTTPStatus
import threading
from typing import TYPE_CHECKING

from ._request_handler import MockedBackendServerCore, MockBackendV2RequestHandler, HttpMethod, RouteHandler
from ._tls import TlsListener, create_server_ssl_context
from ._backend_ffe import MockedBackendServerFfeMixin
from ._client import MockedBackendClient
from ._utils import CONTROL_URL_PREFIX, HOST_DOCKER_INTERNAL, logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


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
        tls_port: int | None = None,
        tls_ca_file: str | None = None,
        tls_hostnames: Sequence[str] = (),
    ) -> None:
        """With tls_port, it also serves HTTPS on this port, for tls_hostnames, with a certificate signed by the CA in
        tls_ca_file: for clients that only speak HTTPS to hostnames derived from DD_SITE.
        """
        super().__init__(("0.0.0.0", port), MockBackendV2RequestHandler)  # noqa: S104
        self.log_folder = log_folder
        self.on_message = on_message if on_message else lambda _: None
        self.message_count = 0
        self._count_lock = threading.Lock()
        self._routes: dict[tuple[HttpMethod, str], RouteHandler] = {}
        self.port = self.server_port

        self.add_handler("GET", f"{CONTROL_URL_PREFIX}/health", self._handle_health)
        self._ffe_configure()

        self._thread = threading.Thread(target=self.serve_forever, name=self.thread_name, daemon=True)
        self._thread.start()

        self.tls_listener: TlsListener | None = None
        if tls_port is not None:
            assert tls_ca_file, "TLS requires a CA file"
            assert tls_hostnames, "TLS requires hostnames"
            ssl_context = create_server_ssl_context(tls_ca_file, tls_hostnames)
            self.tls_listener = TlsListener(self, tls_port, ssl_context)
            logger.debug(f"{self.thread_name} server serves {', '.join(tls_hostnames)} on {self.tls_listener.base_url}")
        logging_into = f"logging into {log_folder}" if log_folder else "not logging to disk"
        logger.debug(f"{self.thread_name} server started on {self.base_url}, {logging_into}")

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def client(self) -> MockedBackendClient:
        """Client of the control endpoints of this server"""
        return MockedBackendClient(self.base_url)

    @property
    def container_url(self) -> str:
        """The URL a container can use to reach the mock server on the docker host."""
        return f"http://{HOST_DOCKER_INTERNAL}:{self.port}"

    def add_handler(self, method: HttpMethod, path: str, handler: RouteHandler) -> None:
        """Register a handler for an exact (method, path) pair. ``path`` is matched without its
        query string; the handler is responsible for validating query params/headers/body itself
        (e.g. by writing a 404 through ``request._write_json`` when they don't match).
        """
        self._routes[(method, path)] = handler

    def get_handler(self, method: HttpMethod, path: str) -> tuple[RouteHandler, str | None, str | None]:
        handler = self._routes.get((method, path), self._default_handler)

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

    def _handle_health(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, {"status": "ok"})

    def _default_handler(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, {})

    def close(self) -> None:
        logger.debug(f"Stopping {self.thread_name} server on {self.base_url}")
        if self.tls_listener:
            self.tls_listener.close()
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

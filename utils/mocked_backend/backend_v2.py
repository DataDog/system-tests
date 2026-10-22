"""MockBackendV2Server: the base class for every mocked HTTP backend, and, used as-is, the generic
mocked backend standing in for the real Datadog backend API used by ``interfaces.backend_v2``
(``utils/interfaces/_backend_v2.py``).

Used directly, its only job is to record every request it receives into the interface's log folder
(``logs/interfaces/backend_v2``), the same way every other interface persists what it observes.
Other mocked backends (e.g. ``utils.mocked_backend.ffe``) extend it and pass their own
``request_handler_cls`` to add their own request handling.
"""

from __future__ import annotations

from http import HTTPStatus
import threading
from typing import TYPE_CHECKING

from utils._logger import logger
from utils.docker_fixtures._core import HOST_DOCKER_INTERNAL

from ._request_handler import MockBackendV2ServerHandlerInterface, MockBackendV2RequestHandler, HttpMethod, RouteHandler

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


class MockBackendV2Server(MockBackendV2ServerHandlerInterface):
    """Base HTTP server for every mocked backend, and, used as-is, a local HTTP server standing in
    for the Datadog backend API: it binds on every interface (not just loopback) so containers can
    reach it through host.docker.internal, runs requests on daemon threads, starts itself on its
    own background thread, and records every request/response it receives into ``log_folder``.

    Subclasses that need different per-path behavior (see ``utils.mocked_backend.ffe``) pass their
    own ``request_handler_cls`` and override that handler's do_GET/do_POST/do_PUT.
    """

    DEFAULT_PORT = 4900

    CONTROL_URL_PREFIX = "/system-tests"
    """Prefix of every endpoint that controls the mock rather than mimicking the real backend."""

    daemon_threads = True
    thread_name = "mock-backend-v2"

    def __init__(
        self,
        log_folder: str | None = None,
        on_message: Callable[[dict], None] | None = None,
        *,
        port: int = DEFAULT_PORT,
    ) -> None:
        super().__init__(("0.0.0.0", port), MockBackendV2RequestHandler)  # noqa: S104
        self.log_folder = log_folder
        self.on_message = on_message if on_message else lambda _: None
        self.message_count = 0
        self._count_lock = threading.Lock()
        self._routes: dict[tuple[HttpMethod, str], RouteHandler] = {}
        self.port = self.server_port
        self._thread = threading.Thread(target=self.serve_forever, name=self.thread_name, daemon=True)
        self._thread.start()
        logging_into = f"logging into {log_folder}" if log_folder else "not logging to disk"
        logger.debug(f"{self.thread_name} server started on {self.base_url}, {logging_into}")

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

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
        with self._count_lock:
            message_count = self.message_count
            self.message_count += 1

        if self.log_folder:
            log_filename = f"{self.log_folder}/{message_count:03d}_{path.replace('/', '_')}.json"
            export_content_files_to = f"{self.log_folder}/files"
        else:
            log_filename = None
            export_content_files_to = None

        return self._routes.get((method, path), self._default_handler), log_filename, export_content_files_to

    def _default_handler(self, request: MockBackendV2RequestHandler, _: bytes | dict | None) -> tuple[Mapping, bytes]:
        return request.write_json(HTTPStatus.OK, {})

    def close(self) -> None:
        logger.debug(f"Stopping {self.thread_name} server on {self.base_url}")
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

"""Generic mocked backend (v2): stands in for the real Datadog backend API used by
``interfaces.backend_v2`` (``utils/interfaces/_backend_v2.py``).

Its only job is to record every request it receives into the interface's log folder
(``logs/interfaces/backend_v2``), the same way every other interface persists what it observes.
"""

from __future__ import annotations

import gzip
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import traceback
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
import zlib

import brotli
import zstandard

from utils._logger import logger
from utils.docker_fixtures._core import HOST_DOCKER_INTERNAL, get_host_port
from utils.proxy._deserializer import deserialize

if TYPE_CHECKING:
    from collections.abc import Callable


def _decode_content(raw_body: bytes, content_encoding: str) -> bytes:
    """Undo the request's Content-Encoding, mirroring utils.proxy.core.get_decoded_content()
    (mitmproxy applies the same decoding transparently for the proxy interface).
    """
    content_encoding = content_encoding.lower()
    if content_encoding == "gzip":
        return gzip.decompress(raw_body)
    if content_encoding == "deflate":
        return zlib.decompress(raw_body)
    if content_encoding == "br":
        return brotli.decompress(raw_body)
    if content_encoding == "zstd":
        # stream_reader().read() consumes every concatenated frame, unlike decompress(),
        # which only decodes the first one (see utils.proxy.core.get_decoded_content).
        return zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw_body)).read()
    return raw_body


_PORT_BASE = 4901


def get_mocked_backend_v2_port(worker_id: str = "master") -> int:
    """The port MockBackendV2Server listens on, computable ahead of starting it (e.g. to
    configure a container's environment before the server is actually running).
    """
    return get_host_port(worker_id, _PORT_BASE)


def get_mocked_backend_v2_container_url(worker_id: str = "master") -> str:
    """The URL a container can use to reach the mock server on the docker host."""
    return f"http://{HOST_DOCKER_INTERNAL}:{get_mocked_backend_v2_port(worker_id)}"


class MockBackendV2Server:
    """A local HTTP server standing in for the Datadog backend API."""

    def __init__(
        self,
        log_folder: str,
        worker_id: str = "master",
        on_message: Callable[[dict], None] | None = None,
        *,
        port: int | None = None,
    ) -> None:
        self.port = get_mocked_backend_v2_port(worker_id) if port is None else port
        # Bind on every interface, not just loopback, so containers can reach it through
        # host.docker.internal.
        self._server = _MockBackendV2HTTPServer(("0.0.0.0", self.port), log_folder, on_message)  # noqa: S104
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, name="mock-backend-v2", daemon=True)
        self._thread.start()
        logger.debug(f"Mocked backend v2 server started on {self.base_url}, logging into {log_folder}")

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def close(self) -> None:
        logger.debug(f"Stopping mocked backend v2 server on {self.base_url}")
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class _MockBackendV2HTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self, server_address: tuple[str, int], log_folder: str, on_message: Callable[[dict], None] | None
    ) -> None:
        super().__init__(server_address, _MockBackendV2RequestHandler)
        self.log_folder = log_folder
        self.on_message = on_message
        self.message_count = 0
        self._count_lock = threading.Lock()


class _MockBackendV2RequestHandler(BaseHTTPRequestHandler):
    server: _MockBackendV2HTTPServer

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _handle(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        path_without_query = urlsplit(self.path).path

        with self.server._count_lock:  # noqa: SLF001
            message_count = self.server.message_count
            self.server.message_count += 1

        log_filename = f"{self.server.log_folder}/{message_count:03d}_{path_without_query.replace('/', '_')}.json"

        data: dict[str, Any] = {
            "log_filename": log_filename,
            "method": self.command,
            "path": path_without_query,
            "request": {"headers": list(self.headers.items())},
        }
        try:
            content = _decode_content(raw_body, self.headers.get("Content-Encoding", "")) if raw_body else None
        except Exception:
            data["request"]["raw_content"] = repr(raw_body)
            data["request"]["traceback"] = traceback.format_exc()
        else:
            deserialize(
                data,
                key="request",
                content=content,
                interface="agent",
                export_content_files_to=f"{self.server.log_folder}/files",
            )

        response_payload: dict[str, Any] = {}
        data["response"] = {
            "status_code": int(HTTPStatus.OK),
            "headers": [("Content-Type", "application/json")],
            "content": response_payload,
        }

        logger.debug(f"Mocked backend v2 received {self.command} {self.path}, logging into {log_filename}")
        with open(log_filename, mode="w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=repr)

        if self.server.on_message is not None:
            self.server.on_message(data)

        self._write_json(HTTPStatus.OK, response_payload)

    def _write_json(self, status_code: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

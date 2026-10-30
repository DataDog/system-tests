from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
import contextlib
from datetime import UTC, datetime
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import traceback
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit
import zlib

import brotli
import zstandard

from utils.proxy._deserializer import deserialize

from ._utils import CONTROL_URL_PREFIX, logger


if TYPE_CHECKING:
    from http import HTTPStatus


RouteHandler = Callable[["MockBackendV2RequestHandler", bytes | dict | None], tuple[list | Mapping | bytes, bytes]]
HttpMethod = Literal["GET", "POST", "PUT"]


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
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw_body)) as reader:
            return reader.read()
    return raw_body


# We need to do some shenanigans to avoid circular import:
#
# * MockBackendV2RequestHandler needs to know MockedBackendV2Server
# * MockedBackendV2Server needs to know MockBackendV2RequestHandler
#
# So we extract the part of MockedBackendV2Server that needs to be known by MockBackendV2RequestHandler
# in this "core" class
class MockedBackendServerCore(ABC, ThreadingHTTPServer):
    on_message: Callable[[dict], None]
    port: int
    scheme: str

    @abstractmethod
    def get_handler(
        self, method: HttpMethod, path: str, *, query: str = ""
    ) -> tuple[RouteHandler, str | None, str | None]: ...

    @abstractmethod
    def add_handler(self, method: HttpMethod, path: str, handler: RouteHandler) -> None: ...

    @property
    @abstractmethod
    def base_url(self) -> str: ...


class MockBackendV2RequestHandler(BaseHTTPRequestHandler):
    server: MockedBackendServerCore
    _data: dict  # use to store request and response info
    # Routes can delay or interrupt body delivery after headers and request logging.
    before_response_body: Callable[[], None] | None = None

    # catch response events
    def send_response(self, code: int, message: str | None = None) -> None:
        if hasattr(self, "_data"):
            self._data["response"]["status_code"] = code
        return super().send_response(code, message)

    def send_header(self, keyword: str, value: str) -> None:
        if hasattr(self, "_data"):
            self._data["response"]["headers"].append((keyword, value))
        return super().send_header(keyword, value)

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def write_json(self, status_code: HTTPStatus, payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], bytes]:
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")

        return payload, json.dumps(payload).encode("utf-8")

    def do_GET(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def _handle(self, method: HttpMethod) -> None:
        timestamp_start = datetime.now(UTC).isoformat()
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        url_parts = urlsplit(self.path)
        path = url_parts.path

        handler, log_filename, export_content_files_to = self.server.get_handler(method, path, query=url_parts.query)

        self._data: dict[str, Any] = {
            "log_filename": log_filename,
            "method": self.command,
            "path": path,
            # like the proxy
            "query": url_parts.query,
            "request": {"timestamp_start": timestamp_start, "headers": list(self.headers.items())},
            "response": {"headers": []},
        }

        content = None

        try:
            content = _decode_content(raw_body, self.headers.get("Content-Encoding", "")) if raw_body else None
        except Exception:
            self._data["request"]["raw_content"] = repr(raw_body)
            self._data["request"]["traceback"] = traceback.format_exc()
        else:
            deserialize(
                self._data,
                key="request",
                content=content,
                interface="agent",
                export_content_files_to=export_content_files_to,
            )

        response, response_as_bytes = handler(self, self._data["request"].get("content", content))

        self._data["response"]["content"] = str(response) if isinstance(response, bytes) else response

        logger.info(f"{self.command} {self.path} -> handled by {handler}: {self._data['response'].get('status_code')}")

        if log_filename:
            with open(log_filename, mode="w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=repr)

        if not path.startswith(CONTROL_URL_PREFIX):
            self.server.on_message(self._data)

        # we need to send data AFTER we wrote the file
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.send_header("Content-Length", str(len(response_as_bytes)))
            self.end_headers()
            if self.before_response_body is not None:
                self.before_response_body()
            self.wfile.write(response_as_bytes)

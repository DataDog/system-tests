from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
import contextlib
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

from utils._logger import logger
from utils.proxy._deserializer import deserialize


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

    @abstractmethod
    def get_handler(self, method: HttpMethod, path: str) -> tuple[RouteHandler, str | None, str | None]: ...


class MockBackendV2RequestHandler(BaseHTTPRequestHandler):
    server: MockedBackendServerCore
    _data: dict  # use to store request and response info

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
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        url_parts = urlsplit(self.path)
        path = url_parts.path

        handler, log_filename, export_content_files_to = self.server.get_handler(method, path)

        self._data: dict[str, Any] = {
            "log_filename": log_filename,
            "method": self.command,
            "path": path,
            "request": {"headers": list(self.headers.items())},
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

        logger.debug(f"Mocked backend v2 received {self.command} {self.path}, logging into {log_filename}")

        if log_filename:
            with open(log_filename, mode="w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=repr)

        self.server.on_message(self._data)

        # we need to send data AFTER we wrote the file
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.send_header("Content-Length", str(len(response_as_bytes)))
            self.end_headers()
            self.wfile.write(response_as_bytes)

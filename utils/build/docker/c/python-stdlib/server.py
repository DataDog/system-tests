from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import urllib.error
import urllib.parse
import urllib.request


PORT = 7777
LIBRARY_VERSION_FILE = Path("/opt/datadog/apm/library/c/version")
OBSERVED_HEADERS_RESPONSE_HEADER = "X-System-Tests-Observed-Request-Headers"


class DualStackThreadingHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "system-tests-python-stdlib"

    def _request_headers(self) -> dict[str, str]:
        return {name.lower(): value for name, value in self.headers.items()}

    def _request_body(self) -> bytes:
        content_length = int(self.headers.get("content-length", "0"))
        return self.rfile.read(content_length) if content_length else b""

    def _send(
        self,
        status: int,
        body: bytes = b"",
        *,
        content_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        observed_headers = json.dumps(self._request_headers(), separators=(",", ":"))
        self.send_header(OBSERVED_HEADERS_RESPONSE_HEADER, observed_headers)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD" and body:
            self.wfile.write(body)

    def _send_json(self, value: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(value, separators=(",", ":")).encode()
        self._send(status, body, content_type="application/json")

    @staticmethod
    def _outbound_request(
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str], dict[str, str]]:
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=10)  # noqa: S310
        except urllib.error.HTTPError as error:
            response = error

        with response:
            response_body = response.read()
            response_headers = {name.lower(): value for name, value in response.headers.items()}
            raw_observed_headers = response.headers.get(OBSERVED_HEADERS_RESPONSE_HEADER, "{}")
            observed_headers = json.loads(raw_observed_headers)
            if not isinstance(observed_headers, dict):
                observed_headers = {}
            return response.status, response_body, response_headers, observed_headers

    def _make_distant_call(self, query: dict[str, list[str]]) -> None:
        if "url" not in query:
            self._send_json({"error": "url query parameter is required"}, HTTPStatus.BAD_REQUEST)
            return

        url = query["url"][0]
        status, _, response_headers, observed_headers = self._outbound_request(url)
        self._send_json(
            {
                "url": url,
                "status_code": status,
                "request_headers": observed_headers,
                "response_headers": response_headers,
            }
        )

    def _external_request(self, parsed_url: urllib.parse.ParseResult, body: bytes) -> None:
        query = urllib.parse.parse_qs(parsed_url.query)
        status = query.pop("status", ["200"])[0]
        url_extra = query.pop("url_extra", [""])[0]
        target = f"http://internal_server:8089/mirror/{status}{url_extra}"
        headers = {name: values[0] for name, values in query.items()}
        if content_type := self.headers.get("content-type"):
            headers["content-type"] = content_type

        try:
            downstream_status, downstream_body, downstream_headers, _ = self._outbound_request(
                target,
                method=self.command,
                body=body or None,
                headers=headers,
            )
            payload = json.loads(downstream_body) if downstream_body else None
            self._send_json({"status": downstream_status, "payload": payload, "headers": downstream_headers})
        except Exception as error:  # noqa: BLE001
            self._send_json({"status": None, "error": str(error)})

    def _external_redirect(self, query: dict[str, list[str]]) -> None:
        redirect_count = query.get("totalRedirects", ["0"])[0]
        target = f"http://internal_server:8089/redirect?totalRedirects={urllib.parse.quote(redirect_count)}"
        try:
            self._outbound_request(target)
            self._send_json({"status": HTTPStatus.OK})
        except Exception as error:  # noqa: BLE001
            self._send_json({"status": None, "error": str(error)})

    def _handle(self) -> None:
        body = self._request_body()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/healthcheck":
            version = LIBRARY_VERSION_FILE.read_text(encoding="utf-8").strip()
            self._send_json({"status": "ok", "library": {"name": "c", "version": version}})
        elif path == "/headers":
            self._send(
                HTTPStatus.OK,
                b"Hello headers!\n",
                content_type="text",
                headers={"Content-Language": "en-US"},
            )
        elif path.startswith("/params/") or path.startswith("/sample_rate_route/"):
            self._send(HTTPStatus.OK, b"Hello world!\n")
        elif path == "/status":
            self._send(int(query.get("code", ["200"])[0]))
        elif path.rstrip("/") == "/returnheaders":
            self._send_json(self._request_headers())
        elif path == "/read_file":
            requested_file = query.get("file", [""])[0]
            if requested_file != "/proc/self/cgroup":
                self._send_json({"error": "file is not allowed"}, HTTPStatus.BAD_REQUEST)
                return
            self._send(HTTPStatus.OK, Path(requested_file).read_bytes())
        elif path == "/requestdownstream":
            _, downstream_body, _, _ = self._outbound_request("http://127.0.0.1:7777/returnheaders")
            self._send(HTTPStatus.OK, downstream_body, content_type="application/json")
        elif path == "/make_distant_call":
            self._make_distant_call(query)
        elif path == "/external_request/redirect":
            self._external_redirect(query)
        elif path == "/external_request":
            self._external_request(parsed_url, body)
        elif path in ("/", "/spans", "/waf"):
            self._send(HTTPStatus.OK, b"Hello world!\n")
        else:
            self._send(HTTPStatus.NOT_FOUND, b"Not found\n")

    do_DELETE = _handle
    do_GET = _handle
    do_HEAD = _handle
    do_OPTIONS = _handle
    do_PATCH = _handle
    do_POST = _handle
    do_PUT = _handle
    do_TRACE = _handle


def main() -> None:
    server = DualStackThreadingHTTPServer(("::", PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()

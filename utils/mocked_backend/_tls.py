"""TLS listener of the mocked backend: for clients that only speak HTTPS to hostnames derived from DD_SITE (e.g. an
SDK sending exposures directly to the intake). It serves the same routes, and records into the same folder, as the
plain HTTP server it is attached to.

tls/mock-intake.pem holds a certificate and its key for these hostnames, signed by the mitmproxy CA, which these
clients trust. To add a hostname, regenerate it:

    openssl req -new -newkey rsa:2048 -nodes -keyout key.pem -out req.csr \
        -subj "/CN=event-platform-intake.mock-intake.invalid"
    echo "subjectAltName=DNS:event-platform-intake.mock-intake.invalid,DNS:..." > ext
    openssl x509 -req -in req.csr -CA utils/proxy/.mitmproxy/mitmproxy-ca.pem \
        -CAkey utils/proxy/.mitmproxy/mitmproxy-ca.pem -set_serial 0x$(openssl rand -hex 8) -days 3650 -sha256 \
        -extfile ext -out cert.pem
    cat cert.pem key.pem > utils/mocked_backend/tls/mock-intake.pem
"""

from __future__ import annotations

import ssl
import threading
from typing import TYPE_CHECKING

from ._request_handler import MockedBackendServerCore, MockBackendV2RequestHandler

if TYPE_CHECKING:
    from ._request_handler import HttpMethod, RouteHandler


class TlsListener(MockedBackendServerCore):
    """Accepts HTTPS requests, and hands them to ``backend``: same routes, same records, same message count"""

    daemon_threads = True

    def __init__(self, backend: MockedBackendServerCore, port: int, cert_file: str) -> None:
        super().__init__(("0.0.0.0", port), MockBackendV2RequestHandler)  # noqa: S104
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file)
        self.socket = context.wrap_socket(self.socket, server_side=True)
        self.backend = backend
        self.on_message = backend.on_message
        self.port = self.server_port
        self._thread = threading.Thread(target=self.serve_forever, name="mock-backend-v2-tls", daemon=True)
        self._thread.start()

    def get_handler(self, method: HttpMethod, path: str) -> tuple[RouteHandler, str | None, str | None]:
        return self.backend.get_handler(method, path)

    def add_handler(self, method: HttpMethod, path: str, handler: RouteHandler) -> None:
        self.backend.add_handler(method, path, handler)

    @property
    def base_url(self) -> str:
        return f"https://127.0.0.1:{self.port}"

    def close(self) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

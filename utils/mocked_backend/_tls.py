"""TLS listener of the mocked backend: for clients that only speak HTTPS to hostnames derived from DD_SITE (e.g. an
SDK sending exposures directly to the intake). It serves the same routes, and records into the same folder, as the
plain HTTP server it is attached to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
import ssl
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ._request_handler import MockedBackendServerCore, MockBackendV2RequestHandler

if TYPE_CHECKING:
    from collections.abc import Sequence
    import socket

    from ._request_handler import HttpMethod, RouteHandler


def create_server_ssl_context(ca_file: str, hostnames: Sequence[str]) -> ssl.SSLContext:
    """A server context with a certificate for ``hostnames``, signed by the CA (key and certificate) in ``ca_file``.
    Clients trusting this CA accept it.
    """
    pem = Path(ca_file).read_text(encoding="utf-8")
    ca_key = serialization.load_pem_private_key(_pem_block(pem, "PRIVATE KEY").encode(), password=None)
    ca_cert = x509.load_pem_x509_certificate(_pem_block(pem, "CERTIFICATE").encode())
    assert isinstance(ca_key, rsa.RSAPrivateKey), "the CA key must be an RSA key"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name) for name in hostnames]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # load_cert_chain only reads files
    with tempfile.TemporaryDirectory() as folder:
        cert_file, key_file = Path(folder) / "cert.pem", Path(folder) / "key.pem"
        cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_file.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            )
        )
        context.load_cert_chain(cert_file, key_file)

    return context


def _pem_block(pem: str, label: str) -> str:
    """The first block of this kind (e.g. "CERTIFICATE") in a PEM file holding several ones"""
    match = re.search(rf"-----BEGIN ([A-Z ]*{label})-----.+?-----END \1-----", pem, re.DOTALL)
    assert match, f"no {label} in the PEM file"
    return match.group(0)


class TlsListener(MockedBackendServerCore):
    """Accepts HTTPS requests, and hands them to ``backend``: same routes, same records, same message count"""

    daemon_threads = True

    def __init__(self, backend: MockedBackendServerCore, port: int, ssl_context: ssl.SSLContext) -> None:
        super().__init__(("0.0.0.0", port), MockBackendV2RequestHandler)  # noqa: S104
        self.backend = backend
        self.on_message = backend.on_message
        self.port = self.server_port
        self._ssl_context = ssl_context
        self._thread = threading.Thread(target=self.serve_forever, name="mock-backend-v2-tls", daemon=True)
        self._thread.start()

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        sock, address = super().get_request()
        # the handshake runs in the request thread, on first read: a slow client never blocks accepting others
        return self._ssl_context.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), address

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

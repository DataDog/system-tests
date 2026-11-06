"""The certificate the mocked backend serves over HTTPS, generated when it starts.

It is signed by the mitmproxy CA, that the senders already trust: any hostname can be added without regenerating a
committed certificate, nor changing anything on the senders.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import ipaddress
from pathlib import Path
import ssl
import tempfile
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

if TYPE_CHECKING:
    from collections.abc import Sequence

# the CA certificate and its private key
CA_FILE = "utils/proxy/.mitmproxy/mitmproxy-ca.pem"
VALIDITY = timedelta(days=7)


def generate_certificate(hostnames: Sequence[str], ca_file: str = CA_FILE) -> tuple[bytes, bytes]:
    """A certificate for the hostnames, localhost and 127.0.0.1, and its key (PEM)"""
    ca_pem = Path(ca_file).read_bytes()
    ca_cert = x509.load_pem_x509_certificate(ca_pem)
    ca_key = serialization.load_pem_private_key(ca_pem, password=None)

    # an EC key takes ~1ms to generate, an RSA one up to a second
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    # naive, in UTC
    ca_not_after = ca_cert.not_valid_after.replace(tzinfo=UTC)
    names: list[x509.GeneralName] = [x509.DNSName(name) for name in [*hostnames, "localhost"]]
    names.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))

    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        # some margin for the clocks of the senders
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(min(now + VALIDITY, ca_not_after))
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        # some clients (e.g. Go, macOS) require it
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert.public_key()), critical=False)  # type: ignore[arg-type]
        .sign(ca_key, hashes.SHA256())  # type: ignore[arg-type]
    )

    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return cert.public_bytes(serialization.Encoding.PEM), key_pem


def server_context(hostnames: Sequence[str], ca_file: str = CA_FILE) -> ssl.SSLContext:
    """A server context serving a certificate generated for the hostnames"""
    cert_pem, key_pem = generate_certificate(hostnames, ca_file)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # the ssl module only loads a certificate from a file
    with tempfile.TemporaryDirectory() as folder:
        cert_file = Path(folder) / "cert.pem"
        cert_file.write_bytes(cert_pem + key_pem)
        context.load_cert_chain(cert_file)
    return context

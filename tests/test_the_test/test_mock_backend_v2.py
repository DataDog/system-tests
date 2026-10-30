"""Unit coverage for MockedBackendServer (utils.mocked_backend)."""

from datetime import UTC, datetime
import gzip
import signal
import socket
import threading
import ssl
import json
from collections.abc import Generator
from pathlib import Path
import subprocess
import sys

from utils import pytest
import requests
import zstandard
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12

from utils import scenarios
from utils.interfaces._mocked_backend import _MockedBackendInterfaceValidator
from utils._context.containers import MockedBackendContainer, TestedContainer
from utils._context._scenarios.agentless_endtoend import JAVA_TRUSTSTORE_SOURCE
from utils.mocked_backend import MockedBackendClient, MockedBackendServer
from utils.mocked_backend._tls import generate_certificate
from utils.mocked_backend.ffe import UFC_FIXTURE_RELATIVE_PATH
from utils.proxy.mocked_response import MockedBackendResponse


@pytest.fixture
def server(tmp_path: Path) -> Generator[MockedBackendServer, None, None]:
    server = MockedBackendServer(str(tmp_path), port=0)

    yield server

    server.close()


@scenarios.test_the_test
def test_writes_one_file_per_request(server: MockedBackendServer, tmp_path: Path):
    response = requests.post(
        f"{server.base_url}/api/v2/series",
        data=json.dumps({"hello": "world"}),
        headers={"Content-Type": "application/json"},
        timeout=5,
    )
    assert response.status_code == 200

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1

    data = json.loads(written[0].read_text())
    assert data["method"] == "POST"
    assert data["path"] == "/api/v2/series"
    assert data["request"]["content"] == {"hello": "world"}


@scenarios.test_the_test
def test_query_string_is_stripped_from_the_log_filename(server: MockedBackendServer, tmp_path: Path):
    response = requests.get(f"{server.base_url}/info?trace_count=42", timeout=5)
    assert response.status_code == 200

    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert "?" not in written[0].name
    assert "trace_count" not in written[0].name

    data = json.loads(written[0].read_text())
    assert data["path"] == "/info"


@scenarios.test_the_test
def test_message_count_is_reflected_in_successive_log_filenames(server: MockedBackendServer, tmp_path: Path):
    for _ in range(3):
        requests.get(f"{server.base_url}/info", timeout=5)

    written = sorted(f.name for f in tmp_path.glob("*.json"))
    assert written == ["000__info.json", "001__info.json", "002__info.json"]


@scenarios.test_the_test
def test_gzip_content_encoding_is_decoded_before_being_logged(server: MockedBackendServer, tmp_path: Path):
    body = gzip.compress(json.dumps({"compressed": "gzip"}).encode())
    response = requests.post(
        f"{server.base_url}/api/v2/series",
        data=body,
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
        timeout=5,
    )
    assert response.status_code == 200

    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert data["request"]["content"] == {"compressed": "gzip"}


@scenarios.test_the_test
def test_zstd_content_encoding_is_decoded_before_being_logged(server: MockedBackendServer, tmp_path: Path):
    body = zstandard.ZstdCompressor().compress(json.dumps({"compressed": "zstd"}).encode())
    response = requests.post(
        f"{server.base_url}/api/v2/series",
        data=body,
        headers={"Content-Type": "application/json", "Content-Encoding": "zstd"},
        timeout=5,
    )
    assert response.status_code == 200

    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert data["request"]["content"] == {"compressed": "zstd"}


@scenarios.test_the_test
def test_undecodable_content_is_logged_without_crashing_the_server(server: MockedBackendServer, tmp_path: Path):
    response = requests.post(
        f"{server.base_url}/api/v2/series",
        data=b"not actually zstd",
        headers={"Content-Type": "application/json", "Content-Encoding": "zstd"},
        timeout=5,
    )
    assert response.status_code == 200

    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert "content" not in data["request"]
    assert "traceback" in data["request"]


@scenarios.test_the_test
def test_serves_internal_mocked_responses_from_a_file(tmp_path: Path):
    """Like the proxy's internal ones, they are set by the scenario for the whole session"""
    mocks_file = tmp_path / "mocks.json"
    mock = MockedBackendResponse("/api/v0.1/configurations", b"\x01\x02", status_code=202)
    mocks_file.write_text(json.dumps([mock.to_json()]))
    log_folder = tmp_path / "logs"
    log_folder.mkdir()

    server = MockedBackendServer(str(log_folder), port=0, internal_mocked_responses_file=str(mocks_file))
    try:
        response = requests.post(f"{server.base_url}/api/v0.1/configurations", data=b"", timeout=5)
        unmatched = requests.post(f"{server.base_url}/api/v2/series", json={}, timeout=5)
    finally:
        server.close()

    assert response.status_code == 202
    assert response.headers["Content-Type"] == "application/x-protobuf"
    assert response.content == b"\x01\x02"
    # other paths get the usual response
    assert unmatched.status_code == 200
    # a mocked request is recorded like any other
    assert sorted(f.name for f in log_folder.glob("*.json")) == [
        "000__api_v0.1_configurations.json",
        "001__api_v2_series.json",
    ]


@scenarios.test_the_test
def test_runtime_mocked_responses_take_precedence_and_are_replaced(tmp_path: Path):
    mocks_file = tmp_path / "mocks.json"
    mocks_file.write_text(json.dumps([MockedBackendResponse("/api/v0.1/configurations", b"internal").to_json()]))
    (tmp_path / "logs").mkdir()

    server = MockedBackendServer(str(tmp_path / "logs"), port=0, internal_mocked_responses_file=str(mocks_file))
    try:
        poll = f"{server.base_url}/api/v0.1/configurations"

        server.client.set_mocked_responses([MockedBackendResponse("/api/v0.1/configurations", b"runtime")])
        assert requests.post(poll, data=b"", timeout=5).content == b"runtime"

        # each call replaces the previous runtime responses, like with the proxy
        server.client.set_mocked_responses([])
        assert requests.post(poll, data=b"", timeout=5).content == b"internal"
    finally:
        server.close()

    # control requests are not recorded
    assert len(list((tmp_path / "logs").glob("*.json"))) == 2


def _configure_without_docker(container: MockedBackendContainer, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run MockedBackendContainer.configure without the base one, which stops containers and loads the image"""

    def base_configure(self: TestedContainer, *, host_log_folder: str, replay: bool) -> None:  # noqa: ARG001
        self.host_log_folder = host_log_folder
        Path(self.log_folder_path).mkdir(parents=True)

    monkeypatch.setattr(TestedContainer, "configure", base_configure)
    container.configure(host_log_folder="logs_x", replay=False)


@scenarios.test_the_test
def test_container_gives_its_internal_mocked_responses_to_the_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    container = MockedBackendContainer(tls=True)
    mock = MockedBackendResponse("/api/v0.1/configurations", b"\x01")
    container.internal_mocked_responses.append(mock)
    _configure_without_docker(container, monkeypatch)

    mocks_path = f"{container.log_folder_path}/{MockedBackendResponse.internal_filename}"
    assert json.loads(Path(mocks_path).read_text()) == [mock.to_json()]
    container_path = f"/app/{MockedBackendResponse.internal_filename}"
    assert container.volumes[mocks_path] == {"bind": container_path, "mode": "ro"}
    assert isinstance(container.command, list)
    assert container.command[-2:] == ["--internal-mocked-responses-file", container_path]


@scenarios.test_the_test
def test_container_without_internal_mocked_responses_does_not_pass_the_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    container = MockedBackendContainer(tls=True)
    _configure_without_docker(container, monkeypatch)

    assert isinstance(container.command, list)
    assert "--internal-mocked-responses-file" not in container.command


@scenarios.test_the_test
@pytest.mark.parametrize("body", [[], {"responses": "nope"}, {"responses": [1]}])
def test_rejects_malformed_mocked_responses(server: MockedBackendServer, body: object):
    response = requests.put(f"{server.base_url}/system-tests/mocked-responses", json=body, timeout=5)
    assert response.status_code == 400


@scenarios.test_the_test
def test_mocked_responses_match_the_query_string_like_the_proxy(server: MockedBackendServer):
    server.client.set_mocked_responses(
        [
            MockedBackendResponse("/endpoint?mode=test", b"with query"),
            MockedBackendResponse("/other", b"without query"),
        ]
    )

    assert requests.get(f"{server.base_url}/endpoint?mode=test", timeout=5).content == b"with query"
    assert requests.get(f"{server.base_url}/endpoint", timeout=5).content != b"with query"
    assert requests.get(f"{server.base_url}/other?mode=test", timeout=5).content != b"without query"


@scenarios.test_the_test
def test_a_bad_internal_mocked_responses_file_does_not_keep_the_port(tmp_path: Path):
    probe = MockedBackendServer(None, port=0)
    port = probe.port
    probe.close()
    bad_file = tmp_path / "mocks.json"
    bad_file.write_text("not json")

    with pytest.raises(json.JSONDecodeError):
        MockedBackendServer(None, port=port, internal_mocked_responses_file=str(bad_file))

    # the port is still free
    MockedBackendServer(None, port=port).close()


@scenarios.test_the_test
def test_on_message_callback_is_invoked_with_the_logged_data(tmp_path: Path):
    received: list[dict] = []
    server = MockedBackendServer(str(tmp_path), on_message=received.append, port=0)

    try:
        requests.post(
            f"{server.base_url}/api/v2/series",
            data=json.dumps({"hello": "callback"}),
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    finally:
        server.close()

    assert len(received) == 1
    assert received[0]["request"]["content"] == {"hello": "callback"}

    written = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert written["log_filename"] == received[0]["log_filename"]
    assert written["request"]["content"] == received[0]["request"]["content"]


@scenarios.test_the_test
def test_control_requests_are_not_recorded(tmp_path: Path):
    received: list[dict] = []
    server = MockedBackendServer(str(tmp_path), on_message=received.append, port=0)

    try:
        server.client.ffe_set_response("valid")
        assert server.client.ffe_get_status()["requests_total"] == 0
        requests.post(f"{server.base_url}/api/v2/series", json={"hello": "recorded"}, timeout=5)
    finally:
        server.close()

    assert [data["path"] for data in received] == ["/api/v2/series"]
    assert [path.name for path in tmp_path.glob("*.json")] == ["000__api_v2_series.json"]


@scenarios.test_the_test
def test_runs_without_the_rest_of_utils(tmp_path: Path):
    """The mocked backend must work with only what its container mounts (utils/mocked_backend, utils/proxy and the
    FFE fixture, see MockedBackendContainer), and without pytest.
    """
    repo_root = Path(__file__).parents[2]
    (tmp_path / "utils").mkdir()  # no __init__.py: a namespace package, as in the proxy image
    for package in ("mocked_backend", "proxy"):
        (tmp_path / "utils" / package).symlink_to(repo_root / "utils" / package)
    (tmp_path / UFC_FIXTURE_RELATIVE_PATH).parent.mkdir(parents=True)
    (tmp_path / UFC_FIXTURE_RELATIVE_PATH).symlink_to(repo_root / UFC_FIXTURE_RELATIVE_PATH)

    # Not `python -I`: third-party packages may come from PYTHONPATH (e.g. Nix). Instead, drop the repository
    # from sys.path, otherwise the real utils package would be imported, and this test would always pass.
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path = [p for p in sys.path if Path(p or '.').resolve() != Path({str(repo_root)!r}).resolve()]\n"
        f"sys.path.insert(0, {str(tmp_path)!r})\n"
        "sys.modules['pytest'] = sys.modules['_pytest'] = None  # importing them raises ImportError\n"
        "import utils\n"
        "assert getattr(utils, '__file__', None) is None, f'not the namespace package: {utils.__file__}'\n"
        "from utils.mocked_backend import MockedBackendServer\n"
        "from utils.mocked_backend.ffe import CONFIG_PATH\n"
        "from utils.mocked_backend.ffe import ffe_library_config_url\n"
        "import utils.mocked_backend.__main__\n"
        "from urllib.request import urlopen\n"
        "server = MockedBackendServer(port=0)\n"
        "try:\n"
        "    with urlopen(ffe_library_config_url(server.base_url), timeout=5) as response:\n"
        "        assert response.status == 200, response.status\n"
        "finally:\n"
        "    server.close()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False, cwd=tmp_path)

    assert result.returncode == 0, result.stderr


@scenarios.test_the_test
def test_entry_point_serves_until_sigterm(tmp_path: Path):
    """`python -m utils.mocked_backend` is how the mocked backend will run in its own container."""
    log_folder = tmp_path / "mocked_backend"  # created by the entry point
    process = subprocess.Popen(
        [sys.executable, "-m", "utils.mocked_backend", "--port", "0", "--log-folder", str(log_folder)],
        cwd=Path(__file__).parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        # its logs are on stdout too: skip them. An empty line means it exited
        line = process.stdout.readline()
        while line and not line.startswith("Mocked backend listening on port "):
            line = process.stdout.readline()
        assert line, process.stderr.read()  # type: ignore[union-attr]
        client = MockedBackendClient(f"http://127.0.0.1:{line.split()[-1]}")

        requests.post(f"{client.base_url}/api/v2/series", json={"hello": "entry point"}, timeout=5)
        client.ffe_set_response("unauthorized")
        assert client.ffe_get_status()["requests_total"] == 0

        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    # control requests are not recorded
    assert [path.name for path in log_folder.glob("*.json")] == ["000__api_v2_series.json"]


@scenarios.test_the_test
def test_health_endpoint(server: MockedBackendServer, tmp_path: Path):
    response = requests.get(f"{server.base_url}/system-tests/health", timeout=5)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # a control endpoint: not recorded
    assert list(tmp_path.glob("*.json")) == []


def _mocked_backend_with_requests(
    tmp_path: Path, requests_: list[tuple[str, str | None]]
) -> _MockedBackendInterfaceValidator:
    """A mocked backend interface that received a series request per (filename, api_key)"""
    interface = _MockedBackendInterfaceValidator()
    interface.configure(str(tmp_path), replay=False)
    for filename, api_key in requests_:
        headers = [["Content-Type", "application/json"]] + ([["DD-API-KEY", api_key]] if api_key else [])
        file = Path(interface.log_folder) / filename
        data = {
            "log_filename": str(file),
            "path": "/api/v2/series",
            "request": {"headers": headers, "content": {"series": [{"metric": filename}]}},
            "response": {},
        }
        file.write_text(json.dumps(data))
        interface.ingest_file(str(file))
    return interface


@scenarios.test_the_test
def test_mocked_backend_with_api_key_only_returns_requests_sent_with_this_key(tmp_path: Path):
    interface = _mocked_backend_with_requests(
        tmp_path, [("000__agent.json", "agent-key"), ("001__sidecar.json", "sidecar-key"), ("002__nokey.json", None)]
    )

    assert [d["log_filename"].split("/")[-1] for d in interface.get_data(with_api_key="sidecar-key")] == [
        "001__sidecar.json"
    ]
    assert [point["metric"] for _, point in interface.get_metrics(with_api_key="agent-key")] == ["000__agent.json"]
    assert list(interface.get_data(with_api_key="unknown-key")) == []
    # without it, every request
    assert len(list(interface.get_data())) == 3


@scenarios.test_the_test
def test_mocked_backend_with_api_key_ignores_the_header_name_case(tmp_path: Path):
    interface = _mocked_backend_with_requests(tmp_path, [("000__agent.json", "agent-key")])
    data = next(interface.get_data())
    data["request"]["headers"] = [["dd-api-key", "agent-key"]]

    assert len(list(interface.get_data(with_api_key="agent-key"))) == 1


_MITMPROXY_CA = "utils/proxy/.mitmproxy/mitmproxy-ca-cert.pem"
_TLS_HOSTNAMES = MockedBackendContainer.tls_hostnames
_INTAKE_HOSTNAME = "event-platform-intake.mocked-backend.invalid"


def _https_post(port: int, hostname: str, path: str, body: bytes) -> str:
    """POST over HTTPS to 127.0.0.1, verifying the certificate is valid for hostname: the status line"""
    context = ssl.create_default_context(cafile=_MITMPROXY_CA)
    with (
        socket.create_connection(("127.0.0.1", port), timeout=5) as raw,
        context.wrap_socket(raw, server_hostname=hostname) as tls,
    ):
        request = f"POST {path} HTTP/1.1\r\nHost: {hostname}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        tls.sendall(request.encode() + body)
        return tls.recv(4096).decode().splitlines()[0]


@scenarios.test_the_test
def test_https_mode_serves_and_records_https_requests(tmp_path: Path):
    server = MockedBackendServer(str(tmp_path), port=0, tls_hostnames=_TLS_HOSTNAMES)
    try:
        status_line = _https_post(server.port, _INTAKE_HOSTNAME, "/api/v2/exposures", b'{"over": "https"}')
        # the control endpoints, as used from the host
        health = requests.get(f"{server.base_url}/system-tests/health", timeout=5, verify=_MITMPROXY_CA)
    finally:
        server.close()

    # the event platform intake accepts the payload for asynchronous processing
    assert status_line == "HTTP/1.0 202 Accepted"
    assert health.json() == {"status": "ok"}
    recorded = json.loads((tmp_path / "000__api_v2_exposures.json").read_text())
    assert recorded["request"]["content"] == {"over": "https"}


@scenarios.test_the_test
def test_https_mode_does_not_serve_http(tmp_path: Path):
    server = MockedBackendServer(str(tmp_path), port=0, tls_hostnames=_TLS_HOSTNAMES)
    try:
        with pytest.raises(requests.exceptions.ConnectionError):
            requests.post(f"http://127.0.0.1:{server.port}/api/v2/series", json={}, timeout=5)
    finally:
        server.close()


@scenarios.test_the_test
def test_https_mode_releases_the_port_if_the_certificate_cannot_be_generated(tmp_path: Path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    with pytest.raises(FileNotFoundError) as error:
        MockedBackendServer(
            str(tmp_path), port=port, tls_hostnames=_TLS_HOSTNAMES, tls_ca_file=str(tmp_path / "missing.pem")
        )

    # the port is free again, even while the error (holding the half-built server) is still referenced
    assert error.traceback
    MockedBackendServer(str(tmp_path), port=port).close()


@scenarios.test_the_test
def test_https_mode_is_not_blocked_by_an_idle_connection(tmp_path: Path):
    server = MockedBackendServer(str(tmp_path), port=0, tls_hostnames=_TLS_HOSTNAMES)
    closed = threading.Event()

    def close() -> None:
        server.close()
        closed.set()

    try:
        # connects, and never starts the TLS handshake
        with socket.create_connection(("127.0.0.1", server.port), timeout=5):
            status_line = _https_post(server.port, _INTAKE_HOSTNAME, "/api/v2/exposures", b"{}")
            threading.Thread(target=close, daemon=True).start()
            assert closed.wait(timeout=10), "close() hangs while a connection is idle"
    finally:
        if not closed.is_set():
            server.close()

    # the event platform intake accepts the payload for asynchronous processing
    assert status_line == "HTTP/1.0 202 Accepted"


@scenarios.test_the_test
def test_https_mode_advertises_https_urls(tmp_path: Path):
    server = MockedBackendServer(str(tmp_path), port=0, tls_hostnames=_TLS_HOSTNAMES)
    try:
        assert server.container_url.startswith("https://")
        assert server.ffe_library_config_url.startswith("https://")
    finally:
        server.close()


@scenarios.test_the_test
def test_https_certificate_is_only_valid_for_the_served_hostnames(tmp_path: Path):
    server = MockedBackendServer(str(tmp_path), port=0, tls_hostnames=_TLS_HOSTNAMES)
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            _https_post(server.port, "other.mocked-backend.invalid", "/api/v2/exposures", b"{}")
    finally:
        server.close()


@scenarios.test_the_test
def test_generated_certificate_covers_the_hostnames_and_is_signed_by_the_ca():
    cert_pem, _ = generate_certificate(_TLS_HOSTNAMES)
    cert = x509.load_pem_x509_certificate(cert_pem)
    ca = x509.load_pem_x509_certificate(Path(_MITMPROXY_CA).read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value

    # reached by its domain, its intake hostnames, and by localhost from the healthcheck and the host
    assert names.get_values_for_type(x509.DNSName) == [*_TLS_HOSTNAMES, "localhost"]
    assert [str(ip) for ip in names.get_values_for_type(x509.IPAddress)] == ["127.0.0.1"]
    assert cert.issuer == ca.subject
    # naive, in UTC
    assert cert.not_valid_before.replace(tzinfo=UTC) < datetime.now(UTC) < cert.not_valid_after.replace(tzinfo=UTC)
    assert cert.not_valid_after <= ca.not_valid_after


@scenarios.test_the_test
def test_java_truststore_holds_the_ca_of_the_certificate():
    """The JVM trusts the mocked backend with this trust store: it must hold the CA that signs its certificate"""
    truststore = pkcs12.load_pkcs12(Path(JAVA_TRUSTSTORE_SOURCE).read_bytes(), b"changeit")
    ca = x509.load_pem_x509_certificate(Path(_MITMPROXY_CA).read_bytes())
    cert = x509.load_pem_x509_certificate(generate_certificate(_TLS_HOSTNAMES)[0])

    assert [entry.certificate for entry in truststore.additional_certs] == [ca]
    assert cert.issuer == ca.subject


@scenarios.test_the_test
def test_mocked_backend_container_serves_either_http_or_https():
    http = MockedBackendContainer()
    assert http.container_url == "http://mocked-backend:4900"
    assert http.network_aliases == []

    https = MockedBackendContainer(tls=True)
    # senders build the intake URLs from DD_SITE: the default HTTPS port, its domain and the intake hostnames
    assert https.container_url == "https://mocked-backend.invalid"
    assert https.network_aliases == list(MockedBackendContainer.tls_hostnames)


@scenarios.test_the_test
def test_serves_remote_config_by_default(server: MockedBackendServer):
    for method, path in (
        ("GET", "/api/v0.1/org"),
        ("GET", "/api/v0.1/status"),
        ("GET", "/api/v0.2/echo-test"),
        ("POST", "/api/v0.1/configurations"),
    ):
        response = requests.request(method, f"{server.base_url}{path}", timeout=5)
        assert response.status_code == 200
        assert response.content, path

    server.client.set_mocked_responses([MockedBackendResponse("/api/v0.1/configurations", b"from a test")])
    assert requests.post(f"{server.base_url}/api/v0.1/configurations", timeout=5).content == b"from a test"

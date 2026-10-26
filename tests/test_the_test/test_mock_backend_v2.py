"""Unit coverage for MockedBackendServer (utils.mocked_backend)."""

import gzip
import signal
import json
from collections.abc import Generator
from pathlib import Path
import subprocess
import sys
import threading

from utils import pytest
import requests
import zstandard

from utils import scenarios
from utils.interfaces._backend_v2 import _BackendV2InterfaceValidator
from utils.mocked_backend import MockedBackendClient, MockedBackendServer


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
def test_interface_wait_for_is_released_by_a_received_message(tmp_path: Path):
    interface = _BackendV2InterfaceValidator()
    interface.configure(str(tmp_path), replay=False)
    message = {"log_filename": "000__api_v2_series.json", "path": "/api/v2/series", "request": {"content": {}}}

    # delivered while wait_for is waiting, as the mocked backend does when it receives a request
    timer = threading.Timer(0.5, interface._on_message, args=(message,))  # noqa: SLF001
    timer.start()
    try:
        assert interface.wait_for(lambda data: data["path"] == "/api/v2/series", timeout=5)
    finally:
        timer.cancel()


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
    """The mocked backend must be importable with only utils/mocked_backend and utils/proxy, and without
    pytest, so it can run in its own container.
    """
    repo_root = Path(__file__).parents[2]
    (tmp_path / "utils").mkdir()  # no __init__.py: a namespace package, as in the proxy image
    for package in ("mocked_backend", "proxy"):
        (tmp_path / "utils" / package).symlink_to(repo_root / "utils" / package)

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
        "import utils.mocked_backend.__main__\n"
        "server = MockedBackendServer(port=0)\n"
        "server.close()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False, cwd=tmp_path)

    assert result.returncode == 0, result.stderr


@scenarios.test_the_test
def test_entry_point_serves_until_sigterm(tmp_path: Path):
    """`python -m utils.mocked_backend` is how the mocked backend will run in its own container."""
    log_folder = tmp_path / "backend_v2"  # created by the entry point
    process = subprocess.Popen(
        [sys.executable, "-m", "utils.mocked_backend", "--port", "0", "--log-folder", str(log_folder)],
        cwd=Path(__file__).parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        first_line = process.stdout.readline()
        assert first_line.startswith("Mocked backend listening on port "), process.stderr.read()  # type: ignore[union-attr]
        client = MockedBackendClient(f"http://127.0.0.1:{first_line.split()[-1]}")

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

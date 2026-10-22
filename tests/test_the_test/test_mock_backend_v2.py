"""Unit coverage for MockedBackendServer (utils.mocked_backend)."""

import gzip
import json
from collections.abc import Generator
from pathlib import Path

from utils import pytest
import requests
import zstandard

from utils import scenarios
from utils.mocked_backend import MockedBackendServer


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
def test_control_requests_are_not_recorded(tmp_path: Path):
    received: list[dict] = []
    server = MockedBackendServer(str(tmp_path), on_message=received.append, port=0)

    try:
        server.ffe_set_response("valid")
        assert server.ffe_get_status()["requests_total"] == 0
        requests.post(f"{server.base_url}/api/v2/series", json={"hello": "recorded"}, timeout=5)
    finally:
        server.close()

    assert [data["path"] for data in received] == ["/api/v2/series"]
    assert [path.name for path in tmp_path.glob("*.json")] == ["000__api_v2_series.json"]

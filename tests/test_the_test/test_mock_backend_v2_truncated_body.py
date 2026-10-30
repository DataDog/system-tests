from collections.abc import Generator
import contextlib
import json
from pathlib import Path
import socket
import time

from utils import pytest
import zstandard

from utils import scenarios
from utils.mocked_backend import MockedBackendServer
from utils.proxy._decoders.protobuf_schemas import MetricPayload


@pytest.fixture
def server(tmp_path: Path) -> Generator[MockedBackendServer, None, None]:
    server = MockedBackendServer(str(tmp_path), port=0)

    yield server

    server.close()


def _series_body() -> bytes:
    payload = MetricPayload()
    for i in range(200):
        serie = payload.series.add()
        serie.metric = f"runtime.dotnet.metric_{i}"
        serie.tags.extend([f"tag_{i}:value_{i}", "env:system-tests"])
        point = serie.points.add()
        point.timestamp = 1793072508
        point.value = float(i)

    return zstandard.ZstdCompressor().compress(payload.SerializeToString())


def _post_series(server: MockedBackendServer, body: bytes, bytes_to_send: int) -> None:
    headers = (
        "POST /api/v2/series HTTP/1.1\r\n"
        f"Host: localhost:{server.port}\r\n"
        "User-Agent: datadog-agent/7.84.6\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Content-Encoding: zstd\r\n"
        "Content-Type: application/x-protobuf\r\n"
        "\r\n"
    ).encode()

    with socket.create_connection(("localhost", server.port), timeout=5) as sock:
        sock.sendall(headers + body[:bytes_to_send])
        sock.shutdown(socket.SHUT_WR)
        with contextlib.suppress(OSError):
            sock.recv(65536)


def _recorded_series(tmp_path: Path) -> dict:
    for _ in range(50):
        written = list(tmp_path.glob("*__api_v2_series.json"))
        if written:
            return json.loads(written[0].read_text())
        time.sleep(0.1)

    raise AssertionError("no /api/v2/series request was recorded")


def _assert_like_get_metrics(data: dict) -> None:
    content = data["request"]["content"]
    assert isinstance(content, dict), f"content is not a dict in {data['log_filename']}"


@scenarios.test_the_test
def test_control_complete_series_body_is_recorded_as_a_dict(server: MockedBackendServer, tmp_path: Path):
    body = _series_body()
    _post_series(server, body, bytes_to_send=len(body))

    data = _recorded_series(tmp_path)
    _assert_like_get_metrics(data)
    assert len(data["request"]["content"]["series"]) == 200


@scenarios.test_the_test
def test_truncated_series_body_is_not_recorded_as_a_valid_payload(server: MockedBackendServer, tmp_path: Path):
    body = _series_body()
    _post_series(server, body, bytes_to_send=len(body) // 2)

    data = _recorded_series(tmp_path)
    if "traceback" in data["request"] or "raw_content" in data["request"]:
        return
    _assert_like_get_metrics(data)

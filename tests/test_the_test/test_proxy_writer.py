"""The proxy must keep serving flows while the disk is slow (APPSEC-71652).

mitmproxy only sends a response to the client once the response hook returns. When that hook wrote the flow
file synchronously, a ~14s I/O stall on a CI runner froze the whole proxy, the PHP sidecar's trace submission
timed out, and the trace never reached the test.
"""

from collections.abc import Iterator
import json
from pathlib import Path
import threading
import time
from typing import Any

from utils import pytest, scenarios
from utils.proxy import _flow_writer
from utils.proxy._flow_writer import FlowWriter


@pytest.fixture
def writer() -> Iterator[FlowWriter]:
    result = FlowWriter()
    try:
        yield result
    finally:
        result.close()


def _data(folder: Path, name: str, path: str) -> dict[str, Any]:
    return {
        "log_filename": str(folder / name),
        "path": path,
        "query": "",
        "request": {"headers": [("content-type", "application/json")], "length": 0},
        "response": {"status_code": 200, "headers": [("content-type", "application/json")], "length": 0},
    }


def _submit(writer: FlowWriter, folder: Path, name: str, path: str) -> None:
    writer.submit(
        "flow-id",
        _data(folder, name, path),
        "library",
        json.dumps({"path": path}).encode(),
        b'{"ok": true}',
        str(folder / "files"),
        response_killed=False,
    )


@scenarios.test_the_test
def test_submit_does_not_wait_for_the_disk(writer: FlowWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disk_released = threading.Event()
    original_deserialize = _flow_writer.deserialize

    def stalled_deserialize(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        # stands for the slow disk: everything the writer thread does happens after this
        disk_released.wait(timeout=30)
        original_deserialize(*args, **kwargs)

    monkeypatch.setattr(_flow_writer, "deserialize", stalled_deserialize)

    start = time.monotonic()
    _submit(writer, tmp_path, "00000__v0.4_traces.json", "/v0.4/traces")
    _submit(writer, tmp_path, "00001__v0.7_config.json", "/v0.7/config")
    elapsed = time.monotonic() - start

    # the response hook can return, so mitmproxy answers the tracer, while the flows are not on disk yet
    assert elapsed < 1, f"submit blocked for {elapsed:.1f}s on a stalled disk"
    assert not list(tmp_path.glob("*.json"))

    disk_released.set()
    writer.close()  # flushes the pending writes, as on proxy shutdown

    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["00000__v0.4_traces.json", "00001__v0.7_config.json"]

    data = json.loads((tmp_path / "00001__v0.7_config.json").read_text())
    assert data["path"] == "/v0.7/config"
    assert data["request"]["content"] == {"path": "/v0.7/config"}
    assert data["response"]["content"] == {"ok": True}


@scenarios.test_the_test
def test_flows_are_written_in_submission_order(
    writer: FlowWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: list[str] = []
    original_persist_flow = _flow_writer.persist_flow

    def recording_persist_flow(data: dict[str, Any], *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        original_persist_flow(data, *args, **kwargs)
        written.append(Path(data["log_filename"]).name)

    monkeypatch.setattr(_flow_writer, "persist_flow", recording_persist_flow)

    names = [f"{i:05d}__v0.4_traces.json" for i in range(50)]
    for name in names:
        _submit(writer, tmp_path, name, "/v0.4/traces")
    writer.close()

    assert written == names


@scenarios.test_the_test
def test_killed_response_is_saved_as_none(writer: FlowWriter, tmp_path: Path) -> None:
    writer.submit(
        "flow-id",
        _data(tmp_path, "00000__v0.4_traces.json", "/v0.4/traces"),
        "library",
        b'{"a": 1}',
        b'{"b": 2}',
        str(tmp_path / "files"),
        response_killed=True,
    )
    writer.close()

    data = json.loads((tmp_path / "00000__v0.4_traces.json").read_text())
    assert data["request"]["content"] == {"a": 1}
    assert data["response"] is None


@scenarios.test_the_test
def test_failed_write_does_not_stop_the_writer(
    writer: FlowWriter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_dump = json.dump
    calls = {"count": 0}

    def flaky_dump(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("No space left on device")
        original_dump(*args, **kwargs)

    monkeypatch.setattr(_flow_writer.json, "dump", flaky_dump)

    _submit(writer, tmp_path, "00000__v0.7_config.json", "/v0.7/config")
    _submit(writer, tmp_path, "00001__v0.7_config.json", "/v0.7/config")
    writer.close()

    assert json.loads((tmp_path / "00001__v0.7_config.json").read_text())["path"] == "/v0.7/config"

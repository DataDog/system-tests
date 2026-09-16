import json
from pathlib import Path
from typing import Any

import pytest
import requests

from utils.interfaces import _test_agent
from utils.interfaces._test_agent import _TestAgentInterfaceValidator


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


class _FakeTestAgentClient:
    def __init__(self, telemetry_responses: list[list[dict[str, Any]] | Exception]) -> None:
        self._telemetry_responses = telemetry_responses
        self.telemetry_calls = 0
        self.telemetry_timeouts: list[float | None] = []

    def traces(self, *, clear: bool) -> list[dict[str, Any]]:
        assert not clear
        return []

    def telemetry(self, *, clear: bool, timeout: float | None = None) -> list[dict[str, Any]]:
        assert not clear
        response = self._telemetry_responses[min(self.telemetry_calls, len(self._telemetry_responses) - 1)]
        self.telemetry_calls += 1
        self.telemetry_timeouts.append(timeout)
        if isinstance(response, Exception):
            raise response
        return response


def _collect_with_fake_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    telemetry_responses: list[list[dict[str, Any]] | Exception],
) -> tuple[_TestAgentInterfaceValidator, _FakeTestAgentClient]:
    client = _FakeTestAgentClient(telemetry_responses)
    monkeypatch.setattr(_test_agent.agent_client, "TestAgentClient", lambda **_kwargs: client)
    interface = _TestAgentInterfaceValidator()
    interface.collect_data(str(tmp_path))
    return interface, client


def test_wait_for_crash_reports_refreshes_the_live_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crash_report = {"tags": "signame:SIGSEGV"}
    monkeypatch.setattr(_test_agent.time, "sleep", lambda _seconds: None)
    interface, client = _collect_with_fake_client(
        tmp_path,
        monkeypatch,
        [
            [],
            [{"request_type": "app-started", "payload": {}}],
            [{"request_type": "logs", "payload": [crash_report]}],
        ],
    )

    assert interface.wait_for_crash_reports(timeout=1) == [crash_report]
    assert client.telemetry_calls == 4
    assert client.telemetry_timeouts[1:]
    assert all(
        request_timeout is not None and 0 < request_timeout <= 1 for request_timeout in client.telemetry_timeouts[1:]
    )
    assert json.loads((tmp_path / "00_telemetry.json").read_text(encoding="utf-8")) == [
        {"request_type": "logs", "payload": [crash_report]}
    ]


def test_wait_for_crash_reports_has_bounded_diagnostic_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    interface, client = _collect_with_fake_client(
        tmp_path, monkeypatch, [[], [{"request_type": "app-started", "payload": {}}]]
    )

    with pytest.raises(
        AssertionError,
        match=r"No crash report received within 0 seconds; collected 0 telemetry request\(s\) with types: <none>",
    ):
        interface.wait_for_crash_reports(timeout=0)

    assert client.telemetry_calls == 1


def test_wait_for_crash_reports_bounds_live_refreshes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    interface, client = _collect_with_fake_client(tmp_path, monkeypatch, [[], requests.Timeout("test agent stalled")])
    monotonic_values = iter([0.0, 0.25, 1.0])
    monkeypatch.setattr(_test_agent.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(AssertionError, match=r"last refresh error: test agent stalled"):
        interface.wait_for_crash_reports(timeout=1)

    assert client.telemetry_calls == 2
    assert client.telemetry_timeouts == [None, 0.75]

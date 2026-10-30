"""Unit tests for the crash report selection in the parametric crashtracking tests.

Covers the ``is_crash:true`` report selection, the log entry flattening for both
crashtracking payload shapes, the telemetry event enumeration it builds on, and the
Error Tracking report selection.
"""

import base64
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import requests

from utils import pytest

from tests.parametric import test_crashtracking
from tests.parametric.test_crashtracking import is_crash_report
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures import ParametricTestClientApi as APMLibrary


pytestmark = pytest.mark.scenario("TEST_THE_TEST")

# The selection helpers under test are stateless; a bare instance lets the unit
# tests call them without the pytest fixtures the parametric scenario provides.
_crashtracking = test_crashtracking.Test_Crashtracking()


def _log_entry(tags: str) -> dict[str, Any]:
    """Build a telemetry log entry carrying the given tags."""
    return {"message": "unit test", "tags": tags}


def _crash_report_entry() -> dict[str, Any]:
    """Build the log entry the crashtracker sends for the crash report itself."""
    return _log_entry("uuid:report,is_crash:true,si_signo:11")


def _crash_ping_entry() -> dict[str, Any]:
    """Build the log entry the crashtracker sends for a crash ping."""
    return _log_entry("uuid:ping,is_crash_ping:true,service:service")


def _debug_log_entry() -> dict[str, Any]:
    """Build the log entry the crashtracker receiver sends for a debug log."""
    return _log_entry("receiver_issue:incomplete_stacktrace,crash_uuid:debug,is_crash_debug:true")


def _v1_logs_event(*entries: dict[str, Any]) -> dict[str, Any]:
    """Build a captured "logs" event with a v1 payload: a bare list of entries."""
    return {"request_type": "logs", "payload": list(entries), "application": {"language_version": "3.12.4"}}


def _v2_logs_event(*entries: dict[str, Any]) -> dict[str, Any]:
    """Build a captured "logs" event with a v2 payload: entries under a "logs" key."""
    return {"request_type": "logs", "payload": {"logs": list(entries)}, "application": {"language_version": "3.12.4"}}


def _error_tracking_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a captured Error Tracking intake request carrying the given payload."""
    return {
        "url": "http://testagent/evp_proxy/v4/api/v2/errorsintake",
        "body": base64.b64encode(json.dumps(payload).encode()).decode(),
    }


class _SnapshotTestAgent:
    """TestAgentAPI double serving successive snapshots of captured "logs" events."""

    def __init__(self, snapshots: list[list[dict[str, Any]]]) -> None:
        self._snapshots = snapshots
        self._snapshot_index = 0
        self.get_telemetry_events_calls = 0

    def get_telemetry_events(self, event_name: str) -> list[dict[str, Any]]:
        assert event_name == "logs"
        self.get_telemetry_events_calls += 1
        snapshot = self._snapshots[min(self._snapshot_index, len(self._snapshots) - 1)]
        self._snapshot_index += 1
        return snapshot


class _ErrorTrackingTestAgent:
    """TestAgentAPI double serving captured Error Tracking intake requests."""

    def __init__(self, requests_: list[dict[str, Any]]) -> None:
        self._requests = requests_

    def requests(self) -> list[dict[str, Any]]:
        return self._requests


def _snapshot_test_agent(snapshots: list[list[dict[str, Any]]]) -> TestAgentAPI:
    """Build a TestAgentAPI double serving successive snapshots of captured "logs" events."""
    return cast("TestAgentAPI", _SnapshotTestAgent(snapshots))


def _error_tracking_test_agent(requests_: list[dict[str, Any]]) -> TestAgentAPI:
    """Build a TestAgentAPI double serving captured Error Tracking intake requests."""
    return cast("TestAgentAPI", _ErrorTrackingTestAgent(requests_))


def _fake_test_library(lang: str) -> APMLibrary:
    """Build a test library double exposing the language under test."""
    return cast("APMLibrary", SimpleNamespace(lang=lang))


def _telemetry_serving(events: list[Any]) -> Callable[..., list[Any]]:
    """Build a telemetry read serving the given captured events."""

    def telemetry(*, clear: bool = False) -> list[Any]:
        assert not clear
        return events

    return telemetry


def _raise_connection_error(*, clear: bool = False) -> list[Any]:
    assert not clear
    raise requests.ConnectionError("agent down")


def _test_agent_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, telemetry: Callable[..., list[Any]]
) -> TestAgentAPI:
    """Build a TestAgentAPI whose telemetry read serves the given callable."""
    agent = TestAgentAPI(
        container_name="unit-test-agent",
        container_port=8126,
        host_log_folder=str(tmp_path),
        host_port=8126,
        otlp_http_host_port=4318,
        pytest_request=cast("pytest.FixtureRequest", SimpleNamespace(cls=None, node=SimpleNamespace(name="unit"))),
        network="unit-test-network",
    )
    monkeypatch.setattr(agent, "telemetry", telemetry)
    return agent


def test_is_crash_report_matches_only_the_report_entry() -> None:
    assert is_crash_report(_crash_report_entry())
    assert not is_crash_report(_crash_ping_entry())
    assert not is_crash_report(_debug_log_entry())
    assert not is_crash_report({"message": "unit test"})
    assert not is_crash_report("not a log entry")


def test_telemetry_log_entries_flattens_both_payload_shapes() -> None:
    ping_entry = _crash_ping_entry()
    report_entry = _crash_report_entry()
    debug_entry = _debug_log_entry()
    test_agent = _snapshot_test_agent(
        [
            [
                _v1_logs_event(ping_entry, debug_entry),
                _v2_logs_event(report_entry),
                {"request_type": "logs", "payload": {}, "application": {"language_version": "3.12.4"}},
            ]
        ]
    )

    entries = list(_crashtracking.telemetry_log_entries(test_agent))

    assert entries == [ping_entry, debug_entry, report_entry]


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(
            _v2_logs_event(_crash_ping_entry(), _debug_log_entry(), _crash_report_entry()),
            id="v2-report-after-ping-and-debug",
        ),
        pytest.param(_v1_logs_event(_debug_log_entry(), _crash_report_entry()), id="v1-report-after-debug"),
        pytest.param(_v2_logs_event(_crash_report_entry(), _crash_ping_entry()), id="v2-report-first"),
    ],
)
def test_wait_for_crash_report_selects_the_report_among_other_entries(event: dict[str, Any]) -> None:
    test_agent = _snapshot_test_agent([[event]])

    entry = _crashtracking.wait_for_crash_report(test_agent)

    assert entry == _crash_report_entry()


def test_wait_for_crash_report_polls_until_the_report_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_sleeps: list[float] = []
    monkeypatch.setattr(test_crashtracking.time, "sleep", recorded_sleeps.append)
    fake_agent = _SnapshotTestAgent(
        [
            [],
            [_v1_logs_event(_crash_ping_entry())],
            [_v2_logs_event(_crash_report_entry())],
        ]
    )

    entry = _crashtracking.wait_for_crash_report(cast("TestAgentAPI", fake_agent))

    assert entry == _crash_report_entry()
    assert fake_agent.get_telemetry_events_calls == 3
    assert recorded_sleeps == [test_crashtracking.CRASH_REPORT_POLL_INTERVAL_SECONDS] * 2


def test_wait_for_crash_report_scans_after_the_final_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    # A report arriving during the last poll interval must still be found: the
    # deadline loop scans again after the final clamped sleep.
    recorded_sleeps: list[float] = []
    monkeypatch.setattr(test_crashtracking.time, "sleep", recorded_sleeps.append)
    monotonic_values = iter([0.0, test_crashtracking.CRASH_REPORT_WAIT_SECONDS - 0.1])
    monkeypatch.setattr(test_crashtracking.time, "monotonic", lambda: next(monotonic_values))
    test_agent = _snapshot_test_agent(
        [
            [],
            [_v2_logs_event(_crash_report_entry())],
        ]
    )

    entry = _crashtracking.wait_for_crash_report(test_agent)

    assert entry == _crash_report_entry()
    assert recorded_sleeps == [pytest.approx(0.1)]


def test_wait_for_crash_report_raises_with_captured_tags_after_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_sleeps: list[float] = []
    monkeypatch.setattr(test_crashtracking.time, "sleep", recorded_sleeps.append)
    monotonic_values = iter([0.0, test_crashtracking.CRASH_REPORT_WAIT_SECONDS + 1])
    monkeypatch.setattr(test_crashtracking.time, "monotonic", lambda: next(monotonic_values))
    test_agent = _snapshot_test_agent(
        [
            [_v1_logs_event(_crash_ping_entry()), _v2_logs_event(_debug_log_entry())],
        ]
    )

    with pytest.raises(AssertionError) as exc_info:
        _crashtracking.wait_for_crash_report(test_agent)

    assert "Crash report not found in telemetry logs events" in str(exc_info.value)
    assert "is_crash_ping:true" in str(exc_info.value)
    assert "is_crash_debug:true" in str(exc_info.value)
    assert recorded_sleeps == []


def test_assert_no_crash_report_passes_without_any_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(test_crashtracking.time, "sleep", lambda _seconds: None)
    monotonic_values = iter([0.0, test_crashtracking.CRASH_REPORT_WAIT_SECONDS])
    monkeypatch.setattr(test_crashtracking.time, "monotonic", lambda: next(monotonic_values))
    test_agent = _snapshot_test_agent(
        [
            [_v1_logs_event(_crash_ping_entry()), _v2_logs_event(_debug_log_entry())],
        ]
    )

    _crashtracking.assert_no_crash_report(test_agent)


def test_assert_no_crash_report_fails_when_a_report_appears(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(test_crashtracking.time, "sleep", lambda _seconds: None)
    monotonic_values = iter([0.0, 1.0])
    monkeypatch.setattr(test_crashtracking.time, "monotonic", lambda: next(monotonic_values))
    test_agent = _snapshot_test_agent(
        [
            [_v1_logs_event(_crash_ping_entry())],
            [_v2_logs_event(_crash_report_entry())],
        ]
    )

    with pytest.raises(AssertionError):
        _crashtracking.assert_no_crash_report(test_agent)


def test_assert_crash_report_java_checks_the_severity_tag() -> None:
    java_entry = _log_entry("severity:crash,is_crash:true")

    _crashtracking.assert_crash_report(_fake_test_library("java"), java_entry)

    with pytest.raises(AssertionError):
        _crashtracking.assert_crash_report(_fake_test_library("java"), _log_entry("is_crash:true,si_signo:11"))


def test_assert_crash_report_checks_the_signal_tags() -> None:
    ruby_library = _fake_test_library("ruby")
    dotnet_library = _fake_test_library("dotnet")

    _crashtracking.assert_crash_report(ruby_library, _log_entry("uuid:r,is_crash:true,si_signo:11"))
    _crashtracking.assert_crash_report(ruby_library, _log_entry("uuid:r,is_crash:true,signum:11,fingerprint:ab:cd"))
    _crashtracking.assert_crash_report(dotnet_library, _log_entry("uuid:r,is_crash:true,signum:6"))

    with pytest.raises(AssertionError, match="signum/si_signo not found"):
        _crashtracking.assert_crash_report(ruby_library, _log_entry("uuid:r,is_crash:true"))

    with pytest.raises(AssertionError):
        _crashtracking.assert_crash_report(ruby_library, _log_entry("uuid:r,is_crash:true,si_signo:6"))


def test_get_telemetry_events_expands_batches_and_excludes_sidecar_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    top_level_event = {"request_type": "logs", "payload": {}, "application": {"language_version": "3.12.4"}}
    app_batch_message = {"request_type": "logs", "payload": {}}
    app_batch_event = {
        "request_type": "message-batch",
        "payload": [app_batch_message, {"request_type": "app-heartbeat", "payload": {}}],
        "application": {"language_version": "1.21.0"},
    }
    sidecar_batch_event = {
        "request_type": "message-batch",
        "payload": [{"request_type": "logs", "payload": {}}],
        "application": {"language_version": "SIDECAR"},
    }
    test_agent = _test_agent_api(
        tmp_path,
        monkeypatch,
        _telemetry_serving(
            [
                None,
                top_level_event,
                app_batch_event,
                sidecar_batch_event,
                {"request_type": "app-heartbeat", "payload": {}},
            ]
        ),
    )

    events = test_agent.get_telemetry_events("logs")

    assert events == [top_level_event, app_batch_message]


def test_get_telemetry_events_returns_no_events_on_request_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_agent = _test_agent_api(tmp_path, monkeypatch, _raise_connection_error)

    assert test_agent.get_telemetry_events("logs") == []


def test_wait_for_error_tracking_crash_report_skips_non_crash_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(test_crashtracking.time, "sleep", lambda _seconds: None)
    report_payload = {"ddsource": "crashtracker", "error": {"is_crash": True, "message": "system-tests crash"}}
    test_agent = _error_tracking_test_agent(
        [
            _error_tracking_request({"error": {"message": "some other error tracking event"}}),
            _error_tracking_request({"error": {"is_crash": False, "message": "crash ping"}}),
            _error_tracking_request(report_payload),
        ]
    )

    report = _crashtracking.wait_for_error_tracking_crash_report(test_agent)

    assert report == report_payload

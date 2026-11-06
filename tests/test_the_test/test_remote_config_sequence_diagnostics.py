from collections.abc import Callable
import json
from types import SimpleNamespace
from typing import Any

from utils import pytest, remote_config as rc


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


def _poll(index: int, *, runtime_id: str = "ruby-worker") -> dict[str, Any]:
    return {
        "path": "/v0.7/config",
        "log_filename": f"{runtime_id}-{index:02d}.json",
        "request": {
            "timestamp_start": f"2026-11-05T09:35:{index:02d}+00:00",
            "content": {
                "client": {
                    "id": f"client-{runtime_id}",
                    "client_tracer": {"runtime_id": runtime_id},
                    "state": {"targets_version": 12, "has_error": False, "config_states": []},
                }
            },
        },
        "response": {
            "status_code": 200,
            "headers": [["st-proxy-overwrite-rc-response", str(min(index, 14))]],
        },
    }


def _run_sequence(
    monkeypatch: pytest.MonkeyPatch, polls: list[dict[str, Any]], *, wait: bool = True
) -> tuple[list[str], list[bool], list[int]]:
    messages: list[str] = []
    predicate_results: list[bool] = []
    timeouts: list[int] = []
    sent: list[list[dict[str, Any]]] = []

    def fake_wait(predicate: Callable[[dict], bool], timeout: int) -> bool:
        timeouts.append(timeout)
        for poll in polls:
            completed = predicate(poll)
            predicate_results.append(completed)
            if completed:
                return True
        return False

    def get_data(*, path_filters: str) -> list[dict[str, Any]]:
        assert path_filters == r"/v0\.7/config"
        return [poll for poll in polls if poll["path"] == "/v0.7/config"]

    monkeypatch.setattr(rc.library, "wait_for", fake_wait)
    monkeypatch.setattr(rc.library, "get_data", get_data)
    monkeypatch.setattr(
        rc.SequentialRemoteConfigJsonMockedTracerResponse, "send", lambda self: sent.append(self.mocked_json_sequence)
    )
    monkeypatch.setattr(rc.logger, "stdout", messages.append)
    clock = iter([100.0, 185.25])
    monkeypatch.setattr(rc, "time", SimpleNamespace(monotonic=lambda: next(clock)))

    commands: list[dict[str, Any]] = [{} for _ in range(15)]
    rc.send_sequential_commands(commands, wait_for_all_command=wait)
    assert sent == [commands]
    return messages, predicate_results, timeouts


@pytest.mark.parametrize("follow_up", [False, True])
def test_sequence_reports_whether_final_follow_up_arrived(monkeypatch: pytest.MonkeyPatch, *, follow_up: bool) -> None:
    polls = [_poll(index) for index in range(15 + follow_up)]
    messages, results, timeouts = _run_sequence(monkeypatch, polls)

    assert timeouts == [85]
    assert results == [False] * 15 + ([True] if follow_up else [])
    assert f"returned={follow_up}, elapsed=85.250s, budget=85s" in messages[0]
    assert "expected_responses=15 plus a follow-up poll" in messages[0]
    assert "responses_by_runtime={'ruby-worker': 15}" in messages[0]
    assert f"last_evaluated_poll={polls[-1]['log_filename']}" in messages[0]
    summaries = [json.loads(line.removeprefix("RC sequence poll: ")) for line in messages[2:]]
    assert len(summaries) == 10
    assert [summary["log_filename"] for summary in summaries] == [poll["log_filename"] for poll in polls[-10:]]
    assert summaries[-1]["mocked_response_index"] == "14"
    assert summaries[-1]["targets_version"] == 12
    assert summaries[-1]["request_at"] == polls[-1]["request"]["timestamp_start"]


def test_sequence_exposes_completion_on_another_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    # Preserve the existing completion predicate, but expose the runtime of the
    # follow-up poll instead of implying that the first runtime acknowledged it.
    polls = [_poll(index) for index in range(15)] + [_poll(0, runtime_id="other-worker")]
    messages, results, _ = _run_sequence(monkeypatch, polls)

    assert results == [False] * 15 + [True]
    assert "returned=True" in messages[0]
    assert "responses_by_runtime={'ruby-worker': 15}" in messages[0]
    assert "last_evaluated_poll=other-worker-00.json" in messages[0]
    assert json.loads(messages[-1].removeprefix("RC sequence poll: "))["runtime_id"] == "other-worker"


def test_sequence_reports_no_remote_config_traffic(monkeypatch: pytest.MonkeyPatch) -> None:
    messages, results, _ = _run_sequence(monkeypatch, [{"path": "/v0.4/traces"}])

    assert results == [False]
    assert "returned=False" in messages[0]
    assert "responses_by_runtime={}, last_evaluated_poll=None" in messages[0]
    assert "last 0 captured polls" in messages[1]


def test_sequence_diagnostics_bound_errors_and_omit_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    poll = _poll(0)
    client = poll["request"]["content"]["client"]
    client["state"].update(
        {
            "has_error": True,
            "error": "e" * 1000,
            "backend_client_state": "private-backend-state",
            "config_states": [
                {"id": str(index), "version": 12, "apply_state": 3, "apply_error": "a" * 1000} for index in range(8)
            ],
        }
    )
    poll["request"]["headers"] = [["Authorization", "private-token"]]
    poll["response"]["content"] = {"target_files": [{"raw": "private-config"}]}
    messages, _, _ = _run_sequence(monkeypatch, [poll])
    summary = json.loads(messages[-1].removeprefix("RC sequence poll: "))

    assert summary["has_error"] is True
    assert summary["error"] == "e" * 200
    assert summary["config_state_count"] == 8
    assert len(summary["config_states"]) == 5
    assert all(config["apply_error"] == "a" * 200 for config in summary["config_states"])
    assert summary["client_id"] == "client-ruby-worker"
    assert summary["status_code"] == 200
    assert "private-" not in "\n".join(messages)


def test_sequence_diagnostics_failure_does_not_hide_other_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(rc.logger, "stdout", messages.append)
    monkeypatch.setattr(rc.library, "get_data", lambda **_kwargs: [{"request": "not a decoded request"}, _poll(0)])

    rc._log_sequence_polls()  # noqa: SLF001

    assert "could not summarize a poll (AttributeError)" in messages[1]
    assert json.loads(messages[-1].removeprefix("RC sequence poll: "))["runtime_id"] == "ruby-worker"


def test_sequence_diagnostics_read_failure_does_not_fail_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def read_error(**_kwargs: object) -> None:
        raise RuntimeError("interface unavailable")

    monkeypatch.setattr(rc.logger, "stdout", messages.append)
    monkeypatch.setattr(rc.library, "get_data", read_error)

    rc._log_sequence_polls()  # noqa: SLF001

    assert messages == ["RC sequence: could not read polls (RuntimeError)"]


def test_sequence_without_wait_does_not_collect_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    messages, results, timeouts = _run_sequence(monkeypatch, [], wait=False)

    assert messages == []
    assert results == []
    assert timeouts == []

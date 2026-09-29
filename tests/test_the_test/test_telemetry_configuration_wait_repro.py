from typing import Any

from utils import pytest, scenarios
from utils.docker_fixtures import TestAgentAPI


CONFIG_NAME = "OTEL_BLRP_MAX_QUEUE_SIZE"


def _configuration_event() -> dict[str, Any]:
    return {
        "request_type": "app-started",
        "runtime_id": "current-runtime",
        "tracer_time": 2,
        "application": {"service_name": "parametric", "language_version": "8.1"},
        "payload": {
            "configuration": [
                {"name": CONFIG_NAME, "origin": "default", "seq_id": 1, "value": 2048},
            ]
        },
    }


def _agent_with_responses(monkeypatch: pytest.MonkeyPatch, responses: list[list[dict[str, Any]]]) -> TestAgentAPI:
    test_agent = object.__new__(TestAgentAPI)

    def telemetry(*, clear: bool = False) -> list[dict[str, Any]]:
        assert clear is False
        return responses.pop(0) if len(responses) > 1 else responses[0]

    monkeypatch.setattr(test_agent, "telemetry", telemetry)
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)
    return test_agent


@scenarios.test_the_test
def test_control_configuration_is_available_on_first_nonempty_read(monkeypatch: pytest.MonkeyPatch) -> None:
    test_agent = _agent_with_responses(monkeypatch, [[_configuration_event()]])

    configurations = test_agent.wait_for_telemetry_configurations()

    assert configurations[CONFIG_NAME][0]["value"] == 2048


@scenarios.test_the_test
def test_repro_waits_past_unrelated_telemetry_for_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    unrelated_event = {
        "request_type": "app-heartbeat",
        "runtime_id": "previous-runtime",
        "tracer_time": 1,
        "application": {"service_name": "parametric", "language_version": "8.1"},
        "payload": {},
    }
    test_agent = _agent_with_responses(
        monkeypatch,
        [[unrelated_event], [unrelated_event, _configuration_event()]],
    )

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(CONFIG_NAME)

    assert entries, f"No telemetry configuration '{CONFIG_NAME}'"

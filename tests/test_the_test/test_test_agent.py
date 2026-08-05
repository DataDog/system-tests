from collections.abc import Callable

import pytest

from tests.parametric.conftest import assert_nodejs_telemetry_config
from utils import scenarios
from utils.docker_fixtures import TestAgentAPI


def _configuration_event(
    *, runtime_id: str, tracer_time: int, configurations: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "request_type": "app-started",
        "runtime_id": runtime_id,
        "tracer_time": tracer_time,
        "application": {
            "language_name": "nodejs",
            "language_version": "24.4.1",
            "service_name": "parametric",
            "tracer_version": "5.62.0",
        },
        "payload": {"configuration": configurations},
        "seq_id": 1,
    }


def _config(name: str, value: str, *, seq_id: int = 0) -> dict[str, object]:
    return {"name": name, "origin": "local_stable_config", "seq_id": seq_id, "value": value}


def _telemetry(events: list[dict[str, object]]) -> Callable[..., list[dict[str, object]]]:
    def get_events(*, clear: bool = False) -> list[dict[str, object]]:
        assert clear is False
        return events

    return get_events


@scenarios.test_the_test
def test_nodejs_telemetry_assertion_waits_for_post_restart_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    stale_event = _configuration_event(
        runtime_id="before-restart",
        tracer_time=1,
        configurations=[_config("DD_TRACE_PROPAGATION_STYLE", "datadog,tracecontext,baggage")],
    )
    current_event = _configuration_event(
        runtime_id="after-restart",
        tracer_time=2,
        configurations=[_config("DD_TRACE_PROPAGATION_STYLE", "tracecontext")],
    )
    telemetry_responses = [[stale_event], [stale_event, current_event]]

    test_agent = object.__new__(TestAgentAPI)

    def telemetry(*, clear: bool = False) -> list[dict[str, object]]:
        assert clear is False
        if len(telemetry_responses) > 1:
            return telemetry_responses.pop(0)
        return telemetry_responses[0]

    monkeypatch.setattr(test_agent, "telemetry", telemetry)

    assert_nodejs_telemetry_config(
        test_agent,
        {"dd_trace_propagation_style": "tracecontext"},
        runtime_id="after-restart",
    )


@scenarios.test_the_test
def test_nodejs_telemetry_assertion_rejects_stale_matching_value(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [
        _configuration_event(
            runtime_id="before-restart",
            tracer_time=1,
            configurations=[_config("DD_TRACE_PROPAGATION_STYLE", "tracecontext")],
        ),
        _configuration_event(
            runtime_id="after-restart",
            tracer_time=2,
            configurations=[_config("DD_TRACE_PROPAGATION_STYLE", "datadog")],
        ),
    ]
    test_agent = object.__new__(TestAgentAPI)
    monkeypatch.setattr(test_agent, "telemetry", _telemetry(events))
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)

    with pytest.raises(AssertionError):
        assert_nodejs_telemetry_config(
            test_agent,
            {"dd_trace_propagation_style": "tracecontext"},
            runtime_id="after-restart",
        )


@scenarios.test_the_test
def test_nodejs_telemetry_assertion_requires_one_runtime_to_match_all_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [
        _configuration_event(
            runtime_id="before-restart",
            tracer_time=1,
            configurations=[_config("DD_SERVICE", "expected"), _config("DD_ENV", "wrong")],
        ),
        _configuration_event(
            runtime_id="after-restart",
            tracer_time=2,
            configurations=[_config("DD_SERVICE", "wrong"), _config("DD_ENV", "expected")],
        ),
    ]
    test_agent = object.__new__(TestAgentAPI)
    monkeypatch.setattr(test_agent, "telemetry", _telemetry(events))
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)

    with pytest.raises(AssertionError):
        assert_nodejs_telemetry_config(
            test_agent,
            {"dd_service": "expected", "dd_env": "expected"},
            runtime_id="after-restart",
        )


@scenarios.test_the_test
def test_nodejs_telemetry_assertion_uses_latest_configuration_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [
        _configuration_event(
            runtime_id="after-restart",
            tracer_time=2,
            configurations=[
                _config("DD_SERVICE", "expected", seq_id=0),
                _config("DD_SERVICE", "wrong", seq_id=1),
            ],
        )
    ]
    test_agent = object.__new__(TestAgentAPI)
    monkeypatch.setattr(test_agent, "telemetry", _telemetry(events))
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)

    with pytest.raises(AssertionError):
        assert_nodejs_telemetry_config(test_agent, {"dd_service": "expected"}, runtime_id="after-restart")


@scenarios.test_the_test
def test_wait_for_telemetry_runtime_id_ignores_excluded_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    stale_event = _configuration_event(runtime_id="before-restart", tracer_time=1, configurations=[])
    current_event = _configuration_event(runtime_id="after-restart", tracer_time=2, configurations=[])
    telemetry_responses = [[stale_event], [stale_event, current_event]]
    test_agent = object.__new__(TestAgentAPI)

    def telemetry(*, clear: bool = False) -> list[dict[str, object]]:
        assert clear is False
        if len(telemetry_responses) > 1:
            return telemetry_responses.pop(0)
        return telemetry_responses[0]

    monkeypatch.setattr(test_agent, "telemetry", telemetry)

    runtime_id = test_agent.wait_for_telemetry_runtime_id(exclude={"before-restart"})

    assert runtime_id == "after-restart"

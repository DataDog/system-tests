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
        "payload": {"configuration": configurations},
    }


def _config(name: str, value: str, *, seq_id: int = 0) -> dict[str, object]:
    return {"name": name, "seq_id": seq_id, "value": value}


def _test_agent(monkeypatch: pytest.MonkeyPatch, responses: list[list[dict[str, object]]]) -> TestAgentAPI:
    test_agent = object.__new__(TestAgentAPI)

    def telemetry(*, clear: bool = False) -> list[dict[str, object]]:
        assert clear is False
        return responses.pop(0) if len(responses) > 1 else responses[0]

    monkeypatch.setattr(test_agent, "telemetry", telemetry)
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)
    return test_agent


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
    test_agent = _test_agent(monkeypatch, [[stale_event], [stale_event, current_event]])
    runtime_id = test_agent.wait_for_telemetry_runtime_id(exclude="before-restart")

    assert_nodejs_telemetry_config(
        test_agent,
        {"dd_trace_propagation_style": "tracecontext"},
        runtime_id=runtime_id,
    )


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("events", "expected"),
    [
        (
            [
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
            ],
            {"dd_trace_propagation_style": "tracecontext"},
        ),
        (
            [
                _configuration_event(
                    runtime_id="after-restart",
                    tracer_time=2,
                    configurations=[
                        _config("DD_SERVICE", "expected", seq_id=0),
                        _config("DD_SERVICE", "wrong", seq_id=1),
                    ],
                )
            ],
            {"dd_service": "expected"},
        ),
    ],
    ids=["stale-match", "superseded-sequence"],
)
def test_nodejs_telemetry_assertion_rejects_invalid_runtime_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    events: list[dict[str, object]],
    expected: dict[str, object],
) -> None:
    test_agent = _test_agent(monkeypatch, [events])

    with pytest.raises(AssertionError):
        assert_nodejs_telemetry_config(test_agent, expected, runtime_id="after-restart")

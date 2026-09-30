from tests.parametric.conftest import APMLibrary, assert_nodejs_telemetry_config, restart_and_get_runtime_id
from utils import pytest, scenarios
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


def _config(name: str, value: str, *, seq_id: int | None = None) -> dict[str, object]:
    config: dict[str, object] = {"name": name, "value": value}
    if seq_id is not None:
        config["seq_id"] = seq_id
    return config


def _test_agent(monkeypatch: pytest.MonkeyPatch, responses: list[list[dict[str, object]]]) -> TestAgentAPI:
    test_agent = object.__new__(TestAgentAPI)

    def telemetry(*, clear: bool = False) -> list[dict[str, object]]:
        assert clear is False
        return responses.pop(0) if len(responses) > 1 else responses[0]

    monkeypatch.setattr(test_agent, "telemetry", telemetry)
    monkeypatch.setattr("utils.docker_fixtures._test_agent.time.sleep", lambda _seconds: None)
    return test_agent


@scenarios.test_the_test
def test_wait_for_telemetry_runtime_id_uses_app_started_wait_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    stale_event = _configuration_event(runtime_id="before-restart", tracer_time=1, configurations=[])
    current_event = _configuration_event(runtime_id="after-restart", tracer_time=2, configurations=[])
    responses = [[stale_event] for _ in range(201)] + [[stale_event, current_event]]
    test_agent = _test_agent(monkeypatch, responses)

    assert test_agent.wait_for_telemetry_runtime_id(exclude="before-restart") == "after-restart"


@scenarios.test_the_test
def test_restart_and_get_runtime_id_waits_for_new_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None]] = []
    test_agent = object.__new__(TestAgentAPI)
    test_library = object.__new__(APMLibrary)
    test_library.lang = "nodejs"

    def wait_for_runtime_id(*, exclude: str | None = None) -> str:
        calls.append(("wait", exclude))
        return "before-restart" if exclude is None else "after-restart"

    def restart() -> None:
        calls.append(("restart", None))

    monkeypatch.setattr(test_agent, "wait_for_telemetry_runtime_id", wait_for_runtime_id)
    monkeypatch.setattr(test_library, "container_restart", restart)

    assert restart_and_get_runtime_id(test_agent, test_library) == "after-restart"
    assert calls == [("wait", None), ("restart", None), ("wait", "before-restart")]


@scenarios.test_the_test
def test_nodejs_telemetry_assertion_uses_requested_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
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
    test_agent = _test_agent(monkeypatch, [[stale_event, current_event]])

    assert_nodejs_telemetry_config(
        test_agent,
        {"dd_trace_propagation_style": "tracecontext"},
        runtime_id="after-restart",
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
                        _config("DD_SERVICE", "expected"),
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

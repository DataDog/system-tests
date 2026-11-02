"""Remote config without an agent: the library polls the (mocked) backend itself, and reports its state there"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from utils import scenarios, pytest
from utils import _remote_config
from utils.dd_constants import RemoteConfigApplyState as ApplyState
from utils.proxy._decoders.protobuf_schemas import LatestConfigsRequest
from utils.proxy._deserializer import deserialize_http_message


def _poll(*, targets_version: int, config_states: list[dict[str, Any]]) -> dict[str, Any]:
    """A recorded /api/v0.1/configurations request, as a library polling the backend itself sends it"""
    request = LatestConfigsRequest(products=["APM_TRACING"])
    client = request.active_clients.add(  # type: ignore[attr-defined]
        id="client-id", is_tracer=True, products=["APM_TRACING"]
    )
    client.state.targets_version = targets_version
    for config_state in config_states:
        client.state.config_states.add(**config_state)

    message: dict[str, Any] = {"headers": [("Content-Type", "application/x-protobuf")]}
    message["content"] = deserialize_http_message(
        "/api/v0.1/configurations", message, request.SerializeToString(), "agent", "request", None
    )
    return {"path": "/api/v0.1/configurations", "request": message}


@scenarios.test_the_test
def test_decodes_the_remote_config_poll_request():
    content = _poll(
        targets_version=3, config_states=[{"id": "abc", "version": 1, "product": "APM_TRACING", "apply_state": 2}]
    )["request"]["content"]

    assert content["products"] == ["APM_TRACING"]
    state = content["active_clients"][0]["state"]
    # protobuf renders 64-bit integers as strings
    assert state["targets_version"] == "3"
    assert state["config_states"] == [{"id": "abc", "version": "1", "product": "APM_TRACING", "apply_state": "2"}]


@scenarios.test_the_test
def test_agentless_client_state_reads_integers():
    data = _poll(targets_version=3, config_states=[{"id": "abc", "version": 1, "product": "APM_TRACING"}])

    state = _remote_config._agentless_client_state(data)  # noqa: SLF001

    assert state["targets_version"] == 3
    # apply_state 0 (unknown) is a default value: omitted by protobuf
    assert state["config_states"] == [{"id": "abc", "version": 1, "product": "APM_TRACING", "apply_state": 0}]


@scenarios.test_the_test
def test_agentless_client_state_without_client():
    assert _remote_config._agentless_client_state({"request": {"content": {}}}) == {  # noqa: SLF001
        "targets_version": 0,
        "config_states": [],
    }


@scenarios.test_the_test
def test_send_state_without_agent_waits_for_the_library_poll_on_the_mocked_backend(monkeypatch: pytest.MonkeyPatch):
    sent: list = []
    scenario = SimpleNamespace(
        rc_api_enabled=True,
        rc_backend_enabled=True,
        include_agent=False,
        use_proxy_for_agent=False,
        mocked_backend_container=SimpleNamespace(client=SimpleNamespace(set_mocked_responses=sent.extend)),
    )
    monkeypatch.setattr(_remote_config, "context", SimpleNamespace(scenario=scenario, library=SimpleNamespace(name="")))
    monkeypatch.setattr(_remote_config.time, "sleep", lambda _: None)

    payload = _remote_config.build_debugger_command(probes=[{"id": "probe-1", "type": "LOG_PROBE"}], version=1)
    polls = [
        # the previous config, then the new one, applied
        _poll(targets_version=0, config_states=[]),
        _poll(
            targets_version=1,
            config_states=[{"id": "logProbe_probe-1", "version": 1, "product": "LIVE_DEBUGGING", "apply_state": 2}],
        ),
    ]

    def wait_for(matcher: Callable[[dict], bool], timeout: int) -> bool:  # noqa: ARG001
        return any(matcher(poll) for poll in polls)

    def library_wait_for(*_: object, **__: object) -> bool:
        raise AssertionError("without agent, the library does not poll /v0.7/config")

    monkeypatch.setattr(_remote_config.mocked_backend, "wait_for", wait_for)
    monkeypatch.setattr(_remote_config.library, "wait_for", library_wait_for)

    result = _remote_config.send_state(payload, target="backend")

    assert [response.path for response in sent] == ["/api/v0.1/configurations"]
    assert result.state == ApplyState.ACKNOWLEDGED
    assert result.configs["logProbe_probe-1"]["apply_state"] == ApplyState.ACKNOWLEDGED

from utils import features, pytest, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    ("urls", "expected"),
    [
        ([], False),
        (["http://agent/telemetry/proxy/api/v2/apmtelemetry"], False),
        (["http://agent/v0.4/traces"], False),
        (["http://agent/v0.5/traces"], False),
        (["http://agent/v0.7/traces"], False),
        (["http://agent/v1.0/traces"], True),
        (["http://agent/v1.0/traces?test_session_token=example"], True),
        (["http://agent/v1.0/traces", "http://agent/v0.4/traces"], False),
        (["http://agent/v1.0/traces", "http://agent/telemetry/proxy/api/v2/apmtelemetry"], True),
    ],
)
def test_v1_trace_detection_preserves_legacy_requirements(
    monkeypatch: pytest.MonkeyPatch, urls: list[str], *, expected: bool
) -> None:
    agent = object.__new__(TestAgentAPI)
    captured_requests = [AgentRequest(method="POST", url=url, headers={}, body="") for url in urls]

    def requests() -> list[AgentRequest]:
        return captured_requests

    monkeypatch.setattr(agent, "requests", requests)

    assert agent.uses_v1_trace_payloads() is expected

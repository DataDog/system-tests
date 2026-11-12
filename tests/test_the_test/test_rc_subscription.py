"""Negative RC assertions must accept silence without hiding activation or broken evidence."""

import base64
import binascii
from typing import Any
from unittest.mock import patch

import requests

from utils import pytest, scenarios
from utils.dd_constants import Capabilities
from utils.docker_fixtures import TestAgentAPI


FFE_BIT = (1 << Capabilities.FFE_FLAG_CONFIGURATION_RULES).to_bytes(8, "big")


def _agent_with_requests(monkeypatch: pytest.MonkeyPatch, clients: list[dict[str, Any]]) -> TestAgentAPI:
    agent = object.__new__(TestAgentAPI)
    monkeypatch.setattr(agent, "rc_requests", lambda: [{"body": {"client": client}} for client in clients])
    return agent


@scenarios.test_the_test
@pytest.mark.parametrize(
    "clients",
    [
        pytest.param([], id="no-requests"),
        pytest.param([{}], id="missing-capabilities"),
        pytest.param([{"capabilities": None}], id="null-capabilities"),
        pytest.param([{"capabilities": ""}], id="empty-base64"),
        pytest.param([{"capabilities": []}], id="empty-byte-array"),
        pytest.param([{"capabilities": "AA=="}], id="zero-base64"),
        pytest.param([{"capabilities": [0]}], id="zero-byte-array"),
        pytest.param([{"products": ["ASM"], "capabilities": "Ag=="}], id="unrelated-subscription"),
    ],
)
def test_negative_rc_allows_absent_subscription(monkeypatch: pytest.MonkeyPatch, clients: list[dict[str, Any]]) -> None:
    agent = _agent_with_requests(monkeypatch, clients)
    agent.assert_no_rc_subscription("FFE_FLAGS", Capabilities.FFE_FLAG_CONFIGURATION_RULES)


@scenarios.test_the_test
@pytest.mark.parametrize(
    "client",
    [
        pytest.param({"products": ["FFE_FLAGS"], "capabilities": ""}, id="product-only"),
        pytest.param({"capabilities": base64.b64encode(FFE_BIT).decode()}, id="capability-base64-only"),
        pytest.param({"capabilities": list(FFE_BIT)}, id="capability-byte-array-only"),
    ],
)
def test_negative_rc_rejects_any_captured_activation(monkeypatch: pytest.MonkeyPatch, client: dict[str, Any]) -> None:
    # A later empty snapshot must not erase an earlier subscription, even if only
    # one of its product/capability fields advertised the feature.
    agent = _agent_with_requests(monkeypatch, [{}, client, {}])
    with pytest.raises(AssertionError, match="Unexpected RemoteConfig"):
        agent.assert_no_rc_subscription("FFE_FLAGS", Capabilities.FFE_FLAG_CONFIGURATION_RULES)


@scenarios.test_the_test
@pytest.mark.parametrize("capabilities", ["!invalid!", [256]])
def test_negative_rc_rejects_malformed_evidence(monkeypatch: pytest.MonkeyPatch, capabilities: str | list[int]) -> None:
    agent = _agent_with_requests(monkeypatch, [{"capabilities": capabilities}])
    with pytest.raises((binascii.Error, ValueError)):
        agent.assert_no_rc_subscription("FFE_FLAGS", Capabilities.FFE_FLAG_CONFIGURATION_RULES)


@scenarios.test_the_test
def test_negative_rc_propagates_agent_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_with_requests(monkeypatch, [])
    with (
        patch.object(agent, "rc_requests", side_effect=requests.ConnectionError("agent unavailable")),
        pytest.raises(requests.ConnectionError, match="agent unavailable"),
    ):
        agent.assert_no_rc_subscription("FFE_FLAGS", Capabilities.FFE_FLAG_CONFIGURATION_RULES)


@scenarios.test_the_test
def test_positive_rc_still_requires_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_with_requests(monkeypatch, [{"capabilities": ""}])
    with pytest.raises(AssertionError, match="RemoteConfig capabilities were empty"):
        agent.wait_for_rc_capabilities(wait_loops=1)

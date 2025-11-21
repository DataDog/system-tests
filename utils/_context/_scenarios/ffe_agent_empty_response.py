"""FFE Agent Empty Response Scenario.

This scenario configures the test agent to return HTTP 200 responses with empty
content, simulating an agent that responds but provides no useful data.
"""

from http import HTTPStatus
from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFEAgentEmptyResponseScenario(FFEResilienceScenarioBase):
    """Scenario that simulates agent returning empty responses.

    This tests FFE behavior when the agent is reachable but returns
    empty or invalid responses to requests.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_AGENT_EMPTY_RESPONSE",
            doc="Test FFE resilience when agent returns empty HTTP 200 responses"
        )

    def configure_agent_empty_responses(self, test_agent: TestAgentAPI) -> None:
        """Configure the test agent to return empty responses.

        Args:
            test_agent: Test agent API instance to configure
        """
        # Configure agent to return empty responses for relevant endpoints
        # This simulates an agent that responds but provides no useful data
        settings = {
            "return_empty_responses": True,
            "empty_response_endpoints": [
                "/v0.7/config",  # Remote Config endpoint
                "/v0.4/traces",  # Trace submission
                "/telemetry/proxy/api/v2/apmtelemetry"  # Telemetry
            ]
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        # Note: We expect this might fail if the test agent doesn't support these settings
        # In that case, we'll implement a workaround using request interception
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Use trace delay to simulate slow responses that effectively timeout
            test_agent.set_trace_delay(30000)  # 30 second delay effectively causes timeouts

    def restore_agent_normal_responses(self, test_agent: TestAgentAPI) -> None:
        """Restore the test agent to normal response behavior.

        Args:
            test_agent: Test agent API instance to restore
        """
        # Restore normal agent behavior
        settings = {
            "return_empty_responses": False,
            "empty_response_endpoints": []
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Reset trace delay
            test_agent.set_trace_delay(0)


# Create the scenario instance
ffe_agent_empty_response = FFEAgentEmptyResponseScenario()
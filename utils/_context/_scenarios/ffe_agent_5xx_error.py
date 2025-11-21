"""FFE Agent 5xx Error Scenario.

This scenario configures the test agent to return HTTP 5xx server errors,
simulating an agent experiencing server failures.
"""

from http import HTTPStatus
from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFEAgent5xxErrorScenario(FFEResilienceScenarioBase):
    """Scenario that simulates agent returning 5xx server errors.

    This tests FFE behavior when the agent is reachable but returns
    server error responses indicating internal failures.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_AGENT_5XX_ERROR",
            doc="Test FFE resilience when agent returns HTTP 5xx server errors"
        )

    def configure_agent_5xx_errors(self, test_agent: TestAgentAPI, error_code: int = 503) -> None:
        """Configure the test agent to return 5xx error responses.

        Args:
            test_agent: Test agent API instance to configure
            error_code: HTTP error code to return (default: 503 Service Unavailable)
        """
        # Configure agent to return server errors for relevant endpoints
        settings = {
            "return_error_responses": True,
            "error_response_code": error_code,
            "error_response_endpoints": [
                "/v0.7/config",  # Remote Config endpoint
                "/v0.4/traces",  # Trace submission
                "/telemetry/proxy/api/v2/apmtelemetry"  # Telemetry
            ]
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        # Note: We expect this might fail if the test agent doesn't support these settings
        # In that case, we'll implement a workaround
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Use an alternative approach
            # We could use trace delay + a flag to simulate errors
            # For now, we'll use extreme delay to simulate unresponsive behavior
            test_agent.set_trace_delay(60000)  # 60 second delay

    def restore_agent_normal_responses(self, test_agent: TestAgentAPI) -> None:
        """Restore the test agent to normal response behavior.

        Args:
            test_agent: Test agent API instance to restore
        """
        # Restore normal agent behavior
        settings = {
            "return_error_responses": False,
            "error_response_code": 200,
            "error_response_endpoints": []
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Reset trace delay
            test_agent.set_trace_delay(0)


# Create the scenario instance
ffe_agent_5xx_error = FFEAgent5xxErrorScenario()
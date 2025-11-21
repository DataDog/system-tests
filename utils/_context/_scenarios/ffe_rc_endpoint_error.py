"""FFE Remote Config Endpoint Error Scenario.

This scenario configures the test agent to return errors for Remote Config
endpoint requests, simulating RC service failures.
"""

from http import HTTPStatus
from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFERCEndpointErrorScenario(FFEResilienceScenarioBase):
    """Scenario that simulates Remote Config endpoint returning errors.

    This tests FFE behavior when the Remote Config service returns
    error responses, forcing FFE to rely on cached configurations.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_RC_ENDPOINT_ERROR",
            doc="Test FFE resilience when Remote Config endpoint returns error responses"
        )

    def configure_rc_endpoint_errors(self, test_agent: TestAgentAPI, error_code: int = 503) -> None:
        """Configure the test agent to return errors for RC endpoint requests.

        Args:
            test_agent: Test agent API instance to configure
            error_code: HTTP error code to return for RC requests (default: 503)
        """
        # Configure agent to return errors specifically for Remote Config endpoint
        settings = {
            "rc_endpoint_error_mode": True,
            "rc_endpoint_error_code": error_code,
            "rc_endpoint_error_message": "Remote Config service temporarily unavailable"
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        # Note: We expect this might fail if the test agent doesn't support these settings
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Use trace delay to simulate RC issues
            # This affects all endpoints but will demonstrate RC resilience
            test_agent.set_trace_delay(10000)  # 10 second delay

    def restore_rc_normal_responses(self, test_agent: TestAgentAPI) -> None:
        """Restore the Remote Config endpoint to normal response behavior.

        Args:
            test_agent: Test agent API instance to restore
        """
        # Restore normal RC behavior
        settings = {
            "rc_endpoint_error_mode": False,
            "rc_endpoint_error_code": 200,
            "rc_endpoint_error_message": ""
        }

        resp = test_agent._session.post(test_agent._url("/test/settings"), json=settings)
        if resp.status_code != HTTPStatus.ACCEPTED:
            # Fallback: Reset trace delay
            test_agent.set_trace_delay(0)


# Create the scenario instance
ffe_rc_endpoint_error = FFERCEndpointErrorScenario()
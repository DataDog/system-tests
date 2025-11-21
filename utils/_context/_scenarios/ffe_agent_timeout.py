"""FFE Agent Timeout Scenario.

This scenario configures the test agent to introduce extreme delays,
simulating an agent that becomes unresponsive and causes requests to timeout.
"""

from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFEAgentTimeoutScenario(FFEResilienceScenarioBase):
    """Scenario that simulates agent request timeouts.

    This tests FFE behavior when the agent becomes unresponsive
    and requests timeout due to extreme delays.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_AGENT_TIMEOUT",
            doc="Test FFE resilience when agent requests timeout due to extreme delays"
        )

    def configure_agent_timeouts(self, test_agent: TestAgentAPI, timeout_delay: int = 45000) -> None:
        """Configure the test agent to introduce extreme delays causing timeouts.

        Args:
            test_agent: Test agent API instance to configure
            timeout_delay: Delay in milliseconds (default: 45 seconds)
        """
        # Use the existing set_trace_delay method to introduce extreme delays
        # This will cause most requests to timeout before receiving responses
        test_agent.set_trace_delay(timeout_delay)

    def restore_agent_normal_responses(self, test_agent: TestAgentAPI) -> None:
        """Restore the test agent to normal response behavior.

        Args:
            test_agent: Test agent API instance to restore
        """
        # Reset trace delay to restore normal behavior
        test_agent.set_trace_delay(0)


# Create the scenario instance
ffe_agent_timeout = FFEAgentTimeoutScenario()
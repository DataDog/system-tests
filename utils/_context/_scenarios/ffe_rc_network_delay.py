"""FFE Remote Config Network Delay Scenario.

This scenario introduces network delays for Remote Config requests,
simulating network issues or slow RC service responses.
"""

from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFERCNetworkDelayScenario(FFEResilienceScenarioBase):
    """Scenario that simulates Remote Config network delays.

    This tests FFE behavior when Remote Config requests are delayed
    due to network issues or slow service responses.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_RC_NETWORK_DELAY",
            doc="Test FFE resilience when Remote Config requests experience network delays"
        )

    def configure_rc_network_delays(self, test_agent: TestAgentAPI, delay_ms: int = 5000) -> None:
        """Configure network delays for Remote Config requests.

        Args:
            test_agent: Test agent API instance to configure
            delay_ms: Delay in milliseconds for RC requests (default: 5 seconds)
        """
        # Use the existing set_trace_delay method to introduce delays
        # This will affect all requests, but primarily tests RC resilience
        test_agent.set_trace_delay(delay_ms)

    def restore_rc_normal_timing(self, test_agent: TestAgentAPI) -> None:
        """Restore normal timing for Remote Config requests.

        Args:
            test_agent: Test agent API instance to restore
        """
        # Reset trace delay to restore normal timing
        test_agent.set_trace_delay(0)


# Create the scenario instance
ffe_rc_network_delay = FFERCNetworkDelayScenario()
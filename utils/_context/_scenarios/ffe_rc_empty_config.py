"""FFE Remote Config Empty Configuration Scenario.

This scenario configures Remote Config to return valid but empty
flag configurations, testing FFE behavior with no available flags.
"""

from typing import Any
from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFERCEmptyConfigScenario(FFEResilienceScenarioBase):
    """Scenario that provides empty Remote Config flag configurations.

    This tests FFE behavior when Remote Config successfully responds
    but contains no flag definitions, forcing fallback to defaults.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_RC_EMPTY_CONFIG",
            doc="Test FFE resilience when Remote Config returns empty flag configurations"
        )

    def configure_empty_rc_config(self, test_agent: TestAgentAPI) -> dict[str, Any]:
        """Configure Remote Config to return an empty configuration.

        Args:
            test_agent: Test agent API instance to configure

        Returns:
            Empty UFC configuration data
        """
        # Create an empty UFC configuration
        empty_ufc_data = {
            "flags": {},  # No flags defined
            "flagsMetadata": {},  # No flag metadata
            "version": 1
        }

        return empty_ufc_data

    def restore_normal_rc_config(self, test_agent: TestAgentAPI, normal_ufc_data: dict[str, Any]) -> None:
        """Restore normal Remote Config configuration.

        Args:
            test_agent: Test agent API instance
            normal_ufc_data: Normal UFC configuration data to restore
        """
        # This method would be called to restore the normal configuration
        # The actual restoration is handled by the test using set_and_wait_ffe_rc
        pass


# Create the scenario instance
ffe_rc_empty_config = FFERCEmptyConfigScenario()
"""FFE Remote Config Malformed Response Scenario.

This scenario configures Remote Config to return corrupted or invalid
configuration data, testing FFE error handling and fallback behavior.
"""

from typing import Any
from utils.docker_fixtures._test_agent import TestAgentAPI

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFERCMalformedResponseScenario(FFEResilienceScenarioBase):
    """Scenario that provides malformed Remote Config responses.

    This tests FFE behavior when Remote Config returns corrupted
    or invalid configuration data, testing error handling and fallback.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_RC_MALFORMED_RESPONSE",
            doc="Test FFE resilience when Remote Config returns malformed/corrupted configuration data"
        )

    def create_malformed_rc_config(self) -> dict[str, Any]:
        """Create a malformed UFC configuration for testing.

        Returns:
            Malformed UFC configuration data that should be rejected
        """
        # Create a malformed UFC configuration with missing required fields
        # and invalid structure that should cause parsing errors
        malformed_ufc_data = {
            "flags": {
                "malformed-flag": {
                    # Missing required fields like 'variationType', 'allocations'
                    "enabled": True,
                    "invalid_field": "this should not be here",
                    # Malformed allocations structure
                    "allocations": "this should be an array",
                }
            },
            # Missing required flagsMetadata
            "version": "invalid_version_type",  # Should be int, not string
            "extra_invalid_field": {"nested": "invalid data"}
        }

        return malformed_ufc_data

    def create_corrupted_json_config(self) -> str:
        """Create corrupted JSON that cannot be parsed.

        Returns:
            Invalid JSON string that should cause parsing errors
        """
        # Return intentionally malformed JSON
        corrupted_json = '{"flags": {"test-flag": {"enabled": true, "allocations": [}' # Missing closing brackets

        return corrupted_json

    def create_wrong_schema_config(self) -> dict[str, Any]:
        """Create configuration with wrong schema structure.

        Returns:
            Configuration that doesn't match expected UFC schema
        """
        # Create config that looks like valid JSON but wrong schema
        wrong_schema_data = {
            "not_flags": {  # Should be "flags"
                "test": "data"
            },
            "wrong_structure": True,
            "version": -1  # Invalid version number
        }

        return wrong_schema_data


# Create the scenario instance
ffe_rc_malformed_response = FFERCMalformedResponseScenario()
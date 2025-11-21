"""FFE Agent Connection Refused Scenario.

This scenario stops the test agent container entirely, simulating
complete agent unavailability with connection refused errors.
"""

import time
from utils._context.docker import get_docker_client
from utils.docker_fixtures._test_agent import TestAgentAPI
from utils._logger import logger

from .ffe_resilience_base import FFEResilienceScenarioBase


class FFEAgentConnectionRefusedScenario(FFEResilienceScenarioBase):
    """Scenario that simulates complete agent unavailability.

    This tests FFE behavior when the agent is completely unreachable,
    causing connection refused errors for all requests.
    """

    def __init__(self) -> None:
        super().__init__(
            name="FFE_AGENT_CONNECTION_REFUSED",
            doc="Test FFE resilience when agent is completely unavailable (connection refused)"
        )

    def stop_agent_container(self, test_agent: TestAgentAPI) -> None:
        """Stop the test agent container to simulate connection refused.

        Args:
            test_agent: Test agent API instance
        """
        try:
            # Get the Docker client and stop the test agent container
            docker_client = get_docker_client()
            agent_container = docker_client.containers.get(test_agent.container_name)
            agent_container.stop()

            # Give some time for connections to be dropped
            time.sleep(2.0)

            logger.info(f"Stopped agent container {test_agent.container_name} for connection refused simulation")
        except Exception as e:
            logger.warning(f"Failed to stop agent container: {e}")
            # Continue with the test - the connection issues may still occur

    def restart_agent_container(self, test_agent: TestAgentAPI) -> None:
        """Restart the test agent container to restore normal operation.

        Args:
            test_agent: Test agent API instance
        """
        try:
            # Get the Docker client and restart the test agent container
            docker_client = get_docker_client()
            agent_container = docker_client.containers.get(test_agent.container_name)
            agent_container.start()

            # Give agent time to initialize
            time.sleep(3.0)

            logger.info(f"Restarted agent container {test_agent.container_name}")
        except Exception as e:
            # If restart fails, try to get a fresh container reference
            try:
                docker_client = get_docker_client()
                agent_container = docker_client.containers.get(test_agent.container_name)
                agent_container.start()
                time.sleep(3.0)
                logger.info(f"Restarted agent container {test_agent.container_name} after retry")
            except Exception as retry_e:
                # Log the issue but don't fail the test - pytest cleanup will handle it
                logger.warning(f"Could not restart test agent container: {retry_e}")


# Create the scenario instance
ffe_agent_connection_refused = FFEAgentConnectionRefusedScenario()
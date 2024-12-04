from utils.tools import logger

from .core import ScenarioGroup
from .endtoend import EndToEndScenario


class Ipv6Scenario(EndToEndScenario):
    def __init__(self, name) -> None:
        super().__init__(
            name,
            enable_ipv6=True,
            scenario_groups=[ScenarioGroup.ESSENTIALS, ScenarioGroup.TRACER_RELEASE],
            doc="Test the agent/lib communication using an IPv6 address",
        )

    def _start_containers(self):
        self.proxy_container.start(self._network)

        agent_container_ip = self.proxy_container.network_ip(self._network)
        logger.stdout(f"Lib is configured with DD_AGENT_HOST: {agent_container_ip}")

        self.weblog_container.environment["DD_AGENT_HOST"] = agent_container_ip

        super()._start_containers()

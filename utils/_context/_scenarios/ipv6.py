from utils._logger import logger

from .core import scenario_groups
from .endtoend import EndToEndScenario


class IPV6Scenario(EndToEndScenario):
    def __init__(self, name: str) -> None:
        super().__init__(
            name,
            enable_ipv6=True,
            scenario_groups=[scenario_groups.ipv6],
            use_proxy_for_agent=True,
            use_proxy_for_weblog=False,
            doc=(
                "Test the agent/lib communication using an IPv6 address. We do not use the proxy between "
                "the lib and the agent to check that the agent correctly accept IPv6 traffic"
            ),
        )

    def _start_containers(self):
        self.proxy_container.start(self._network)
        self.agent_container.start(self._network)

        agent_container_ip = self.agent_container.network_ipv6(self._network)
        logger.stdout(f"Lib is configured with DD_AGENT_HOST: {agent_container_ip}")

        self.weblog_container.environment["DD_AGENT_HOST"] = agent_container_ip

        super()._start_containers()

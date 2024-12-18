from .endtoend import EndToEndScenario


class IPV6Scenario(EndToEndScenario):
    def __init__(self, name):
        super().__init__(name, doc="Library use a DD_AGENT_HOST using an IPv6 address")

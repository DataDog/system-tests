from utils import scenarios, weblog, interfaces, features


@features.agent_host_ipv6
@scenarios.ipv6
class Test_Basic:
    def setup_main(self):
        self.r = weblog.get("/")

    def test_main(self):
        interfaces.agent.assert_trace_exists(self.r)

from utils import scenarios, weblog, interfaces


@scenarios.ipv6
class Test_Basic:
    def setup_main(self):
        self.r = weblog.get("/")

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)
        interfaces.agent.assert_trace_exists(self.r)

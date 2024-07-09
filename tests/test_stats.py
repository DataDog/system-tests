from utils import interfaces, weblog
from utils._context._scenarios import scenarios
from utils.tools import logger

#@scenarios.disable_trace_stats
class Test_Stats:
    """Test client-side stats are compatible with Agent implementation"""

    def setup_main(self):
        self.r = weblog.get("/")

    def test_stats(self):
        stats_count = 0
        for s in interfaces.agent.get_stats(resource="GET /"):
            stats_count += 1
            logger.debug(f"GOT AN S {s}")
            assert "weblog" == s["Service"]
            assert 1 == s["Hits"]
            assert 200 == s["HTTPStatusCode"]
        assert stats_count == 1

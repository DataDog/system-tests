from utils import interfaces, weblog
from utils._context._scenarios import scenarios
from utils.tools import logger


def assert_http_stat(s):
    logger.debug(f"asserting on {s}")
    assert "weblog" == s["Service"]
    assert 1 == s["Hits"]
    assert 200 == s["HTTPStatusCode"]
    assert 1 == s["IsTraceRoot"]
    # todo: peer tags?


"""
Test scenarios we want:
    * Generate N spans that will be aggregated together
        - Must aggregate by:
            - HTTP status code
            - peer service tags (todo: can we just rely on the defaults?)
        - Must have `is_trace_root` on trace root
        - Must set peer tags
        - Must have span_kind
        
Config:
- apm_config.peer_tags_aggregation (we should see peer service tags and aggregation by them, note only works on client or producer kind)
- apm_config.compute_stats_by_span_kind (span_kind will be set and we will calc stats on these spans even when not "top level")

"""


class Test_Agent_Stats:
    """Test client-side stats are compatible with Agent implementation"""

    def setup_main(self):
        # this setup never actually runs!?
        # also seems like weblog `/spans?repeats=10` doesn't exist anymore (or maybe ever in go?)
        self.r = weblog.get("/")
        logger.debug(f"what is going on here {self.r}")
        assert self.r.status_code == 204
        assert False

    def test_agent_stats(self):
        # why doesn't this form a valid connection?
        for i in range(10):
            req = weblog.get("/")
            logger.debug(f"got resp {req}")
        stats_count = 0
        # Do we need to _wait_ for the stats to be flushed?
        for s in interfaces.agent.get_stats(resource="GET /"):
            stats_count += 1
            assert_http_stat(s)
        assert stats_count == 1
        assert False

#
# @scenarios.library_conf_client_stats # I want to enable client stats for these tests
# class Test_Client_Stats:
#     """Test client-side stats are compatible with Agent implementation"""
#
#     def setup_main(self):
#         self.r = weblog.get("/")
#
#     def test_client_stats(self):
#         stats_count = 0
#         for s in interfaces.agent.get_stats(resource="GET /"):
#             stats_count += 1
#             assert_http_stat(s)
#         assert stats_count == 1

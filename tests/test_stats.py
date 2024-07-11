from utils import interfaces, weblog
from utils._context._scenarios import scenarios
from utils.tools import logger

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

    def setup_agent_stats(self):
        for _ in range(5):
            self.r = weblog.get("/stats-unique")
        for _ in range(3):
            self.r = weblog.get("/stats-unique?code=204")

    # TODO: mark that this is only good for golang net-http & dotnet for now?
    # todo: why is python "on" by default?
    # TODO: why are hits and top-level hits separated in python? (and not go)
    def test_agent_stats(self):
        stats_count = 0
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            stats_count += 1
            logger.debug(f"asserting on {s}")
            if s["HTTPStatusCode"] == 200:
                assert 5 == s["Hits"]
                assert 5 == s["TopLevelHits"]
            elif s["HTTPStatusCode"] == 204:
                assert 3 == s["Hits"]
                assert 3 == s["TopLevelHits"]
            else:
                assert False  # We only expect these two status codes
            assert "weblog" == s["Service"]
            assert "web" == s["Type"]
            # assert 1 == s["IsTraceRoot"]     # This breaks with client stats as IsTraceRoot doesn't exist yet
            # assert "server" == s["SpanKind"] # This breaks with client stats as IsTraceRoot doesn't exist yet
        assert stats_count == 2

# # TODO: A new scenario with client stats enabled and we can verify the aggregation is the same

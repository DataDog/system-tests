from utils import interfaces, weblog, features, scenarios, missing_feature, context, bug
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


@features.client_side_stats_supported
class Test_Client_Stats:
    """Test client-side stats are compatible with Agent implementation"""

    def setup_client_stats(self):
        for _ in range(5):
            weblog.get("/stats-unique")
        for _ in range(3):
            weblog.get("/stats-unique?code=204")

    @bug(
        library="python", weblog_variant in ("django-poc", "python3.12"), reason="APMSP-1375",
    )
    def test_client_stats(self):
        stats_count = 0
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            stats_count += 1
            logger.debug(f"asserting on {s}")
            if s["HTTPStatusCode"] == 200:
                assert 5 == s["Hits"], "expect 5 hits at 200 status code"
                assert 5 == s["TopLevelHits"], "expect 5 top level hits at 200 status code"
            elif s["HTTPStatusCode"] == 204:
                assert 3 == s["Hits"], "expect 3 hits at 204 status code"
                assert 3 == s["TopLevelHits"], "expect 3 top level hits at 204 status code"
            else:
                assert False, "Unexpected status code " + str(s["HTTPStatusCode"])
            assert "weblog" == s["Service"], "expect weblog as service"
            assert "web" == s["Type"], "expect 'web' type"
        assert stats_count == 2, "expect 2 stats"

    @missing_feature(
        context.library in ("cpp", "dotnet", "golang", "java", "nodejs", "php", "python", "ruby"),
        reason="Tracers have not implemented this feature yet.",
    )
    def test_is_trace_root(self):
        """Test IsTraceRoot presence in stats.
        Note: Once all tracers have implmented it and the test xpasses for all of them, we can move these
        assertions to `test_client_stats` method."""
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            assert 1 == s["IsTraceRoot"]
            assert "server" == s["SpanKind"]

    @scenarios.everything_disabled
    def test_disable(self):
        requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(requests) == 0, "Stats should be disabled by default"

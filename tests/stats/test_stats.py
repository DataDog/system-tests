import pytest
from utils import interfaces, weblog, features, scenarios, missing_feature, context, bug, logger

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
@scenarios.trace_stats_computation
class Test_Client_Stats:
    """Test client-side stats are compatible with Agent implementation"""

    def setup_client_stats(self):
        for _ in range(5):
            weblog.get("/stats-unique")
        for _ in range(3):
            weblog.get("/stats-unique?code=204")

    @bug(context.weblog_variant in ("django-poc", "python3.12"), library="python", reason="APMSP-1375")
    def test_client_stats(self):
        stats_count = 0
        ok_hits = 0
        ok_top_hits = 0
        no_content_hits = 0
        no_content_top_hits = 0
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            stats_count += 1
            logger.debug(f"asserting on {s}")
            if s["HTTPStatusCode"] == 200:
                ok_hits += s["Hits"]
                ok_top_hits += s["TopLevelHits"]
            elif s["HTTPStatusCode"] == 204:
                no_content_hits += s["Hits"]
                no_content_top_hits += s["TopLevelHits"]
            else:
                pytest.fail("Unexpected status code " + str(s["HTTPStatusCode"]))
            assert s["Service"] == "weblog", "expect weblog as service"
            assert s["Type"] == "web", "expect 'web' type"
        assert (
            stats_count <= 4
        ), "expect <= 4 stats"  # Normally this is exactly 2 but in certain high load this can flake and result in additional payloads where hits are split across two payloads
        assert ok_hits == ok_top_hits == 5, "expect exactly 5 'OK' hits and top level hits across all payloads"
        assert (
            no_content_hits == no_content_top_hits == 3
        ), "expect exactly 5 'No Content' hits and top level hits across all payloads"

    @missing_feature(
        context.library in ("cpp", "dotnet", "golang", "java", "nodejs", "php", "python", "ruby"),
        reason="Tracers have not implemented this feature yet.",
    )
    def test_is_trace_root(self):
        """Test IsTraceRoot presence in stats.
        Note: Once all tracers have implmented it and the test xpasses for all of them, we can move these
        assertions to `test_client_stats` method.
        """
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            assert s["IsTraceRoot"] == 1
            assert s["SpanKind"] == "server"

    @scenarios.default
    def test_disable(self):
        requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(requests) == 0, "Stats should be disabled by default"

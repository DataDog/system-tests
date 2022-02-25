from utils import BaseTestCase, interfaces, missing_feature, flaky, rfc


@rfc("https://github.com/DataDog/dd-trace-py/pull/2915")
@missing_feature(library="php")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="nodejs")
class TestTraceStatsV06(BaseTestCase):
    def test_valid(self):
        """Test stats payloads are valid."""
        for i in range(10):
            self.weblog_get(f"/stats")
        interfaces.library.add_trace_stats_validation(num_traces=10)

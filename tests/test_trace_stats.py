from utils import context, BaseTestCase, interfaces, bug, missing_feature, flaky


class TestTraceStatsComputation(BaseTestCase):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def test_valid(self):
        """Test stats payloads are valid.
        """
        self.weblog_get(f"/stats/10")
        interfaces.library.add_trace_stats_validation()


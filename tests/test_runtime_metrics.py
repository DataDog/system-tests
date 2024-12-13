from utils import interfaces, scenarios, features


@features.not_reported  # TODO
@scenarios.runtime_metrics
class Test_RuntimeMetrics:
    def test_main(self):
        for data in interfaces.agent.get_data("/api/v2/series"):
            assert data["request"]["content"]["series"]["metrics"] == 1  # TODO

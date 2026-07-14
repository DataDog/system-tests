"""Test evaluation metrics when UFC is loaded through the default agentless source."""

from tests.ffe.test_flag_eval_metrics import get_tag_value
from tests.ffe.utils.evaluation import evaluate_flag
from tests.ffe.utils.fixtures import JSON
from tests.ffe.utils.telemetry import assert_expected_telemetry_route, telemetry_interface, wait_for_telemetry
from utils import features, scenarios
from utils.interfaces._feature_flag_telemetry import metric_points_from_data


@scenarios.feature_flagging_and_experimentation_agentless_sidecar
@scenarios.feature_flagging_and_experimentation_agentless_direct_fallback
@features.feature_flags_eval_metrics
class Test_FFE_Agentless_Eval_Metric:
    flag_key = "empty-targeting-key-flag"

    def setup_agentless_eval_metric(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key="agentless-metric-user")

    def test_agentless_eval_metric(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        def find_metrics():
            return [
                point
                for _, point in telemetry_interface().get_metrics()
                if point.get("metric") == "feature_flag.evaluations"
                and f"feature_flag.key:{self.flag_key}" in point.get("tags", [])
            ]

        def matcher(data: JSON) -> bool:
            return any(
                point.get("metric") == "feature_flag.evaluations"
                and f"feature_flag.key:{self.flag_key}" in point.get("tags", [])
                for point in metric_points_from_data(data)
            )

        wait_for_telemetry(matcher, "feature_flag.evaluations metric")
        metrics = find_metrics()
        assert metrics, f"No feature_flag.evaluations metric found for {self.flag_key}"
        assert_expected_telemetry_route(matcher, "feature_flag.evaluations metric")

        tags = metrics[0].get("tags", [])
        assert get_tag_value(tags, "feature_flag.key") == self.flag_key
        assert get_tag_value(tags, "feature_flag.result.variant") == "on"
        assert get_tag_value(tags, "feature_flag.result.allocation_key") == "default-allocation"

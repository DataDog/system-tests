"""Test evaluation metrics when UFC is loaded through the default agentless source."""

from tests.ffe.test_flag_eval_metrics import find_eval_metrics, get_tag_value
from tests.ffe.utils.evaluation import evaluate_flag
from utils import features, scenarios


@scenarios.feature_flagging_and_experimentation_agentless
@features.feature_flags_eval_metrics
class Test_FFE_Agentless_Eval_Metric:
    flag_key = "empty-targeting-key-flag"

    def setup_agentless_eval_metric(self) -> None:
        self.response = evaluate_flag(self.flag_key, targeting_key="agentless-metric-user")

    def test_agentless_eval_metric(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert metrics, f"No feature_flag.evaluations metric found for {self.flag_key}"

        tags = metrics[0].get("tags", [])
        assert get_tag_value(tags, "feature_flag.key") == self.flag_key
        assert get_tag_value(tags, "feature_flag.result.variant") == "on"
        assert get_tag_value(tags, "feature_flag.result.allocation_key") == "default-allocation"

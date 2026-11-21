"""Read numeric HTTP status values without overriding legacy metadata."""

from utils import features, pytest, scenarios
from utils.dd_types import DataDogAgentTrace


@features.not_reported
@scenarios.test_the_test
class Test_AgentSpanTags:
    @pytest.mark.parametrize("status", [403, 403.0])
    def test_numeric_status(self, status: float) -> None:
        span = DataDogAgentTrace.from_agent_legacy(
            {}, {"spans": [{"meta": {}, "metrics": {"http.status_code": status}}]}
        ).spans[0]
        assert span.get_tag("http.status_code") == "403"

    def test_legacy_metadata_takes_precedence(self) -> None:
        span = DataDogAgentTrace.from_agent_legacy(
            {}, {"spans": [{"meta": {"http.status_code": 200}, "metrics": {"http.status_code": 403}}]}
        ).spans[0]
        assert span.get_tag("http.status_code") == 200

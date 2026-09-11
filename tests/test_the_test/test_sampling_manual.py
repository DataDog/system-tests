from tests.test_sampling_manual import _upstream_headers
from utils import scenarios
from utils.dd_constants import SamplingPriority


@scenarios.test_the_test
def test_manual_sampling_cases_use_distinct_upstream_contexts() -> None:
    keep_headers = _upstream_headers(SamplingPriority.AUTO_REJECT)
    drop_headers = _upstream_headers(SamplingPriority.USER_KEEP)

    for id_header in ("x-datadog-trace-id", "x-datadog-parent-id"):
        assert int(keep_headers[id_header]) > 0
        assert int(drop_headers[id_header]) > 0
        assert keep_headers[id_header] != drop_headers[id_header]

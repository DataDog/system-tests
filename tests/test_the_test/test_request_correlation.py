import pytest

from utils import features, scenarios
from utils.dd_types._utils import get_rid_from_span_data
from utils.interfaces._test_agent import _get_rid_from_span


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"system_tests.request.user_agent": "system_tests rid/" + "A" * 36}, "A" * 36),
        ({"system_tests.request.user_agent": "without a request id"}, None),
        ({}, None),
        (
            {
                "http.useragent": "system_tests rid/" + "B" * 36,
                "system_tests.request.user_agent": "system_tests rid/" + "A" * 36,
            },
            "B" * 36,
        ),
    ],
)
def test_test_only_request_correlation(meta: dict[str, str], expected: str | None) -> None:
    metrics = {"_dd.top_level": 1.0}
    assert get_rid_from_span_data("web", meta, metrics) == expected
    assert _get_rid_from_span({"type": "web", "meta": meta, "metrics": metrics}) == expected
    assert _get_rid_from_span({"type": "web", "attributes": {**meta, **metrics}}) == expected

"""Self-tests ensure the opt-out oracle rejects leaks and missing positive controls."""

from typing import Any
from tests.ffe.utils.evaluation_telemetry import assert_count, assert_evaluation_responses, evaluation_count
from utils import HttpResponse, features, pytest, scenarios


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize(
    ("status_code", "text", "count", "passes"),
    [
        (200, '{"value": "on-value"}', 3, True),
        (500, '{"value": "on-value"}', 3, False),
        (200, '{"value": "default"}', 3, False),
        (200, "not JSON", 3, False),
        (200, "{}", 3, False),
        (200, '{"value": "on-value"}', 0, False),
    ],
)
def test_evaluation_response_oracle(status_code: int, text: str, count: int, *, passes: bool) -> None:
    response = HttpResponse(
        {
            "request": {"method": "POST", "url": "http://weblog/ffe", "params": None},
            "status_code": status_code,
            "text": text,
            "cookies": {},
        }
    )
    responses = [response] * count
    if passes:
        assert_evaluation_responses(responses, expected_count=3, expected_value="on-value")
    else:
        with pytest.raises((AssertionError, ValueError, KeyError)):
            assert_evaluation_responses(responses, expected_count=3, expected_value="on-value")


@scenarios.feature_flagging_contract_tests
@features.not_reported
@pytest.mark.parametrize(
    ("suppressed_count", "allowed_count", "passes"),
    [(0, 3, True), (3, 3, False), (0, 0, False), (0, 6, False)],
)
def test_opt_out_evp_oracle(suppressed_count: int, allowed_count: int, *, passes: bool) -> None:
    events = [
        {"flag": {"key": flag}, "evaluation_count": count}
        for flag, count in [("suppressed", suppressed_count), ("allowed", allowed_count)]
        if count
    ]
    captures: list[dict[str, Any]] = [
        {"path": "/api/v2/flagevaluation", "request": {"content": {"flagEvaluations": events}}}
    ]

    def validate() -> None:
        assert_count(evaluation_count(captures, "suppressed"), 0, "suppressed")
        assert_count(evaluation_count(captures, "allowed"), 3, "allowed")

    if passes:
        validate()
    else:
        with pytest.raises(AssertionError, match="expected.*evaluations"):
            validate()

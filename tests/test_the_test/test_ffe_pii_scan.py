"""Deterministic coverage for the EVP flagevaluation raw-PII scan."""

import pytest

from tests.ffe.test_flag_eval_evp import PII_ATTRIBUTES, assert_no_raw_pii_in_event
from tests.ffe.utils.fixtures import JSON
from utils import scenarios


@scenarios.test_the_test
def test_numeric_pii_does_not_match_substring_of_numeric_timestamp() -> None:
    assert PII_ATTRIBUTES["org_id"] == 1234
    assert isinstance(PII_ATTRIBUTES["org_id"], int)

    assert_no_raw_pii_in_event({"timestamp": 1788901234711}, [PII_ATTRIBUTES["org_id"]])


@scenarios.test_the_test
@pytest.mark.parametrize(
    "field_name",
    ["timestamp", "first_evaluation", "last_evaluation", "evaluation_count"],
)
def test_numeric_pii_is_detected_in_generated_numeric_event_fields(field_name: str) -> None:
    with pytest.raises(AssertionError, match="raw PII value 1234"):
        assert_no_raw_pii_in_event({field_name: 1234}, [PII_ATTRIBUTES["org_id"]])


@scenarios.test_the_test
@pytest.mark.parametrize("value", ["1234", "sdk-prefix-1234-sdk-suffix"])
def test_numeric_pii_is_detected_after_string_conversion(value: str) -> None:
    with pytest.raises(AssertionError, match="raw PII value 1234"):
        assert_no_raw_pii_in_event({"unexpected": value}, [PII_ATTRIBUTES["org_id"]])


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("event", "forbidden_value"),
    [
        pytest.param({"jane.doe@datadoghq.com": "redacted"}, "jane.doe@datadoghq.com", id="dictionary-key"),
        pytest.param(
            {"unexpected": "prefix-jane.doe@datadoghq.com-suffix"},
            "jane.doe@datadoghq.com",
            id="string-value",
        ),
        pytest.param({"context": {"evaluation": {"plan": "enterprise"}}}, "enterprise", id="nested-dictionary"),
        pytest.param({"context": {"values": ["safe", {"region": "us-east-1"}]}}, "us-east-1", id="nested-list"),
    ],
)
def test_string_pii_is_detected_in_nested_and_unexpected_shapes(event: JSON, forbidden_value: str) -> None:
    with pytest.raises(AssertionError, match="raw PII value"):
        assert_no_raw_pii_in_event(event, [forbidden_value])

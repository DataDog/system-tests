"""Regression controls for canonical split-feature assertions and wire decoding."""

import base64
import gzip
import json
from typing import Any

from utils import pytest, scenarios
from tests.parametric.test_ffe.utils import assert_feature_map, ffe_events_from_requests


@scenarios.test_the_test
@pytest.mark.parametrize(
    "actual",
    [
        None,
        {},
        {"zero": 0},
        {"zero": False, "empty": "", "enabled": False},
        {"zero": 0, "empty": "", "enabled": 0},
        {"zero": "0", "empty": "", "enabled": False},
        {"zero": 0, "empty": "changed", "enabled": False},
        {"zero": 0, "empty": "", "enabled": False, "wrong-destination": True},
    ],
)
def test_feature_map_rejects_missing_changed_misrouted_or_coerced_values(actual: object) -> None:
    # Value/reason can remain correct while metadata is dropped or misrouted.
    with pytest.raises(AssertionError):
        assert_feature_map(actual, {"zero": 0, "empty": "", "enabled": False}, "EVALUATION")


@scenarios.test_the_test
def test_feature_map_preserves_json_number_equivalence_and_empty_maps() -> None:
    assert_feature_map(
        {"zero": 0.0, "number": 1.25, "false": False, "empty": ""},
        {"zero": 0, "number": 1.25, "false": False, "empty": ""},
        "HOOK",
    )
    assert_feature_map({}, {}, "EVALUATION")
    with pytest.raises(AssertionError):
        assert_feature_map({"leaked": True}, {}, "EVALUATION")
    with pytest.raises(AssertionError):
        assert_feature_map(None, {}, "EVALUATION")


@scenarios.test_the_test
@pytest.mark.parametrize("encoding", ["identity", "gzip", "decoded-gzip"])
def test_ffe_wire_events_keep_destination_boundaries_and_empty_features(encoding: str) -> None:
    def request(path: str, field: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({field: events}).encode()
        if encoding == "gzip":
            body = gzip.compress(body)
        return {
            "url": f"http://agent/evp_proxy/v4/api/v2/{path}",
            "headers": {"Content-Encoding": "gzip"} if encoding != "identity" else {},
            "body": base64.b64encode(body).decode(),
        }

    exposure = {"flag": {"key": "flag"}, "features": {"exposure.only": False}}
    evaluation = {"flag": {"key": "flag"}, "features": {"zero": 0}}
    empty_evaluation = {"flag": {"key": "flag"}}
    unrelated = {"flag": {"key": "other"}, "features": {"leaked": True}}
    actual = ffe_events_from_requests(
        [
            request("exposures", "exposures", [exposure, unrelated]),
            request("flagevaluation", "flagEvaluations", [evaluation, empty_evaluation, unrelated]),
            {"url": "/v0.7/config", "headers": {}, "body": "not-json"},
        ],
        "flag",
    )
    assert actual == {"EXPOSURE": [exposure], "EVALUATION": [evaluation, empty_evaluation]}
    assert ffe_events_from_requests([], "flag") == {"EXPOSURE": [], "EVALUATION": []}

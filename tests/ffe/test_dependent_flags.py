"""End-to-end coverage for rules-based dependent-flag evaluation."""

import json
import time

from tests.ffe.utils.canonical import JSON, canonical_event_matches, load_dependent_flag_fixtures
from tests.ffe.utils.evaluations import EVP_FLAGEVALUATIONS_PATH, evaluation_events_from_data
from tests.ffe.utils.exposures import EXPOSURES_PATH, exposure_events_from_data
from utils import features, interfaces, remote_config as rc, scenarios, weblog


RC_PATH = "datadog/2/FFE_FLAGS"
CASES_UNDER_TEST = {
    "dependent-direct-root",
    "dependent-transitive-root",
    "dependent-atomic-error-root",
    "dependent-depth-three-root",
    "dependent-cycle-a",
}
PROVIDER_READY_TIMEOUT_SECONDS = 30


def _expected_event_matchers(expectations: JSON, event_type: str) -> list[JSON]:
    matchers = expectations.get(event_type, [])
    assert isinstance(matchers, list), f"expectations.{event_type} must be an array"
    expanded: list[JSON] = []
    for matcher in matchers:
        assert isinstance(matcher, dict), f"{event_type} matcher must be an object"
        flag_key = matcher.get("flag")
        assert isinstance(flag_key, str), f"{event_type} matcher requires a flag"
        count = matcher.get("_count", 1)
        assert isinstance(count, int), f"{event_type} matcher count must be an integer"
        assert count >= 1, f"{event_type} matcher count must be positive"
        expanded.extend([matcher] * count)
    return expanded


def _assert_result(actual: JSON, expected: JSON, flag_key: str) -> None:
    for field in ("value", "reason", "errorCode"):
        if field in expected:
            assert actual.get(field) == expected[field], (
                f"{flag_key} returned unexpected {field}: expected {expected[field]!r}, got {actual.get(field)!r}"
            )
        elif field == "errorCode":
            assert actual.get(field) is None, f"{flag_key} unexpectedly returned errorCode={actual.get(field)!r}"
    if expected.get("reason") == "ERROR":
        assert actual.get("variant") is None, f"{flag_key} error result unexpectedly retained a variant"


def _evaluate_when_provider_is_ready(payload: JSON):
    deadline = time.monotonic() + PROVIDER_READY_TIMEOUT_SECONDS
    while True:
        response = weblog.post("/ffe", json=payload)
        if response.status_code != 500:
            return response

        try:
            error = json.loads(response.text).get("error")
        except (AttributeError, json.JSONDecodeError):
            return response
        if not isinstance(error, str) or not error.startswith("Initialization timeout after "):
            return response
        if time.monotonic() >= deadline:
            return response
        time.sleep(0.1)


def _captured_events(targeting_key: str) -> tuple[list[JSON], list[JSON]]:
    exposures = [
        event
        for data in interfaces.agent.get_data(path_filters=EXPOSURES_PATH)
        for event in exposure_events_from_data(data, subject_id=targeting_key)
    ]
    evaluations = [
        event
        for data in interfaces.agent.get_data(path_filters=EVP_FLAGEVALUATIONS_PATH)
        for event in evaluation_events_from_data(data, targeting_key=targeting_key)
    ]
    return exposures, evaluations


def _assert_events(actual: list[JSON], expected: list[JSON], *, exact: bool, event_type: str) -> None:
    unmatched = actual.copy()
    for matcher in expected:
        matching_index = next(
            (index for index, event in enumerate(unmatched) if canonical_event_matches(event, matcher)), None
        )
        assert matching_index is not None, f"missing {event_type} matching {matcher}: received {actual}"
        unmatched.pop(matching_index)
    if exact:
        assert not unmatched, f"unexpected unmatched {event_type}: {unmatched}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_Dependent_Flags:
    """Exercise canonical dependent trees against one Node server SDK build."""

    def setup_dependent_flag_trees(self) -> None:
        ufc, all_cases = load_dependent_flag_fixtures()
        self.cases = [case for case in all_cases if case.get("flag") in CASES_UNDER_TEST]
        assert {case["flag"] for case in self.cases} == CASES_UNDER_TEST, "canonical dependent cases are incomplete"

        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/dependent-flags/config", ufc).apply()
        self.results: dict[str, JSON] = {}
        for case in self.cases:
            flag_key = case["flag"]
            response = _evaluate_when_provider_is_ready(
                {
                    "flag": flag_key,
                    "variationType": case["variationType"],
                    "defaultValue": case["defaultValue"],
                    "targetingKey": case["targetingKey"],
                    "attributes": case.get("attributes", {}),
                    "details": True,
                }
            )
            assert response.status_code == 200, f"{flag_key} evaluation failed: {response.text}"
            result = json.loads(response.text)
            assert isinstance(result, dict), f"{flag_key} response must be an object"
            self.results[flag_key] = result

    def test_dependent_flag_trees(self) -> None:
        for case in self.cases:
            flag_key = case["flag"]
            expected_result = case["result"]
            expectations = case.get("expectations", {})
            assert isinstance(expected_result, dict)
            assert isinstance(expectations, dict)
            _assert_result(self.results[flag_key], expected_result, flag_key)

            exposures, evaluations = _captured_events(case["targetingKey"])
            exact = expectations.get("noUnmatchedEvents") is True
            _assert_events(
                exposures,
                _expected_event_matchers(expectations, "exposures"),
                exact=exact,
                event_type="exposures",
            )
            _assert_events(
                evaluations,
                _expected_event_matchers(expectations, "evaluationEvents"),
                exact=exact,
                event_type="evaluation events",
            )

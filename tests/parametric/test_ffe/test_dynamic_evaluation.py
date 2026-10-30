"""Test FFE (Feature Flags & Experimentation) functionality via parametric tests."""

import base64
import gzip
import hashlib
import json
from utils import pytest
import time
from pathlib import Path
from typing import Any

from utils import (
    context,
    features,
    scenarios,
    slow,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import assert_feature_map, ffe_events_from_requests

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
FFE_READY_RETRY_ATTEMPTS = 10
FFE_READY_RETRY_INTERVAL_SECONDS = 0.2
FFE_EVENT_WAIT_ATTEMPTS = 300
FFE_EVENT_WAIT_INTERVAL_SECONDS = 0.1
EXPOSURES_PATH = "/api/v2/exposures"
EVALUATIONS_PATH = "/api/v2/flagevaluation"
FFE_EVENT_PATHS = (EXPOSURES_PATH, EVALUATIONS_PATH)
FFE_SYSTEM_TEST_DATA_DIR = Path(__file__).parent / "ffe-system-test-data"
FFE_EVALUATION_CASES_DIR = FFE_SYSTEM_TEST_DATA_DIR / "evaluation-cases"
DEPENDENT_FLAGS_DIR = FFE_SYSTEM_TEST_DATA_DIR / "evaluation-suites" / "dependent-flags"
DEPENDENT_FLAGS_CASES_DIR = DEPENDENT_FLAGS_DIR / "cases"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = FFE_SYSTEM_TEST_DATA_DIR / "ufc-config.json"

    with fixture_path.open() as f:
        return json.load(f)


def _get_test_case_files() -> list[str]:
    """Get all test case files from the fixtures directory."""
    case_files = sorted(path.name for path in FFE_EVALUATION_CASES_DIR.glob("*.json"))
    if not case_files:
        raise FileNotFoundError(f"No canonical evaluation cases found in {FFE_EVALUATION_CASES_DIR}")
    return case_files


def _filter_test_cases_for_platform(test_cases: list[dict[str, Any]], platform: str) -> list[dict[str, Any]]:
    """Apply the canonical corpus _skip/_include selection rules."""
    applicable_cases = []
    for test_case in test_cases:
        if "_skip" in test_case and "_include" in test_case:
            raise ValueError("Evaluation cases cannot define both _skip and _include")
        skipped_platforms = {entry["platform"] for entry in test_case.get("_skip", [])}
        included_platforms = {entry["platform"] for entry in test_case.get("_include", [])}
        if platform in skipped_platforms:
            continue
        if included_platforms and platform not in included_platforms:
            continue
        applicable_cases.append(test_case)
    return applicable_cases


def _get_dependent_flags_test_case_files() -> list[Path]:
    """Get the test case files owned by the dependent-flags suite."""
    return sorted(DEPENDENT_FLAGS_CASES_DIR.glob("*.json"))


# Load fixture at module level for reuse across tests
UFC_FIXTURE_DATA = _load_ufc_fixture()
ALL_TEST_CASE_FILES = _get_test_case_files()
SPLIT_FEATURE_CASES = [
    case
    for filename in ALL_TEST_CASE_FILES
    for case in json.loads((FFE_EVALUATION_CASES_DIR / filename).read_text())
    if "features" in case["result"]
]
DEPENDENT_FLAGS_UFC_DATA = json.loads((DEPENDENT_FLAGS_DIR / "ufc-config.json").read_text())
DEPENDENT_FLAGS_TEST_CASE_FILES = _get_dependent_flags_test_case_files()

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _set_and_wait_ffe_rc(
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
) -> dict[str, Any]:
    """Set FFE Remote Config and wait for it to be acknowledged.

    Args:
        test_agent: The test agent API instance
        ufc_data: The UFC (User Feature Configuration) data payload
        config_id: Optional config ID, will be generated from data hash if not provided

    Returns:
        The apply state response from the test agent

    """
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    # Create RC config payload
    rc_config = ufc_data

    # Set the config
    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=rc_config)

    # Allow extra RC polling cycles under CI load, and match this update's ACK.
    return test_agent.wait_for_rc_apply_state(
        RC_PRODUCT,
        state=RemoteConfigApplyState.ACKNOWLEDGED,
        config_id=config_id,
        wait_loops=500,
        clear=True,
    )


def _is_ffe_waiting_for_rc(result: dict[str, Any]) -> bool:
    provider_state = result.get("providerState")
    return result.get("errorCode") == "PROVIDER_NOT_READY" or (
        isinstance(provider_state, dict) and provider_state.get("hasConfig") is False
    )


def _ffe_evaluate_with_rc_retry(
    test_library: APMLibrary,
    *,
    flag: str,
    variation_type: str,
    default_value: bool | str | float | dict[str, Any],
    targeting_key: str | None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = test_library.ffe_evaluate(
        flag=flag,
        variation_type=variation_type,
        default_value=default_value,
        targeting_key=targeting_key,
        attributes=attributes,
    )
    for _ in range(FFE_READY_RETRY_ATTEMPTS - 1):
        if not _is_ffe_waiting_for_rc(result):
            return result
        time.sleep(FFE_READY_RETRY_INTERVAL_SECONDS)
        result = test_library.ffe_evaluate(
            flag=flag,
            variation_type=variation_type,
            default_value=default_value,
            targeting_key=targeting_key,
            attributes=attributes,
        )

    return result


def _assert_evaluation_cases(
    test_case_file: Path,
    ufc_data: dict[str, Any],
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
) -> list[dict[str, Any]]:
    with test_case_file.open() as fixture_file:
        test_cases = json.load(fixture_file)
    assert isinstance(test_cases, list), f"Expected an evaluation-case array in {test_case_file.name}"
    assert test_cases, f"No evaluation cases in {test_case_file.name}"

    platform = context.library.name
    test_cases = _filter_test_cases_for_platform(test_cases, platform)
    if not test_cases:
        pytest.skip(f"No cases in {test_case_file.name} apply to platform {platform}")

    _set_and_wait_ffe_rc(test_agent, ufc_data)
    assert test_library.ffe_start(ufc_data), "Failed to start FFE provider"

    for index, test_case in enumerate(test_cases):
        expected_result = test_case["result"]
        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag=test_case["flag"],
            variation_type=test_case["variationType"],
            default_value=test_case["defaultValue"],
            targeting_key=test_case["targetingKey"],
            attributes=test_case.get("attributes", {}),
        )
        assert not _is_ffe_waiting_for_rc(result), (
            f"Test case {index} in {test_case_file.name} failed: FFE provider did not load RC data after "
            f"{FFE_READY_RETRY_ATTEMPTS} attempts; result={result}"
        )
        for field in ("value", "reason", "errorCode"):
            if field not in expected_result:
                continue
            assert result.get(field) == expected_result[field], (
                f"Test case {index} in {test_case_file.name} failed: "
                f"flag='{test_case['flag']}', targetingKey='{test_case['targetingKey']}', field='{field}', "
                f"expected={expected_result[field]!r}, actual={result.get(field)!r}"
            )
        if "errorCode" not in expected_result and expected_result.get("reason") != "ERROR":
            assert result.get("errorCode") in {None, ""}, (
                f"Test case {index} in {test_case_file.name} failed: "
                f"flag='{test_case['flag']}' unexpectedly returned errorCode={result.get('errorCode')!r}"
            )

    return test_cases


def _request_json(request: AgentRequest) -> dict[str, Any] | None:
    raw = base64.b64decode(request["body"])
    # The test agent may decompress a request while retaining its original headers.
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    try:
        content = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return content if isinstance(content, dict) else None


def _targeting_key_matches(actual: object, expected: str) -> bool:
    hashed = f"sha256_{hashlib.sha256(expected.encode()).hexdigest()}"
    return actual in (expected, hashed)


def _events_from_requests(requests: list[AgentRequest], path: str, targeting_key: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for request in requests:
        if not request["url"].endswith(path):
            continue
        content = _request_json(request)
        if content is None:
            continue
        event_key = "exposures" if path == EXPOSURES_PATH else "flagEvaluations"
        request_events = content.get(event_key)
        if not isinstance(request_events, list):
            continue
        for event in request_events:
            if not isinstance(event, dict):
                continue
            if path == EXPOSURES_PATH:
                subject = event.get("subject")
                actual_targeting_key = subject.get("id") if isinstance(subject, dict) else None
                if actual_targeting_key != targeting_key:
                    continue
            elif not _targeting_key_matches(event.get("targeting_key"), targeting_key):
                continue
            events.append(event)
    return events


def _event_matches(event: dict[str, Any], matcher: dict[str, Any]) -> bool:
    nested_key_fields = {
        "allocation": "allocation",
        "errorCode": "error",
        "flag": "flag",
        "variant": "variant",
    }

    def event_field(field: str) -> object:
        if field in nested_key_fields:
            value = event.get(nested_key_fields[field])
            if not isinstance(value, dict):
                return None
            return value.get("message" if field == "errorCode" else "key")
        if field == "runtimeDefaultUsed":
            return event.get("runtime_default_used", False)
        return event.get(field)

    fields_match = all(
        event_field(field) == expected for field, expected in matcher.items() if not field.startswith("_")
    )
    expected_error_code = matcher.get("errorCode")
    return fields_match and (expected_error_code is None or event.get("runtime_default_used") is True)


def _expected_event_matchers(expectations: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    matchers = expectations.get(event_type, [])
    assert isinstance(matchers, list), f"expectations.{event_type} must be an array"
    expanded: list[dict[str, Any]] = []
    for matcher in matchers:
        assert isinstance(matcher, dict), f"{event_type} matcher must be an object"
        count = matcher.get("_count", 1)
        assert isinstance(count, int), f"{event_type} matcher count must be an integer"
        assert count >= 1, f"{event_type} matcher count must be positive"
        expanded.extend([matcher] * count)
    return expanded


def _events_match(actual: list[dict[str, Any]], expected: list[dict[str, Any]], *, exact: bool) -> bool:
    unmatched = actual.copy()
    for matcher in expected:
        matching_index = next((index for index, event in enumerate(unmatched) if _event_matches(event, matcher)), None)
        if matching_index is None:
            return False
        unmatched.pop(matching_index)
    return not exact or not unmatched


def _assert_evaluation_telemetry(
    test_agent: TestAgentAPI, test_library: APMLibrary, test_cases: list[dict[str, Any]]
) -> None:
    marker_case = next(
        test_case for test_case in test_cases if _expected_event_matchers(test_case["expectations"], "exposures")
    )
    marker_targeting_key = f"{marker_case['targetingKey']}-telemetry-drain-marker"
    marker_result = _ffe_evaluate_with_rc_retry(
        test_library,
        flag=marker_case["flag"],
        variation_type=marker_case["variationType"],
        default_value=marker_case["defaultValue"],
        targeting_key=marker_targeting_key,
        attributes=marker_case.get("attributes", {}),
    )
    assert marker_result.get("reason") != "ERROR", f"telemetry drain marker evaluation failed: {marker_result}"

    captured: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}

    for _ in range(FFE_EVENT_WAIT_ATTEMPTS):
        requests = test_agent.requests()
        relevant_requests = [request for request in requests if request["url"].endswith(FFE_EVENT_PATHS)]
        captured = {
            test_case["targetingKey"]: (
                _events_from_requests(relevant_requests, EXPOSURES_PATH, test_case["targetingKey"]),
                _events_from_requests(relevant_requests, EVALUATIONS_PATH, test_case["targetingKey"]),
            )
            for test_case in test_cases
        }

        # Each writer preserves event order. Seeing the post-batch marker from both writers
        # proves that all telemetry from the evaluation cases has drained before exact checks.
        drained_paths = {
            path for path in FFE_EVENT_PATHS if _events_from_requests(relevant_requests, path, marker_targeting_key)
        }
        complete = drained_paths == set(FFE_EVENT_PATHS)
        for test_case in test_cases:
            expectations = test_case["expectations"]
            assert isinstance(expectations, dict)
            exposures, evaluations = captured[test_case["targetingKey"]]
            exact = expectations.get("noUnmatchedEvents") is True
            complete = complete and _events_match(
                exposures, _expected_event_matchers(expectations, "exposures"), exact=exact
            )
            complete = complete and _events_match(
                evaluations, _expected_event_matchers(expectations, "evaluationEvents"), exact=exact
            )

        if complete:
            break
        time.sleep(FFE_EVENT_WAIT_INTERVAL_SECONDS)
    else:
        raise AssertionError(f"evaluation telemetry did not stabilize: {captured}")

    for test_case in test_cases:
        expectations = test_case["expectations"]
        exposures, evaluations = captured[test_case["targetingKey"]]
        exact = expectations.get("noUnmatchedEvents") is True
        assert _events_match(exposures, _expected_event_matchers(expectations, "exposures"), exact=exact), (
            f"unexpected exposures for {test_case['flag']}: {exposures}"
        )
        assert _events_match(evaluations, _expected_event_matchers(expectations, "evaluationEvents"), exact=exact), (
            f"unexpected evaluation events for {test_case['flag']}: {evaluations}"
        )


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Dynamic_Evaluation:
    """Test Feature Flagging dynamic evaluation functionality.

    This test suite focuses on flag evaluation logic.

    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test to verify FFE can receive and acknowledge UFC configurations via Remote Config."""

        assert test_library.is_alive(), "library container is not alive"
        apply_state = _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ALL_TEST_CASE_FILES)
    def test_ffe_flag_evaluation(self, test_case_file: str, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        test_case_path = FFE_EVALUATION_CASES_DIR / test_case_file
        _assert_evaluation_cases(test_case_path, UFC_FIXTURE_DATA, test_agent, test_library)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("agent_env", [{"SYSTEM_TESTS_FFE_INTAKE": "true"}])
    @parametrize("test_case_file", DEPENDENT_FLAGS_TEST_CASE_FILES)
    def test_ffe_dependent_flags(
        self,
        test_case_file: Path,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        """Run dependent-flag results and telemetry from the imported canonical feature suite."""
        test_cases = _assert_evaluation_cases(test_case_file, DEPENDENT_FLAGS_UFC_DATA, test_agent, test_library)
        telemetry_cases = [test_case for test_case in test_cases if "expectations" in test_case]
        if telemetry_cases:
            _assert_evaluation_telemetry(test_agent, test_library, telemetry_cases)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
@slow
class Test_Feature_Flag_Split_Features:
    """Check canonical destination maps at the public hook and EVP boundaries."""

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "SYSTEM_TESTS_FFE_CAPTURE_HOOK_FEATURES": "true",
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_SPAN_ENRICHMENT_ENABLED": "true",
                "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "true",
                "DD_FLAGGING_EVALUATION_COUNTS_ENABLED": "true",
            }
        ],
    )
    @parametrize("agent_env", [{"SYSTEM_TESTS_FFE_INTAKE": "true"}])
    @parametrize("case", SPLIT_FEATURE_CASES)
    def test_split_feature_destinations(
        self, case: dict[str, Any], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        if not _filter_test_cases_for_platform([case], context.library.name):
            pytest.skip(f"Case does not apply to {context.library.name}")
        expected = case["result"]
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)
        assert test_library.ffe_start(UFC_FIXTURE_DATA), "Failed to start FFE provider"
        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag=case["flag"],
            variation_type=case["variationType"],
            default_value=case["defaultValue"],
            targeting_key=case["targetingKey"],
            attributes=case.get("attributes", {}),
        )
        assert result.get("value") == expected["value"], result
        assert result.get("reason") == expected["reason"], result
        assert result.get("errorCode") in (None, ""), result
        assert_feature_map(result.get("hookFeatures"), expected["features"]["HOOK"], "HOOK callback")

        # Selected metadata remains available even when doLog=false suppresses delivery.
        # Also check the actual payloads below: metadata alone cannot prove isolation.
        metadata = result.get("flagMetadata")
        assert isinstance(metadata, dict), result
        for destination, prefix in (
            ("EXPOSURE", "__dd_exposure_feature."),
            ("EVALUATION", "__dd_evaluation_feature."),
        ):
            selected = {key.removeprefix(prefix): value for key, value in metadata.items() if key.startswith(prefix)}
            assert_feature_map(selected, expected["features"][destination], f"{destination} selected metadata")

        # Evaluation batches flush every 10s; continue briefly after a matching batch
        # to observe forbidden exposures for the doLog=false case as well.
        deadline = time.monotonic() + 30
        received_at = None
        while True:
            events = ffe_events_from_requests(test_agent.requests(), case["flag"])
            if events["EVALUATION"] and (events["EXPOSURE"] or not expected["doLog"]):
                if received_at is None:
                    received_at = time.monotonic()
                if time.monotonic() - received_at >= 2:
                    break
            assert time.monotonic() < deadline, f"Missing split-feature events for {case['flag']}: {events}"
            time.sleep(0.2)

        if not expected["doLog"]:
            assert not events["EXPOSURE"], f"doLog=false emitted exposures: {events['EXPOSURE']}"
        for destination, observed_events in events.items():
            for event in observed_events:
                # Empty features are omitted from the wire format, but the event itself
                # must exist. An absent event never stands in for an empty feature map.
                assert_feature_map(event.get("features", {}), expected["features"][destination], destination)

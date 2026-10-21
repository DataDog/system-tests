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
    features,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures._test_agent import AgentRequest
from tests.parametric.conftest import APMLibrary

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
FFE_SYSTEM_TEST_CASES_DIR = Path(__file__).parent / "system-test-cases"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = FFE_SYSTEM_TEST_DATA_DIR / "ufc-config.json"

    with fixture_path.open() as f:
        return json.load(f)


def _contains_flag_evaluation(value: object) -> bool:
    if isinstance(value, dict):
        return "flagEvaluation" in value or any(_contains_flag_evaluation(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_flag_evaluation(child) for child in value)
    return False


def _get_test_case_files(ufc: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    """Partition canonical cases by evaluator capability without naming fixture files."""
    case_paths = sorted(FFE_EVALUATION_CASES_DIR.glob("*.json"))
    if not case_paths:
        raise FileNotFoundError(f"No canonical evaluation cases found in {FFE_EVALUATION_CASES_DIR}")

    ordinary: list[Path] = []
    dependent: list[Path] = []
    flags = ufc["flags"]
    for case_path in case_paths:
        with case_path.open() as fixture_file:
            cases = json.load(fixture_file)
        destination = (
            dependent if any(_contains_flag_evaluation(flags.get(case["flag"], {})) for case in cases) else ordinary
        )
        destination.append(case_path)
    return ordinary, dependent


# Load fixture at module level for reuse across tests
UFC_FIXTURE_DATA = _load_ufc_fixture()
ORDINARY_TEST_CASE_FILES, DEPENDENT_TEST_CASE_FILES = _get_test_case_files(UFC_FIXTURE_DATA)
DEPENDENT_TEST_CASE_FILES.extend(sorted(FFE_SYSTEM_TEST_CASES_DIR.glob("*.json")))

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


def _request_json(request: AgentRequest) -> dict[str, Any] | None:
    raw = base64.b64decode(request["body"])
    headers = {key.lower(): value for key, value in request["headers"].items()}
    if headers.get("content-encoding", "").lower() == "gzip":
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
        key = "exposures" if path == EXPOSURES_PATH else "flagEvaluations"
        request_events = content.get(key)
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
            expectations = test_case.get("expectations", {})
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

    def _assert_evaluation_cases(
        self,
        test_case_file: Path,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> list[dict[str, Any]]:
        # Load the test case file
        with test_case_file.open() as f:
            test_cases = json.load(f)
        assert isinstance(test_cases, list), f"Expected an evaluation-case array in {test_case_file.name}"
        assert test_cases, f"No evaluation cases in {test_case_file.name}"

        # Set up UFC Remote Config and wait for it to be applied
        _set_and_wait_ffe_rc(test_agent, UFC_FIXTURE_DATA)

        # Initialize FFE provider
        success = test_library.ffe_start(UFC_FIXTURE_DATA)
        assert success, "Failed to start FFE provider"

        # Run each test case
        for i, test_case in enumerate(test_cases):
            flag = test_case["flag"]
            variation_type = test_case["variationType"]
            default_value = test_case["defaultValue"]
            targeting_key = test_case["targetingKey"]
            attributes = test_case.get("attributes", {})
            expected_result = test_case["result"]

            result = _ffe_evaluate_with_rc_retry(
                test_library,
                flag=flag,
                variation_type=variation_type,
                default_value=default_value,
                targeting_key=targeting_key,
                attributes=attributes,
            )
            assert not _is_ffe_waiting_for_rc(result), (
                f"Test case {i} in {test_case_file.name} failed: FFE provider did not load RC data after "
                f"{FFE_READY_RETRY_ATTEMPTS} attempts; result={result}"
            )
            for field in ("value", "reason", "errorCode"):
                if field not in expected_result:
                    continue
                assert result.get(field) == expected_result[field], (
                    f"Test case {i} in {test_case_file.name} failed: "
                    f"flag='{flag}', targetingKey='{targeting_key}', field='{field}', "
                    f"expected={expected_result[field]!r}, actual={result.get(field)!r}"
                )
            if "errorCode" not in expected_result and expected_result.get("reason") != "ERROR":
                assert result.get("errorCode") in {None, ""}, (
                    f"Test case {i} in {test_case_file.name}: unexpected evaluation error; result={result}"
                )
        return test_cases

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", ORDINARY_TEST_CASE_FILES)
    def test_ffe_flag_evaluation(
        self, test_case_file: Path, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test every expected result field present in each canonical fixture case."""
        self._assert_evaluation_cases(test_case_file, test_agent, test_library)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("test_case_file", DEPENDENT_TEST_CASE_FILES)
    def test_ffe_dependent_flag_evaluation(
        self, test_case_file: Path, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Run dependency cases and infer optional telemetry assertions from each case."""
        test_cases = self._assert_evaluation_cases(test_case_file, test_agent, test_library)
        telemetry_cases = [test_case for test_case in test_cases if "expectations" in test_case]
        if telemetry_cases:
            _assert_evaluation_telemetry(test_agent, test_library, telemetry_cases)

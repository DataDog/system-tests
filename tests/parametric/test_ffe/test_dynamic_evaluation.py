"""Test FFE (Feature Flags & Experimentation) functionality via parametric tests."""

# ruff: noqa: UP045 - Repository guidance requires explicit Optional annotations.

import json
from utils import pytest
import time
from pathlib import Path
from typing import Any, Optional

from utils import (
    context,
    features,
    scenarios,
    slow,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import (
    assert_feature_map,
    events_match,
    ffe_events_for_target,
    ffe_events_from_requests,
)

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
FFE_READY_RETRY_ATTEMPTS = 10
FFE_READY_RETRY_INTERVAL_SECONDS = 0.2
FFE_EVENT_WAIT_ATTEMPTS = 60
FFE_EVENT_WAIT_INTERVAL_SECONDS = 0.5
FFE_SYSTEM_TEST_DATA_DIR = Path(__file__).parent / "ffe-system-test-data"
FFE_EVALUATION_CASES_DIR = FFE_SYSTEM_TEST_DATA_DIR / "evaluation-cases"
DEPENDENT_FLAGS_DIR = FFE_SYSTEM_TEST_DATA_DIR / "evaluation-suites" / "dependent-flags"
DEPENDENT_FLAGS_CASES_DIR = DEPENDENT_FLAGS_DIR / "cases"
TELEMETRY_DRAIN_TARGETING_KEY = "system-tests-telemetry-drain"
TELEMETRY_READINESS_TARGETING_KEY = "system-tests-telemetry-readiness"

parametrize = pytest.mark.parametrize


# Load the UFC fixture file at module level
def _load_evaluation_suite(
    suite_directory: Path,
    cases_directory: Path,
    *,
    required: bool,
) -> tuple[Path, list[Path]]:
    """Discover one canonical rules-based evaluation suite without parsing its UFC."""
    case_files = sorted(cases_directory.glob("*.json"))
    if not case_files:
        if required:
            raise FileNotFoundError(f"No canonical evaluation cases found in {cases_directory}")
        return suite_directory / "ufc-config.json", []
    config_path = suite_directory / "ufc-config.json"
    if not config_path.is_file():
        raise FileNotFoundError(f"No canonical UFC configuration found at {config_path}")
    return config_path, case_files


def _filter_for_platform(items: list[dict[str, Any]], platform: str) -> list[dict[str, Any]]:
    """Apply the canonical corpus _skip/_include selection rules."""
    applicable_items = []
    for item in items:
        if "_skip" in item and "_include" in item:
            raise ValueError("Corpus entries cannot define both _skip and _include")
        skipped_platforms = {entry["platform"] for entry in item.get("_skip", [])}
        included_platforms = {entry["platform"] for entry in item.get("_include", [])}
        if platform in skipped_platforms:
            continue
        if included_platforms and platform not in included_platforms:
            continue
        applicable_items.append(item)
    return applicable_items


# Load fixture at module level for reuse across tests
UFC_FIXTURE_PATH, ALL_TEST_CASE_FILES = _load_evaluation_suite(
    FFE_SYSTEM_TEST_DATA_DIR,
    FFE_EVALUATION_CASES_DIR,
    required=True,
)
UFC_FIXTURE_DATA = json.loads(UFC_FIXTURE_PATH.read_text())
SPLIT_FEATURE_CASES = [
    case
    for case_file in ALL_TEST_CASE_FILES
    for case in json.loads(case_file.read_text())
    if "features" in case["result"]
]
DEPENDENT_FLAGS_UFC_PATH, DEPENDENT_FLAGS_TEST_CASE_FILES = _load_evaluation_suite(
    DEPENDENT_FLAGS_DIR,
    DEPENDENT_FLAGS_CASES_DIR,
    required=False,
)
DEPENDENT_FLAGS_CASE_PARAMETERS = [
    pytest.param(case_file, id=case_file.stem) for case_file in DEPENDENT_FLAGS_TEST_CASE_FILES
] or [pytest.param(None, id="missing-suite")]


def _case_file_has_telemetry_expectations(case_file: Path) -> bool:
    return any("expectations" in case for case in json.loads(case_file.read_text()))


CORE_CASE_PARAMETERS = [
    pytest.param(
        case_file,
        {"SYSTEM_TESTS_FFE_INTAKE": "true"} if _case_file_has_telemetry_expectations(case_file) else {},
        id=case_file.stem,
    )
    for case_file in ALL_TEST_CASE_FILES
]

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _set_and_wait_ffe_rc(
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: Optional[str] = None
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
    targeting_key: Optional[str],
    attributes: Optional[dict[str, Any]] = None,
    retry_if_waiting: bool = True,
) -> dict[str, Any]:
    result = test_library.ffe_evaluate(
        flag=flag,
        variation_type=variation_type,
        default_value=default_value,
        targeting_key=targeting_key,
        attributes=attributes,
    )
    retry_attempts = FFE_READY_RETRY_ATTEMPTS - 1 if retry_if_waiting else 0
    for _ in range(retry_attempts):
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
    ufc_path: Path,
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
) -> None:
    with test_case_file.open() as fixture_file:
        test_cases = json.load(fixture_file)
    assert isinstance(test_cases, list), f"Expected an evaluation-case array in {test_case_file.name}"
    assert test_cases, f"No evaluation cases in {test_case_file.name}"

    platform = context.library.name
    test_cases = _filter_for_platform(test_cases, platform)
    if not test_cases:
        pytest.skip(f"No cases in {test_case_file.name} apply to platform {platform}")

    ufc_data = json.loads(ufc_path.read_text())
    telemetry_cases = [test_case for test_case in test_cases if "expectations" in test_case]
    telemetry_drain_case = _find_telemetry_drain_case(ufc_data) if telemetry_cases else None

    _set_and_wait_ffe_rc(test_agent, ufc_data)
    assert test_library.ffe_start(ufc_data), "Failed to start FFE provider"
    if telemetry_cases:
        assert telemetry_drain_case is not None
        _prepare_telemetry_capture(test_agent, test_library, telemetry_drain_case)

    for index, test_case in enumerate(test_cases):
        expected_result = test_case["result"]
        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag=test_case["flag"],
            variation_type=test_case["variationType"],
            default_value=test_case["defaultValue"],
            targeting_key=test_case["targetingKey"],
            attributes=test_case.get("attributes", {}),
            retry_if_waiting=not telemetry_cases,
        )
        assert not _is_ffe_waiting_for_rc(result), (
            f"Test case {index} in {test_case_file.name} failed: FFE provider did not load RC data after "
            f"{FFE_READY_RETRY_ATTEMPTS} attempts; result={result}"
        )
        for field in ("value", "reason"):
            assert result.get(field) == expected_result[field], (
                f"Test case {index} in {test_case_file.name} failed: "
                f"flag='{test_case['flag']}', targetingKey='{test_case['targetingKey']}', field='{field}', "
                f"expected={expected_result[field]!r}, actual={result.get(field)!r}"
            )
        if "errorCode" in expected_result:
            assert result.get("errorCode") == expected_result["errorCode"], (
                f"Test case {index} in {test_case_file.name} failed: "
                f"flag='{test_case['flag']}', targetingKey='{test_case['targetingKey']}', field='errorCode', "
                f"expected={expected_result['errorCode']!r}, actual={result.get('errorCode')!r}"
            )
        elif expected_result["reason"] != "ERROR":
            assert result.get("errorCode") in {None, ""}, (
                f"Test case {index} in {test_case_file.name} failed: "
                f"flag='{test_case['flag']}' unexpectedly returned errorCode={result.get('errorCode')!r}"
            )

    if telemetry_cases:
        assert telemetry_drain_case is not None
        _assert_evaluation_telemetry(test_agent, test_library, test_cases, telemetry_drain_case)


def _find_telemetry_drain_case(ufc_data: dict[str, Any]) -> dict[str, Any]:
    """Find a corpus-owned static logging flag suitable for draining both writers."""
    flags = ufc_data.get("flags")
    assert isinstance(flags, dict), "UFC flags must be an object"
    defaults: dict[str, Any] = {
        "BOOLEAN": False,
        "INTEGER": 0,
        "JSON": {},
        "NUMERIC": 0.0,
        "STRING": "",
    }
    for flag_key, flag in flags.items():
        if not isinstance(flag, dict) or flag.get("key") != flag_key or flag.get("enabled") is not True:
            continue
        allocations = flag.get("allocations")
        if not isinstance(allocations, list) or len(allocations) != 1:
            continue
        allocation = allocations[0]
        if not isinstance(allocation, dict) or allocation.get("doLog") is not True:
            continue
        if allocation.get("rules", []) != []:
            continue
        splits = allocation.get("splits")
        if (
            not isinstance(splits, list)
            or len(splits) != 1
            or not isinstance(splits[0], dict)
            or splits[0].get("shards") != []
        ):
            continue
        variation_type = flag.get("variationType")
        variations = flag.get("variations")
        variation_key = splits[0].get("variationKey")
        if variation_type not in defaults or not isinstance(variations, dict):
            continue
        variation = variations.get(variation_key)
        if not isinstance(variation, dict) or variation.get("key") != variation_key or "value" not in variation:
            continue
        value = variation["value"]
        if variation_type == "BOOLEAN":
            valid_value = type(value) is bool
        elif variation_type == "INTEGER":
            valid_value = type(value) is int
        elif variation_type == "NUMERIC":
            valid_value = type(value) in (int, float)
        elif variation_type == "STRING":
            valid_value = isinstance(value, str)
        else:
            valid_value = isinstance(value, dict)
        if not valid_value:
            continue
        return {
            "flag": flag_key,
            "variationType": variation_type,
            "defaultValue": defaults[variation_type],
            "value": value,
        }
    raise AssertionError("Telemetry expectations require a static doLog=true flag for the drain barrier")


def _expected_event_matchers(expectations: dict[str, Any], event_type: str, platform: str) -> list[dict[str, Any]]:
    matchers = expectations.get(event_type, [])
    assert isinstance(matchers, list), f"expectations.{event_type} must be an array"
    expanded: list[dict[str, Any]] = []
    for matcher in matchers:
        assert isinstance(matcher, dict), f"{event_type} matcher must be an object"
        if not _filter_for_platform([matcher], platform):
            continue
        count = matcher.get("_count", 1)
        assert isinstance(count, int), f"{event_type} matcher count must be an integer"
        assert count >= 1, f"{event_type} matcher count must be positive"
        expanded.extend([matcher] * count)
    return expanded


def _expected_events_for_cases(
    cases: list[dict[str, Any]], platform: str
) -> Optional[tuple[list[dict[str, Any]], list[dict[str, Any]], bool]]:
    expectation_cases = [case for case in cases if "expectations" in case]
    if not expectation_cases:
        return None
    exposures = [
        matcher
        for case in expectation_cases
        for matcher in _expected_event_matchers(case["expectations"], "exposures", platform)
    ]
    evaluations = [
        matcher
        for case in expectation_cases
        for matcher in _expected_event_matchers(case["expectations"], "evaluationEvents", platform)
    ]
    exact = len(expectation_cases) == len(cases) and all(
        case["expectations"].get("noUnmatchedEvents") is True for case in expectation_cases
    )
    return exposures, evaluations, exact


def _logical_evaluation_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand aggregated evaluation rows into the logical evaluations they represent."""
    expanded: list[dict[str, Any]] = []
    for event in events:
        count = event.get("evaluation_count", 1)
        assert type(count) is int, f"evaluation_count must be an integer: {count!r}"
        assert count >= 1, f"evaluation_count must be positive: {count!r}"
        expanded.extend([event] * count)
    return expanded


def _evaluate_telemetry_marker(
    test_library: APMLibrary,
    drain_case: dict[str, Any],
    targeting_key: str,
) -> dict[str, Any]:
    result = _ffe_evaluate_with_rc_retry(
        test_library,
        flag=drain_case["flag"],
        variation_type=drain_case["variationType"],
        default_value=drain_case["defaultValue"],
        targeting_key=targeting_key,
        attributes={},
    )
    assert result.get("value") == drain_case["value"], f"telemetry marker evaluation failed: {result}"
    assert result.get("reason") != "ERROR", f"telemetry marker evaluation failed: {result}"
    return result


def _prepare_telemetry_capture(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    drain_case: dict[str, Any],
) -> None:
    """Establish provider readiness, drain retry telemetry, then start with an empty capture."""
    _evaluate_telemetry_marker(test_library, drain_case, TELEMETRY_READINESS_TARGETING_KEY)
    for _ in range(FFE_EVENT_WAIT_ATTEMPTS):
        events = ffe_events_for_target(
            ffe_events_from_requests(test_agent.requests()), TELEMETRY_READINESS_TARGETING_KEY
        )
        if all(events.values()):
            test_agent.clear()
            return
        time.sleep(FFE_EVENT_WAIT_INTERVAL_SECONDS)
    raise AssertionError(f"telemetry readiness marker did not drain: {events}")


def _assert_evaluation_telemetry(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    test_cases: list[dict[str, Any]],
    drain_case: dict[str, Any],
) -> None:
    platform = context.library.name
    reserved_targeting_keys = {TELEMETRY_DRAIN_TARGETING_KEY, TELEMETRY_READINESS_TARGETING_KEY}
    assert all(test_case["targetingKey"] not in reserved_targeting_keys for test_case in test_cases), (
        f"Evaluation cases may not use reserved targeting keys {sorted(reserved_targeting_keys)}"
    )
    telemetry_targeting_keys = [test_case["targetingKey"] for test_case in test_cases if "expectations" in test_case]
    assert all(
        sum(case["targetingKey"] == targeting_key for case in test_cases) == 1
        for targeting_key in telemetry_targeting_keys
    ), "Telemetry expectations require a targeting key unique within the case file"
    _evaluate_telemetry_marker(test_library, drain_case, TELEMETRY_DRAIN_TARGETING_KEY)

    grouped_cases: dict[Optional[str], list[dict[str, Any]]] = {}
    for test_case in test_cases:
        grouped_cases.setdefault(test_case["targetingKey"], []).append(test_case)
    captured: dict[Optional[str], dict[str, list[dict[str, Any]]]] = {}

    for _ in range(FFE_EVENT_WAIT_ATTEMPTS):
        requests = test_agent.requests()
        all_events = ffe_events_from_requests(requests)
        captured = {targeting_key: ffe_events_for_target(all_events, targeting_key) for targeting_key in grouped_cases}

        # Each writer preserves event order. Seeing the post-batch marker from both writers
        # proves that all telemetry from the evaluation cases has drained before exact checks.
        marker_events = ffe_events_for_target(all_events, TELEMETRY_DRAIN_TARGETING_KEY)
        complete = all(marker_events.values())
        for targeting_key, cases in grouped_cases.items():
            expected = _expected_events_for_cases(cases, platform)
            if expected is None:
                continue
            expected_exposures, expected_evaluations, exact = expected
            complete = complete and events_match(captured[targeting_key]["EXPOSURE"], expected_exposures, exact=exact)
            complete = complete and events_match(
                _logical_evaluation_events(captured[targeting_key]["EVALUATION"]),
                expected_evaluations,
                exact=exact,
            )

        if complete:
            break
        time.sleep(FFE_EVENT_WAIT_INTERVAL_SECONDS)
    else:
        raise AssertionError(f"evaluation telemetry did not stabilize: marker={marker_events}, captured={captured}")

    for targeting_key, cases in grouped_cases.items():
        expected = _expected_events_for_cases(cases, platform)
        if expected is None:
            continue
        expected_exposures, expected_evaluations, exact = expected
        events = captured[targeting_key]
        assert events_match(events["EXPOSURE"], expected_exposures, exact=exact), (
            f"unexpected exposures for targeting key {targeting_key!r}: {events['EXPOSURE']}"
        )
        assert events_match(_logical_evaluation_events(events["EVALUATION"]), expected_evaluations, exact=exact), (
            f"unexpected evaluation events for targeting key {targeting_key!r}: {events['EVALUATION']}"
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
    @parametrize("test_case_file,agent_env", CORE_CASE_PARAMETERS)
    def test_ffe_flag_evaluation(
        self,
        test_case_file: Path,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        _assert_evaluation_cases(test_case_file, UFC_FIXTURE_PATH, test_agent, test_library)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @parametrize("agent_env", [{"SYSTEM_TESTS_FFE_INTAKE": "true"}])
    @parametrize("test_case_file", DEPENDENT_FLAGS_CASE_PARAMETERS)
    def test_ffe_dependent_flags(
        self,
        test_case_file: Optional[Path],
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        """Run the imported dependent-flags feature suite through the shared evaluator harness."""
        if test_case_file is None:
            raise FileNotFoundError(f"No canonical evaluation cases found in {DEPENDENT_FLAGS_CASES_DIR}")
        _assert_evaluation_cases(test_case_file, DEPENDENT_FLAGS_UFC_PATH, test_agent, test_library)


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
        if not _filter_for_platform([case], context.library.name):
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

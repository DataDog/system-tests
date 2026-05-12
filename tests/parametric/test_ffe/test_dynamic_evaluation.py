"""Test FFE (Feature Flags & Experimentation) functionality via parametric tests."""

import json
import pytest
from pathlib import Path
from typing import Any

from utils import (
    context,
    features,
    scenarios,
)
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
FFE_SYSTEM_TEST_DATA_DIR = Path(__file__).parent / "ffe-system-test-data"
FFE_EVALUATION_CASES_DIR = FFE_SYSTEM_TEST_DATA_DIR / "evaluation-cases"
MISSING_FFE_FIXTURES_CASE = "__missing_ffe_fixtures__"
KNOWN_FIXTURE_GAPS = {
    "test-case-null-targeting-key.json": {
        "python": "dd-trace-py main does not yet support explicit null targeting keys",
        "ruby": "dd-trace-rb main does not yet support explicit null targeting keys",
    },
}

parametrize = pytest.mark.parametrize


def _load_ufc_fixture() -> dict[str, Any]:
    """Load the UFC fixture file."""
    fixture_path = FFE_SYSTEM_TEST_DATA_DIR / "ufc-config.json"

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Fixture file not found: {fixture_path}. Run `git submodule update --init --recursive`."
        )

    with fixture_path.open() as f:
        return json.load(f)


def _get_test_case_files() -> list[str]:
    """Get all test case files from the fixtures directory."""
    if not FFE_EVALUATION_CASES_DIR.exists():
        raise FileNotFoundError(
            f"Fixture directory not found: {FFE_EVALUATION_CASES_DIR}. Run `git submodule update --init --recursive`."
        )

    test_case_files = sorted(f.name for f in FFE_EVALUATION_CASES_DIR.iterdir() if f.suffix == ".json")
    if not test_case_files:
        raise AssertionError(f"No FFE JSON fixtures found in {FFE_EVALUATION_CASES_DIR}")

    return test_case_files


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize FFE cases during pytest collection, not module import."""
    if "test_case_file" in metafunc.fixturenames:
        try:
            test_case_files = _get_test_case_files()
        except (FileNotFoundError, AssertionError):
            test_case_files = [MISSING_FFE_FIXTURES_CASE]

        metafunc.parametrize("test_case_file", test_case_files)


@pytest.fixture
def ufc_fixture_data() -> dict[str, Any]:
    return _load_ufc_fixture()


def _xfail_known_fixture_gap(test_case_file: str) -> None:
    reason = KNOWN_FIXTURE_GAPS.get(test_case_file, {}).get(context.library.name)
    if reason:
        pytest.xfail(reason)


DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
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

    # Wait for RC acknowledgment
    return test_agent.wait_for_rc_apply_state(RC_PRODUCT, state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Dynamic_Evaluation:
    """Test Feature Flagging dynamic evaluation functionality.

    This test suite focuses on flag evaluation logic.

    """

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_remote_config(
        self, ufc_fixture_data: dict[str, Any], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test to verify FFE can receive and acknowledge UFC configurations via Remote Config."""

        assert test_library.is_alive(), "library container is not alive"
        apply_state = _set_and_wait_ffe_rc(test_agent, ufc_fixture_data)
        assert apply_state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert apply_state["product"] == RC_PRODUCT

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_flag_evaluation(
        self, test_case_file: str, ufc_fixture_data: dict[str, Any], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """Test FFE flag evaluation logic with various targeting scenarios.

        This is the core FFE test that validates the OpenFeature provider correctly:
        1. Loads flag configurations from Remote Config (UFC format)
        2. Evaluates flags based on targeting rules and evaluation context
        3. Returns correct variation values for different variation types
        4. Handles user targeting, attribute matching, and rollout percentages

        """
        if test_case_file == MISSING_FFE_FIXTURES_CASE:
            pytest.fail(
                f"No FFE JSON fixtures found in {FFE_EVALUATION_CASES_DIR}. "
                "Run `git submodule update --init --recursive`."
            )

        _xfail_known_fixture_gap(test_case_file)

        # Skip OF.7 (empty targeting key) test for libraries with known bugs
        # Java: FFL-1729 - OpenFeature Java SDK rejects empty targeting keys
        # Node.js: FFL-1730 - OpenFeature JS SDK rejects empty targeting keys
        if test_case_file == "test-case-of-7-empty-targeting-key.json":
            if context.library.name in ("java", "nodejs"):
                pytest.skip("OF.7 empty targeting key bug: FFL-1729 (java), FFL-1730 (nodejs)")

        # Load the test case file
        test_case_path = FFE_EVALUATION_CASES_DIR / test_case_file

        if not test_case_path.exists():
            pytest.skip(f"Test case file not found: {test_case_path}")

        with test_case_path.open() as f:
            test_cases = json.load(f)

        # Set up UFC Remote Config and wait for it to be applied
        _set_and_wait_ffe_rc(test_agent, ufc_fixture_data)

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Run each test case
        for i, test_case in enumerate(test_cases):
            flag = test_case["flag"]
            variation_type = test_case["variationType"]
            default_value = test_case["defaultValue"]
            targeting_key = test_case["targetingKey"]
            attributes = test_case.get("attributes", {})
            expected_result = test_case["result"]["value"]

            result = test_library.ffe_evaluate(
                flag=flag,
                variation_type=variation_type,
                default_value=default_value,
                targeting_key=targeting_key,
                attributes=attributes,
            )
            actual_value = result.get("value")

            # Assert the evaluation result matches expected value
            assert actual_value == expected_result, (
                f"Test case {i} in {test_case_file} failed: "
                f"flag='{flag}', targetingKey='{targeting_key}', "
                f"expected={expected_result}, actual={actual_value}"
            )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_ffe_of7_empty_targeting_key(
        self, ufc_fixture_data: dict[str, Any], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """OF.7: Empty string is a valid targeting key.

        This test validates that flag evaluation succeeds when the targeting key
        is an empty string. The flag should still match allocations and return
        the expected value, not fail with TARGETING_KEY_MISSING.

        Temporary dedicated test until FFL-1729 (Java) and FFL-1730 (Node.js) are resolved.
        """
        # Set up UFC Remote Config and wait for it to be applied
        _set_and_wait_ffe_rc(test_agent, ufc_fixture_data)

        # Initialize FFE provider
        success = test_library.ffe_start()
        assert success, "Failed to start FFE provider"

        # Evaluate flag with empty targeting key
        result = test_library.ffe_evaluate(
            flag="empty-targeting-key-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="",
            attributes={},
        )

        assert result.get("value") == "on-value", (
            f"OF.7 failed: empty targeting key should return 'on-value', got '{result.get('value')}'"
        )

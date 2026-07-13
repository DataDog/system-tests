"""Shared UFC fixtures and evaluation assertions for FFE configuration sources."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.parametric.conftest import APMLibrary

FFE_READY_RETRY_ATTEMPTS = 10
FFE_READY_RETRY_INTERVAL_SECONDS = 0.2

FIXTURE_DIRECTORY = Path(__file__).parent
UFC_FIXTURE_PATH = FIXTURE_DIRECTORY / "flags-v1.json"
MALFORMED_UFC_BYTES = b'{"flags": ['


def load_ufc_fixture() -> dict[str, Any]:
    """Load the canonical UFC configuration shared by every delivery source."""
    if not UFC_FIXTURE_PATH.exists():
        pytest.skip(f"Fixture file not found: {UFC_FIXTURE_PATH}")

    with UFC_FIXTURE_PATH.open() as fixture:
        return json.load(fixture)


def get_test_case_files() -> list[str]:
    """Return the canonical UFC evaluation fixture files."""
    excluded = {UFC_FIXTURE_PATH.name, "span-enrichment-flags.json"}
    return sorted(
        fixture.name
        for fixture in FIXTURE_DIRECTORY.iterdir()
        if fixture.suffix == ".json" and fixture.name not in excluded
    )


UFC_FIXTURE_DATA = load_ufc_fixture()
UFC_FIXTURE_BYTES = UFC_FIXTURE_PATH.read_bytes()
ALL_TEST_CASE_FILES = get_test_case_files()


def is_ffe_waiting_for_configuration(result: dict[str, Any]) -> bool:
    """Return whether an evaluation is still waiting for its initial UFC payload."""
    provider_state = result.get("providerState")
    return result.get("errorCode") == "PROVIDER_NOT_READY" or (
        isinstance(provider_state, dict) and provider_state.get("hasConfig") is False
    )


def evaluate_with_configuration_retry(
    test_library: APMLibrary,
    *,
    flag: str,
    variation_type: str,
    default_value: bool | str | float | dict[str, Any],
    targeting_key: str,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate after allowing an asynchronous configuration source to become ready."""
    result = test_library.ffe_evaluate(
        flag=flag,
        variation_type=variation_type,
        default_value=default_value,
        targeting_key=targeting_key,
        attributes=attributes,
    )
    for _ in range(FFE_READY_RETRY_ATTEMPTS - 1):
        if not is_ffe_waiting_for_configuration(result):
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


def assert_evaluation_cases(test_library: APMLibrary, test_case_file: str) -> None:
    """Run one canonical evaluation fixture against an initialized provider."""
    test_case_path = FIXTURE_DIRECTORY / test_case_file
    if not test_case_path.exists():
        pytest.skip(f"Test case file not found: {test_case_path}")

    with test_case_path.open() as fixture:
        test_cases: list[dict[str, Any]] = json.load(fixture)

    for index, test_case in enumerate(test_cases):
        result = evaluate_with_configuration_retry(
            test_library,
            flag=test_case["flag"],
            variation_type=test_case["variationType"],
            default_value=test_case["defaultValue"],
            targeting_key=test_case["targetingKey"],
            attributes=test_case.get("attributes", {}),
        )
        assert not is_ffe_waiting_for_configuration(result), (
            f"Test case {index} in {test_case_file} failed: FFE provider did not load UFC data after "
            f"{FFE_READY_RETRY_ATTEMPTS} attempts; result={result}"
        )

        expected_value = test_case["result"]["value"]
        actual_value = result.get("value")
        assert actual_value == expected_value, (
            f"Test case {index} in {test_case_file} failed: "
            f"flag='{test_case['flag']}', targetingKey='{test_case['targetingKey']}', "
            f"expected={expected_value}, actual={actual_value}"
        )

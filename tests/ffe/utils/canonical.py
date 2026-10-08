"""Load canonical FFE evaluation fixtures without copying them into system-tests."""

import json
import os
from pathlib import Path
from typing import Any


JSON = dict[str, Any]
TEST_DATA_PATH_ENV = "SYSTEM_TESTS_FFE_TEST_DATA_PATH"
REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_TEST_DATA_PATH = REPOSITORY_ROOT / "binaries" / "ffe-system-test-data"
LOCAL_SIBLING_TEST_DATA_PATH = REPOSITORY_ROOT.parent / "ffe-system-test-data"


def ffe_test_data_path() -> Path:
    """Return the configured canonical fixture checkout."""
    configured_path = os.environ.get(TEST_DATA_PATH_ENV)
    if configured_path is not None:
        fixture_path = Path(configured_path).expanduser().resolve()
    elif DEFAULT_TEST_DATA_PATH.is_dir():
        fixture_path = DEFAULT_TEST_DATA_PATH
    else:
        fixture_path = LOCAL_SIBLING_TEST_DATA_PATH

    if not fixture_path.is_dir():
        raise AssertionError(
            f"FFE test data not found at {fixture_path}. Run "
            "utils/scripts/prepare-ffe-system-test-data.sh or set "
            f"{TEST_DATA_PATH_ENV}."
        )
    return fixture_path


def load_dependent_flag_fixtures() -> tuple[JSON, list[JSON]]:
    """Load the UFC and provisional dependent-flag evaluation cases."""
    fixture_path = ffe_test_data_path()
    ufc = json.loads((fixture_path / "ufc-config.json").read_text(encoding="utf-8"))
    cases = json.loads(
        (fixture_path / "evaluation-cases" / "test-case-dependent-flags.json").read_text(encoding="utf-8")
    )
    assert isinstance(ufc, dict), "canonical UFC fixture must be an object"
    assert isinstance(cases, list), "dependent-flag evaluation cases must be an array"
    assert all(isinstance(case, dict) for case in cases), "dependent-flag cases must be objects"
    return ufc, cases


def canonical_event_matches(event: JSON, matcher: JSON) -> bool:
    """Match a canonical event expectation against an emitted EVP event."""
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
            nested_field = "message" if field == "errorCode" else "key"
            return value.get(nested_field)
        if field == "runtimeDefaultUsed":
            return event.get("runtime_default_used", False)
        return event.get(field)

    fields_match = all(
        event_field(field) == expected for field, expected in matcher.items() if not field.startswith("_")
    )
    expected_error_code = matcher.get("errorCode")
    return fields_match and (expected_error_code is None or event.get("runtime_default_used") is True)

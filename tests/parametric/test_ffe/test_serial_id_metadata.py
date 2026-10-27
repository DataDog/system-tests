"""Test that UFC split serial IDs are threaded through OpenFeature flagMetadata.

Every evaluated (allocation, variant) pair has a stable per-org serial ID
(`Split.serialId` in the UFC wire format). Downstream consumers -- APM span
enrichment, exposure caching, evaluation-metrics correlation -- need that
serial ID without re-deriving it from (flag_key, allocation_key, variant_key).

The contract under test: when span enrichment is enabled, the SDK's OpenFeature
EvaluationDetails-equivalent object must expose the selected split's serial ID
via `flagMetadata` under the internal key `__dd_split_serial_id`, matching the
value present in the UFC config pushed over Remote Config. This is the field
`openfeature-js-client#269` introduced for the Node server SDK; this test
generalizes the contract to every parametric-tested SDK.

This module tests:
1. flagMetadata carries the exact serialId of the selected split.
2. Zero is a valid serial ID and must not be treated as "missing" (falsy-check trap).
3. Evaluation details always expose flagMetadata; for a split with no serialId, the map must not
   contain the serial ID key.
4. flagMetadata reflects whichever split targeting actually selected, not always the first one.
5. Repeated evaluations of the same context return the same serial ID.
6. Splits sharing a variant across allocations retain their own serial IDs.
7. Remote Config updates replace or remove serial IDs without restarting the provider.
"""

import copy
import json
import time
from pathlib import Path
from typing import Any

from utils import pytest

from utils import features, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI
from tests.parametric.conftest import APMLibrary

RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
FFE_READY_RETRY_ATTEMPTS = 10
FFE_READY_RETRY_INTERVAL_SECONDS = 0.2

SERIAL_ID_METADATA_KEY = "__dd_split_serial_id"

parametrize = pytest.mark.parametrize


def _load_serial_id_metadata_fixture() -> dict[str, Any]:
    """Load the UFC fixture file for serial ID metadata tests."""
    fixture_path = Path(__file__).parent / "serial-id-metadata-flags.json"

    if not fixture_path.exists():
        pytest.skip(f"Fixture file not found: {fixture_path}")

    with fixture_path.open() as f:
        return json.load(f)


UFC_SERIAL_ID_METADATA_DATA = _load_serial_id_metadata_fixture()

DEFAULT_ENVVARS = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_SPAN_ENRICHMENT_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _set_and_wait_ffe_rc(
    test_agent: TestAgentAPI, ufc_data: dict[str, Any], config_id: str | None = None
) -> dict[str, Any]:
    """Set FFE Remote Config and wait for it to be acknowledged."""
    if not config_id:
        config_id = str(hash(json.dumps(ufc_data, sort_keys=True)))

    test_agent.set_remote_config(path=f"{RC_PATH}/{config_id}/config", payload=ufc_data)
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


def _require_flag_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """Require evaluation details to expose flagMetadata, allowing a null map."""
    assert "flagMetadata" in result, f"FFE evaluation details did not emit flagMetadata; result={result}"

    flag_metadata = result["flagMetadata"]
    assert flag_metadata is None or isinstance(flag_metadata, dict), (
        f"Expected flagMetadata to be a map or null, got {flag_metadata!r}"
    )
    if flag_metadata and SERIAL_ID_METADATA_KEY in flag_metadata:
        serial_id = flag_metadata[SERIAL_ID_METADATA_KEY]
        assert type(serial_id) is int, f"Expected an integer serial ID, got {serial_id!r}"
    return flag_metadata or {}


def _ffe_evaluate_with_rc_retry(
    test_library: APMLibrary,
    *,
    flag: str,
    variation_type: str,
    default_value: bool | str | float | dict[str, Any],
    targeting_key: str,
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


@scenarios.parametric
@features.feature_flags_serial_id_metadata
class Test_FFE_Serial_Id_Metadata:
    """Test that the selected split's serial ID is threaded through flagMetadata."""

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_present_in_flag_metadata(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """The serial ID of the selected split must appear in flagMetadata."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-basic-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-1",
        )
        assert not _is_ffe_waiting_for_rc(result), f"FFE provider did not load RC data; result={result}"

        flag_metadata = _require_flag_metadata(result)
        assert flag_metadata.get(SERIAL_ID_METADATA_KEY) == 42, (
            f"Expected flagMetadata['{SERIAL_ID_METADATA_KEY}'] == 42 for the selected split, "
            f"got flagMetadata={flag_metadata}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_zero_is_not_treated_as_missing(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Serial ID 0 is a real, valid ID and must survive falsy-value checks."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-zero-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-1",
        )
        assert not _is_ffe_waiting_for_rc(result), f"FFE provider did not load RC data; result={result}"

        flag_metadata = _require_flag_metadata(result)
        assert SERIAL_ID_METADATA_KEY in flag_metadata, (
            f"flagMetadata is missing '{SERIAL_ID_METADATA_KEY}' entirely; a 0 serial ID must not be "
            f"dropped by a truthiness check. flagMetadata={flag_metadata}"
        )
        assert flag_metadata.get(SERIAL_ID_METADATA_KEY) == 0, (
            f"Expected flagMetadata['{SERIAL_ID_METADATA_KEY}'] == 0, got flagMetadata={flag_metadata}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_absent_when_split_has_no_serial_id(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """A split without a serialId must not have one fabricated for it."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-missing-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="user-1",
        )
        assert not _is_ffe_waiting_for_rc(result), f"FFE provider did not load RC data; result={result}"
        assert result.get("errorCode") in {None, ""}, f"FFE evaluation failed; result={result}"
        assert result.get("reason") != "ERROR", f"FFE evaluation failed; result={result}"
        assert result.get("value") == "control", f"Expected the configured control variation; result={result}"

        flag_metadata = _require_flag_metadata(result)
        assert SERIAL_ID_METADATA_KEY not in flag_metadata, (
            f"Expected flagMetadata to omit '{SERIAL_ID_METADATA_KEY}' for a split without a serial ID, "
            f"got flagMetadata={flag_metadata}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_matches_selected_split_under_targeting(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """FlagMetadata must reflect whichever split targeting actually selected."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        vip_result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-targeting-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="user-vip",
            attributes={"segment": "vip"},
        )
        standard_result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-targeting-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="user-standard",
            attributes={"segment": "standard"},
        )

        for label, result in (("vip", vip_result), ("standard", standard_result)):
            assert not _is_ffe_waiting_for_rc(result), f"FFE provider did not load RC data ({label}); result={result}"

        vip_metadata = _require_flag_metadata(vip_result)
        standard_metadata = _require_flag_metadata(standard_result)

        assert vip_result.get("value") == "vip"
        assert vip_metadata.get(SERIAL_ID_METADATA_KEY) == 201, (
            f"VIP targeting should select the split with serialId 201, got flagMetadata={vip_metadata}"
        )

        assert standard_result.get("value") == "standard"
        assert standard_metadata.get(SERIAL_ID_METADATA_KEY) == 200, (
            f"Non-VIP targeting should select the split with serialId 200, got flagMetadata={standard_metadata}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_stable_across_repeated_evaluations(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """The same context evaluated twice must yield the same serial ID."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        first = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-basic-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-repeat",
        )
        second = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-basic-flag",
            variation_type="BOOLEAN",
            default_value=False,
            targeting_key="user-repeat",
        )

        first_id = _require_flag_metadata(first).get(SERIAL_ID_METADATA_KEY)
        second_id = _require_flag_metadata(second).get(SERIAL_ID_METADATA_KEY)
        assert first_id == second_id == 42, (
            f"Expected stable serial ID 42 across repeated evaluations, got {first_id} then {second_id}"
        )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_matches_second_split(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """A zero-traffic first split must not supply the selected second split's ID."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        result = _ffe_evaluate_with_rc_retry(
            test_library,
            flag="serial-id-second-split-flag",
            variation_type="STRING",
            default_value="default",
            targeting_key="user-second-split",
        )
        assert result.get("errorCode") in {None, ""}, f"FFE evaluation failed; result={result}"
        assert result.get("value") == "treatment", f"Expected the second split; result={result}"
        assert _require_flag_metadata(result).get(SERIAL_ID_METADATA_KEY) == 302, result

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_distinguishes_allocations_with_same_variant(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """The same variant in different allocations must retain each allocation's serial ID."""
        _set_and_wait_ffe_rc(test_agent, UFC_SERIAL_ID_METADATA_DATA)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        for segment, expected_id in (("vip", 401), ("standard", 402), ("vip", 401)):
            result = _ffe_evaluate_with_rc_retry(
                test_library,
                flag="serial-id-shared-variant-flag",
                variation_type="STRING",
                default_value="default",
                targeting_key="user-shared-variant",
                attributes={"segment": segment},
            )
            assert result.get("errorCode") in {None, ""}, f"FFE evaluation failed; result={result}"
            assert result.get("value") == "shared", result
            assert _require_flag_metadata(result).get(SERIAL_ID_METADATA_KEY) == expected_id, result

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_serial_id_refreshes_after_remote_config_updates(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """The same provider and context must see ID changes and removal after RC updates."""
        ufc_data = copy.deepcopy(UFC_SERIAL_ID_METADATA_DATA)
        _set_and_wait_ffe_rc(test_agent, ufc_data)
        assert test_library.ffe_start(), "Failed to start FFE provider"

        for expected_id in (42, 43, None):
            if expected_id != 42:
                split = ufc_data["flags"]["serial-id-basic-flag"]["allocations"][0]["splits"][0]
                if expected_id is None:
                    del split["serialId"]
                else:
                    split["serialId"] = expected_id
                _set_and_wait_ffe_rc(test_agent, ufc_data)

            result = _ffe_evaluate_with_rc_retry(
                test_library,
                flag="serial-id-basic-flag",
                variation_type="BOOLEAN",
                default_value=False,
                targeting_key="user-config-update",
            )
            assert result.get("errorCode") in {None, ""}, f"FFE evaluation failed; result={result}"
            assert result.get("value") is True, f"Expected the configured variation after RC update; result={result}"
            metadata = _require_flag_metadata(result)
            if expected_id is None:
                assert SERIAL_ID_METADATA_KEY not in metadata, f"Stale serial ID survived removal; result={result}"
            else:
                assert metadata.get(SERIAL_ID_METADATA_KEY) == expected_id, result

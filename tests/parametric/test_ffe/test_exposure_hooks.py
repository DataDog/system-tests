"""Customer exposure decisions share the Datadog cache, including warehouse-only mode."""

import base64
import json
import time
from typing import Any

from tests.ffe.utils.fixtures import make_ufc_fixture
from tests.parametric.conftest import APMLibrary
from utils import features, pytest, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI

BASE_ENV = {
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
    "DD_FLAGGING_EVALUATION_COUNTS_ENABLED": "true",
}


def install(test_agent: TestAgentAPI, fixture: dict[str, Any], *, wait: bool = True) -> None:
    allocation = fixture["flags"]["hook-flag"]["allocations"][0]
    config_id = f"hook-{allocation['splits'][0]['serialId']}-{allocation['doLog']}"
    test_agent.set_remote_config(path=f"datadog/2/FFE_FLAGS/{config_id}/config", payload=fixture)
    if wait:
        test_agent.wait_for_rc_apply_state("FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id=config_id)


def evaluate(test_library: APMLibrary, subject: str, *, flag: str = "hook-flag") -> dict[str, Any]:
    return test_library.ffe_evaluate(
        flag=flag, variation_type="STRING", default_value="fallback", targeting_key=subject, exposure_hooks=True
    )


def observations(result: dict[str, Any], *, exposure: bool, hit: bool) -> None:
    assert result["errorCode"] == "", result
    rows = result.get("exposureHooks", [])
    assert len(rows) == 2, result
    assert {row["hook"] for row in rows} == {0, 1}
    for row in rows:
        assert row["isExposure"] is exposure
        assert row["isCacheHit"] is hit
        assert row["shouldSend"] is (exposure and not hit)
        assert row["flag"] == "hook-flag"


def events(test_agent: TestAgentAPI, path: str, field: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for request in test_agent.requests():
        if request["url"].endswith(path):
            payload = json.loads(base64.b64decode(request["body"]))
            result.extend(payload.get(field, []))
    return result


@scenarios.parametric
@features.feature_flags_exposures
class Test_FFE_ExposureHooks:
    @pytest.mark.parametrize(
        "library_env",
        [BASE_ENV, {**BASE_ENV, "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "false"}],
    )
    def test_shared_cache_and_destination_control(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        fixture = make_ufc_fixture("hook-flag", serial_id=0)
        install(test_agent, fixture, wait=False)
        assert test_library.ffe_start()
        first = evaluate(test_library, "athlete")
        observations(first, exposure=True, hit=False)
        assert first["value"] == "on-value"
        assert first["exposureHooks"][0]["metadata"]["__dd_split_serial_id"] == 0
        assert first["exposureHooks"][0]["subject"] == "athlete"
        observations(evaluate(test_library, "athlete"), exposure=True, hit=True)
        observations(evaluate(test_library, "another-athlete"), exposure=True, hit=False)

        # Same value and allocation, new serial ID: this is a new exposure.
        fixture["flags"]["hook-flag"]["allocations"][0]["splits"][0]["serialId"] = 42
        install(test_agent, fixture)
        observations(evaluate(test_library, "athlete"), exposure=True, hit=False)
        observations(evaluate(test_library, "athlete"), exposure=True, hit=True)

        fixture["flags"]["hook-flag"]["allocations"][0]["doLog"] = False
        install(test_agent, fixture)
        observations(evaluate(test_library, "athlete"), exposure=False, hit=False)
        failed = evaluate(test_library, "athlete", flag="missing")
        assert failed["errorCode"] == "FLAG_NOT_FOUND"
        assert not failed.get("exposureHooks")

        # Evaluation events are a positive control for egress when exposure logging is off.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            evaluations = events(test_agent, "/api/v2/flagevaluation", "flagEvaluations")
            if sum(event["evaluation_count"] for event in evaluations) >= 7:
                break
            time.sleep(0.2)
        assert sum(event["evaluation_count"] for event in evaluations) == 7, evaluations
        exposures = events(test_agent, "/api/v2/exposures", "exposures")
        if library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") == "false":
            assert exposures == []
        else:
            assert len(exposures) == 3, exposures
            assert sorted(event["serial_id"] for event in exposures) == [0, 0, 42]

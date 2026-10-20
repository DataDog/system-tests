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
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "cumulative",
}
RC_PATH = "datadog/2/FFE_FLAGS/exposure-hooks/config"


@pytest.fixture(autouse=True)
def evaluation_metrics_endpoint(library_env: dict[str, str], test_agent: TestAgentAPI) -> None:
    library_env["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"] = f"http://{test_agent.container_name}:4318/v1/metrics"


def install(test_agent: TestAgentAPI, fixture: dict[str, Any], *, wait: bool = True) -> None:
    previous = None
    previous_requests = test_agent.rc_requests() if wait else []
    if wait:
        for request in previous_requests:
            for target in request["body"].get("cached_target_files", []):
                if target["path"] == RC_PATH:
                    previous = target
        assert previous is not None, "The initial configuration must be acknowledged before an update"
    test_agent.set_remote_config(path=RC_PATH, payload=fixture)
    if not wait:
        return
    # Keep the same file ID. Wait for its new content hash and ACK, not a stale ACK.
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        for request in test_agent.rc_requests()[len(previous_requests) :]:
            body = request["body"]
            changed = any(
                target["path"] == RC_PATH and target != previous for target in body.get("cached_target_files", [])
            )
            acknowledged = any(
                state["id"] == "exposure-hooks" and state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
                for state in body["client"]["state"].get("config_states", [])
            )
            if changed and acknowledged:
                return
        time.sleep(0.05)
    pytest.fail("The SDK did not acknowledge the updated configuration content")


def evaluate(
    test_library: APMLibrary, subject: str, *, flag: str = "hook-flag", fail_after: bool = False
) -> dict[str, Any]:
    return test_library.ffe_evaluate(
        flag=flag,
        variation_type="STRING",
        default_value="fallback",
        targeting_key=subject,
        exposure_hooks=True,
        fail_after_hook=fail_after,
    )


def observations(
    result: dict[str, Any], *, exposure: bool, hit: bool, error_code: str = "", flag: str = "hook-flag"
) -> None:
    assert result["errorCode"] == error_code, result
    rows = result.get("exposureHooks", [])
    assert len(rows) == 2, result
    assert {row["hook"] for row in rows} == {0, 1}
    for row in rows:
        assert row["isExposure"] is exposure
        assert row["isCacheHit"] is hit
        assert row["shouldSend"] is (exposure and not hit)
        assert row["flag"] == flag
        assert row["errorCode"] == error_code
        assert row["value"] == result["value"]


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
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks"
        )
        rejected = evaluate(test_library, "athlete", fail_after=True)
        assert rejected["value"] == "fallback"
        assert rejected["reason"] == "ERROR"
        observations(rejected, exposure=False, hit=False, error_code="GENERAL")
        # The failed evaluation must not consume the first successful exposure.
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
        observations(failed, exposure=False, hit=False, error_code="FLAG_NOT_FOUND", flag="missing")

        # Evaluation metrics are a positive control when Datadog exposure logging is off.
        # The pinned test-agent image does not accept EVP /api/v2/flagevaluation yet.
        deadline = time.monotonic() + 20
        counts = []
        while time.monotonic() < deadline:
            counts = [
                sum(int(point["as_int"]) for point in metric["sum"]["data_points"])
                for export in test_agent.metrics()
                for resource in export.get("resource_metrics", [])
                for scope in resource.get("scope_metrics", [])
                for metric in scope.get("metrics", [])
                if metric["name"] == "feature_flag.evaluations"
            ]
            if 8 in counts:
                break
            time.sleep(0.2)
        assert 8 in counts, counts
        exposures = events(test_agent, "/api/v2/exposures", "exposures")
        if library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") == "false":
            assert exposures == []
        else:
            assert len(exposures) == 3, exposures
            assert sorted(event["serial_id"] for event in exposures) == [0, 0, 42]

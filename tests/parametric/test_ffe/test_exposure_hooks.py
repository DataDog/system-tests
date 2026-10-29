"""Customer exposure decisions share the Datadog cache, including warehouse-only mode."""

import base64
import json
import time
from collections import Counter
from typing import Any

from tests.ffe.utils.fixtures import make_ufc_fixture
from tests.parametric.conftest import APMLibrary
from utils import features, pytest, scenarios, slow
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI

BASE_ENV = {
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
    "DD_FLAGGING_EVALUATION_COUNTS_ENABLED": "true",
    "DD_METRICS_OTEL_ENABLED": "true",
    "OTEL_METRIC_EXPORT_INTERVAL": "1000",
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
    assert (result["errorCode"] or "") == error_code, result
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


def assert_evaluation_count(test_agent: TestAgentAPI, expected: int) -> None:
    # OTLP capture is supported by the stock test agent, unlike EVP evaluations.
    deadline = time.monotonic() + 20
    counts: list[int] = []
    while time.monotonic() < deadline:
        counts = [
            sum(int(point["as_int"]) for point in metric["sum"]["data_points"])
            for export in test_agent.metrics()
            for resource in export.get("resource_metrics", [])
            for scope in resource.get("scope_metrics", [])
            for metric in scope.get("metrics", [])
            if metric["name"] == "feature_flag.evaluations"
        ]
        if expected in counts:
            return
        time.sleep(0.2)
    assert expected in counts, counts


@scenarios.parametric
@features.feature_flags_exposures
class Test_FFE_ExposureHooks:
    @pytest.mark.parametrize(
        "library_env",
        [
            {**BASE_ENV, "SYSTEM_TESTS_FFE_MULTI_PROVIDER": "true"},
            {
                **BASE_ENV,
                "SYSTEM_TESTS_FFE_MULTI_PROVIDER": "true",
                "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "false",
            },
        ],
    )
    def test_multiprovider_exposure_guard(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        install(test_agent, make_ufc_fixture("hook-flag", serial_id=42), wait=False)
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks", wait_loops=500
        )
        assert test_library.ffe_start()
        for rejected in (True, False, False):
            result = evaluate(test_library, "athlete", fail_after=rejected)
            assert result["value"] == ("fallback" if rejected else "on-value")
            assert not result.get("exposureHooks"), result

        # The guard stops exposures, not evaluation telemetry or flag delivery.
        assert_evaluation_count(test_agent, 3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            assert events(test_agent, "/api/v2/exposures", "exposures") == []
            time.sleep(0.2)

    @pytest.mark.parametrize("library_env", [{**BASE_ENV}])
    @pytest.mark.parametrize("full_data", [False, True])
    @slow
    def test_evaluation_feature_aggregation(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, *, full_data: bool
    ) -> None:
        fixture = make_ufc_fixture("hook-flag", serial_id=42, observe_full_evaluation_data=full_data)
        allocation = fixture["flags"]["hook-flag"]["allocations"][0]
        allocation["doLog"] = False
        split = allocation["splits"][0]
        split["features"] = [
            {"key": "group", "value": "a", "destinations": ["EVALUATION"]},
            {"key": "shared", "value": True, "destinations": ["EVALUATION", "HOOK"]},
            {"key": "hook_only", "value": 2.5, "destinations": ["HOOK"]},
        ]
        install(test_agent, fixture, wait=False)
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks", wait_loops=500
        )
        assert test_library.ffe_start()
        for group in ("a", "b"):
            if group == "b":
                split["features"][0]["value"] = group
                install(test_agent, fixture)
            for _ in range(2):
                result = evaluate(test_library, "athlete")
                observations(result, exposure=False, hit=False)
                assert result["value"] == "on-value"
                for row in result["exposureHooks"]:
                    assert row["features"] == {"shared": True, "hook_only": 2.5}

        deadline = time.monotonic() + 20
        evaluations: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            evaluations = events(test_agent, "/api/v2/flagevaluation", "flagEvaluations")
            if sum(event["evaluation_count"] for event in evaluations) >= 4:
                break
            time.sleep(0.2)
        counts = {"a": 0, "b": 0}
        for event in evaluations:
            group = event["features"]["group"]
            assert event["features"] == {"group": group, "shared": True}
            counts[group] += event["evaluation_count"]
            assert event["flag"]["key"] == "hook-flag"
            assert event["variant"]["key"] == "on"
            if not full_data:
                assert "context" not in event
                assert event.get("targeting_key") != "athlete"
        assert counts == {"a": 2, "b": 2}, evaluations
        assert events(test_agent, "/api/v2/exposures", "exposures") == []

    @pytest.mark.parametrize(
        "library_env",
        [{**BASE_ENV}, {**BASE_ENV, "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "false"}],
    )
    def test_split_feature_destinations(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        fixture = make_ufc_fixture("hook-flag", serial_id=0)
        split = fixture["flags"]["hook-flag"]["allocations"][0]["splits"][0]
        split["features"] = [
            {"key": "holdout.key", "value": "q3-holdout", "destinations": ["HOOK"]},
            {"key": "holdout.assignment_group", "value": "status_quo", "destinations": ["HOOK"]},
            {"key": "shared", "value": True, "destinations": ["HOOK", "EXPOSURE", "EVALUATION"]},
            {"key": "exposure_only", "value": 2.5, "destinations": ["EXPOSURE"]},
            {"key": "evaluation_only", "value": "a", "destinations": ["EVALUATION"]},
            {"key": "unknown", "value": True, "destinations": ["FUTURE"]},
            {"key": "invalid", "value": {"nested": True}, "destinations": ["HOOK"]},
            {"key": "holdout.key", "value": "duplicate", "destinations": ["HOOK", "EXPOSURE"]},
            None,
        ]
        install(test_agent, fixture, wait=False)
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks", wait_loops=500
        )
        assert test_library.ffe_start()
        for hit in (False, True):
            result = evaluate(test_library, "athlete")
            observations(result, exposure=True, hit=hit)
            assert result["value"] == "on-value"
            for row in result["exposureHooks"]:
                assert row["features"] == {
                    "holdout.key": "q3-holdout",
                    "holdout.assignment_group": "status_quo",
                    "shared": True,
                }

        # A new holdout split has a new serial ID, even when its flag value is unchanged.
        split["serialId"] = 42
        split["features"][1]["value"] = "all_shipped"
        install(test_agent, fixture)
        changed = evaluate(test_library, "athlete")
        observations(changed, exposure=True, hit=False)
        for row in changed["exposureHooks"]:
            assert row["features"]["holdout.assignment_group"] == "all_shipped"
            assert row["metadata"]["__dd_split_serial_id"] == 42

        # Old configurations remain valid and produce no features field in the event.
        split.pop("features")
        split["serialId"] = 43
        install(test_agent, fixture)
        plain = evaluate(test_library, "athlete")
        observations(plain, exposure=True, hit=False)
        for row in plain["exposureHooks"]:
            assert not row["features"]

        disabled = library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") == "false"
        deadline = time.monotonic() + (5 if disabled else 20)
        while time.monotonic() < deadline:
            exposures = events(test_agent, "/api/v2/exposures", "exposures")
            if disabled:
                assert exposures == []
            elif len(exposures) >= 3:
                break
            time.sleep(0.2)
        if not disabled:
            assert len(exposures) == 3, exposures
            by_serial = {event["serial_id"]: event for event in exposures}
            assert by_serial[0]["features"] == {"shared": True, "exposure_only": 2.5}
            assert by_serial[42]["features"] == {"shared": True, "exposure_only": 2.5}
            assert "features" not in by_serial[43]

    @pytest.mark.parametrize(
        "library_env",
        [{**BASE_ENV}, {**BASE_ENV, "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "false"}],
    )
    def test_after_hook_failure_preserves_exposure_cache(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        install(test_agent, make_ufc_fixture("hook-flag", serial_id=0), wait=False)
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks", wait_loops=500
        )
        assert test_library.ffe_start()
        rejected = evaluate(test_library, "athlete", fail_after=True)
        assert rejected["value"] == "fallback"
        rows = rejected["exposureHooks"]
        assert len(rows) == 2
        assert {row["hook"] for row in rows} == {0, 1}
        for row in rows:
            assert row["value"] == "fallback"
            assert row["errorCode"] == "GENERAL"
            assert row["reason"] == "ERROR"
            assert row["isExposure"] is False
            assert row["isCacheHit"] is False
            assert row["shouldSend"] is False
        # Observe delivery before retrying: a premature exposure could otherwise
        # be hidden by writer deduplication of the successful retry.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            assert events(test_agent, "/api/v2/exposures", "exposures") == []
            time.sleep(0.2)
        assert events(test_agent, "/api/v2/exposures", "exposures") == []

        # A rejected evaluation must not consume the next successful exposure.
        observations(evaluate(test_library, "athlete"), exposure=True, hit=False)
        observations(evaluate(test_library, "athlete"), exposure=True, hit=True)

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            exposures = events(test_agent, "/api/v2/exposures", "exposures")
            if library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") == "false":
                assert exposures == []
            else:
                assert len(exposures) <= 1
            time.sleep(0.2)
        exposures = events(test_agent, "/api/v2/exposures", "exposures")
        if library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") != "false":
            assert len(exposures) == 1
            assert exposures[0]["serial_id"] == 0

    @pytest.mark.parametrize(
        "library_env",
        [{**BASE_ENV}, {**BASE_ENV, "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "false"}],
    )
    def test_shared_cache_and_destination_control(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        fixture = make_ufc_fixture("hook-flag", serial_id=0)
        install(test_agent, fixture, wait=False)
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="exposure-hooks", wait_loops=500
        )
        assert test_library.ffe_start()
        split = fixture["flags"]["hook-flag"]["allocations"][0]["splits"][0]
        # Reverting or removing a serial is a new assignment, not a historical cache hit.
        sequence = [
            ("athlete", 0, False),
            ("athlete", 0, True),
            ("another-athlete", 0, False),
            ("athlete", 42, False),
            ("athlete", 42, True),
            ("athlete", 0, False),
            ("athlete", 0, True),
            ("athlete", None, False),
            ("athlete", None, True),
        ]
        for subject, serial, hit in sequence:
            if split.get("serialId") != serial:
                if serial is None:
                    split.pop("serialId")
                else:
                    split["serialId"] = serial
                install(test_agent, fixture)
            result = evaluate(test_library, subject)
            observations(result, exposure=True, hit=hit)
            assert result["value"] == "on-value"
            for row in result["exposureHooks"]:
                assert row["subject"] == subject
                assert row["variant"] == "on"
                assert row["allocationKey"] == "default-allocation"
                if serial is None:
                    assert "__dd_split_serial_id" not in row["metadata"]
                else:
                    assert row["metadata"]["__dd_split_serial_id"] == serial

        fixture["flags"]["hook-flag"]["allocations"][0]["doLog"] = False
        install(test_agent, fixture)
        observations(evaluate(test_library, "athlete"), exposure=False, hit=False)
        failed = evaluate(test_library, "athlete", flag="missing")
        observations(failed, exposure=False, hit=False, error_code="FLAG_NOT_FOUND", flag="missing")

        # Evaluation metrics are a positive control when Datadog exposure logging is off.
        assert_evaluation_count(test_agent, len(sequence) + 2)
        if library_env.get("DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED") == "false":
            # Observe multiple flush intervals; metric delivery does not prove exposure delivery.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                assert events(test_agent, "/api/v2/exposures", "exposures") == []
                time.sleep(0.2)
        else:
            deadline = time.monotonic() + 20
            exposures = []
            while time.monotonic() < deadline:
                exposures = events(test_agent, "/api/v2/exposures", "exposures")
                if len(exposures) >= 5:
                    break
                time.sleep(0.2)
            assert len(exposures) == 5, exposures
            for event in exposures:
                if event.get("serial_id") is None:
                    assert "serial_id" not in event
            assert Counter(
                (
                    event["subject"]["id"],
                    event["flag"]["key"],
                    event["allocation"]["key"],
                    event["variant"]["key"],
                    event.get("serial_id"),
                )
                for event in exposures
            ) == Counter(
                (subject, "hook-flag", "default-allocation", "on", serial)
                for subject, serial, hit in sequence
                if not hit
            )

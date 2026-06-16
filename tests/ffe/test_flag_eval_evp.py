"""Test server-side feature flag evaluation counts via EVP flagevaluation."""

import json
import time
from typing import Any
from typing import cast

import pytest

from utils import HttpResponse
from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import scenarios
from utils import weblog


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
EVP_FLAGEVALUATIONS_PATH = "/api/v2/flagevaluations"
EVP_FLUSH_WAIT_SECONDS = 12

JSON = dict[str, Any]


def make_ufc_fixture(
    flag_key: str,
    variant_key: str = "on",
    variation_type: str = "STRING",
    *,
    enabled: bool = True,
) -> JSON:
    values: dict[str, dict[str, str | bool | float | int]] = {
        "STRING": {"on": "on-value", "off": "off-value"},
        "BOOLEAN": {"on": True, "off": False},
        "NUMERIC": {"on": 1.5, "off": 0.0},
        "INTEGER": {"on": 42, "off": 0},
    }
    var_values = values[variation_type]

    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": enabled,
                "variationType": variation_type,
                "variations": {
                    "on": {"key": "on", "value": var_values["on"]},
                    "off": {"key": "off", "value": var_values["off"]},
                },
                "allocations": [
                    {
                        "key": "default-allocation",
                        "rules": [],
                        "splits": [{"variationKey": variant_key, "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def make_multi_flag_fixture(flag_keys: list[str]) -> JSON:
    fixture = make_ufc_fixture(flag_keys[0])
    flags = cast("JSON", fixture["flags"])
    for flag_key in flag_keys[1:]:
        flags[flag_key] = cast("JSON", make_ufc_fixture(flag_key)["flags"])[flag_key]
    return fixture


def evaluate_flag(
    flag_key: str,
    *,
    targeting_key: str = "user-1",
    attributes: JSON | None = None,
    variation_type: str = "STRING",
    default_value: object = "default",
) -> HttpResponse:
    return weblog.post(
        "/ffe",
        json={
            "flag": flag_key,
            "variationType": variation_type,
            "defaultValue": default_value,
            "targetingKey": targeting_key,
            "attributes": attributes or {},
        },
    )


def wait_for_evp_flush() -> None:
    time.sleep(EVP_FLUSH_WAIT_SECONDS)


def find_evp_flagevaluation_events(flag_key: str) -> list[tuple[JSON, JSON]]:
    results: list[tuple[JSON, JSON]] = []

    for data in interfaces.agent.get_data(path_filters=EVP_FLAGEVALUATIONS_PATH):
        content = data["request"]["content"]
        if not isinstance(content, dict):
            continue

        events = content.get("flagEvaluations")
        if not isinstance(events, list):
            continue

        for event in events:
            if not isinstance(event, dict):
                continue

            flag = event.get("flag")
            if isinstance(flag, dict) and flag.get("key") == flag_key:
                results.append((cast("JSON", content), cast("JSON", event)))

    return results


def sum_evaluation_count(events: list[tuple[JSON, JSON]]) -> int:
    total = 0
    for _, event in events:
        count = event.get("evaluation_count")
        if isinstance(count, int):
            total += count
    return total


def assert_no_reason_field(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        assert "reason" not in value, f"OpenFeature reason must not be emitted at {path}"
        for key, child in value.items():
            assert_no_reason_field(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_reason_field(child, f"{path}[{index}]")


def object_key(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    assert isinstance(value, dict), f"{field_name} must be an object when present"
    key = value.get("key")
    assert isinstance(key, str), f"{field_name}.key must be a string"
    assert key, f"{field_name}.key must be non-empty"
    return key


def assert_batch_context(batch: JSON) -> None:
    context = batch.get("context")
    assert isinstance(context, dict), "batch context must be an object"
    assert context.get("service") == "weblog", f"expected service weblog, got {context}"
    if "env" in context:
        assert context["env"] == "system-tests", f"expected env system-tests, got {context}"


def assert_event_contract(event: JSON, flag_key: str) -> None:
    assert_no_reason_field(event)
    assert "targeting_rule" not in event, "targeting_rule must be omitted without real rule metadata"

    flag = event.get("flag")
    assert isinstance(flag, dict), "flag must be an object"
    assert flag.get("key") == flag_key, f"expected flag {flag_key}, got {flag}"

    timestamp = event.get("timestamp")
    first_evaluation = event.get("first_evaluation")
    last_evaluation = event.get("last_evaluation")
    evaluation_count = event.get("evaluation_count")

    assert isinstance(timestamp, int), "timestamp must be an integer"
    assert isinstance(first_evaluation, int), "first_evaluation must be an integer"
    assert isinstance(last_evaluation, int), "last_evaluation must be an integer"
    assert isinstance(evaluation_count, int), "evaluation_count must be an integer"
    assert evaluation_count >= 1, f"evaluation_count must be positive: {event}"
    assert first_evaluation <= last_evaluation, f"first_evaluation must be <= last_evaluation: {event}"

    object_key(event.get("variant"), "variant")
    object_key(event.get("allocation"), "allocation")


def event_identity(event: JSON) -> str:
    visible_identity = {
        "flag": event.get("flag"),
        "variant": event.get("variant"),
        "allocation": event.get("allocation"),
        "runtime_default_used": event.get("runtime_default_used"),
        "targeting_key": event.get("targeting_key"),
        "targeting_rule": event.get("targeting_rule"),
        "error": event.get("error"),
        "context": event.get("context"),
    }
    return json.dumps(visible_identity, sort_keys=True, default=str)


def assert_no_duplicate_visible_events(events: list[tuple[JSON, JSON]]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for _, event in events:
        identity = event_identity(event)
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)

    assert not duplicates, f"found duplicate serialized-visible EVP buckets: {sorted(duplicates)}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Basic:
    """Test that flag evaluation produces an EVP flagevaluation payload."""

    def setup_ffe_evp_flagevaluation_basic(self) -> None:
        config_id = "ffe-evp-basic"
        self.flag_key = "evp-basic-flag"
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.r = evaluate_flag(self.flag_key, targeting_key="evp-basic-user", attributes={})
        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_basic(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        batch, event = events[0]
        assert_batch_context(batch)
        assert_event_contract(event, self.flag_key)
        assert object_key(event.get("variant"), "variant") == "on"
        assert object_key(event.get("allocation"), "allocation") == "default-allocation"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Count:
    """Test that repeated evaluations are counted in EVP flagevaluation payloads."""

    def setup_ffe_evp_flagevaluation_count(self) -> None:
        config_id = "ffe-evp-count"
        self.flag_key = "evp-count-flag"
        self.eval_count = 5
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.responses = [
            evaluate_flag(self.flag_key, targeting_key="evp-count-user", attributes={}) for _ in range(self.eval_count)
        ]
        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_count(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        total_count = sum_evaluation_count(events)
        assert total_count >= self.eval_count, f"Expected count >= {self.eval_count}, got {total_count}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Context_Bounds:
    """Test that EVP evaluation context is bounded before it reaches payloads."""

    def setup_ffe_evp_flagevaluation_context_bounds(self) -> None:
        config_id = "ffe-evp-context-bounds"
        self.flag_key = "evp-context-bounds-flag"
        self.oversized_field = "field_010_oversized"
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        attributes: JSON = {f"field_{index:03d}": f"value-{index}" for index in range(300)}
        attributes[self.oversized_field] = "x" * 300

        self.r = evaluate_flag(self.flag_key, targeting_key="evp-context-user", attributes=attributes)
        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_context_bounds(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        full_context_events = 0
        for _, event in events:
            assert_event_contract(event, self.flag_key)
            context = event.get("context")
            if context is None:
                continue

            assert isinstance(context, dict), "context must be an object when present"
            evaluation_context = context.get("evaluation")
            if evaluation_context is None:
                continue

            full_context_events += 1
            assert isinstance(evaluation_context, dict), "context.evaluation must be an object"
            assert len(evaluation_context) <= 256, f"context.evaluation has too many fields: {len(evaluation_context)}"
            assert self.oversized_field not in evaluation_context, "oversized string context field must be omitted"

        if full_context_events == 0:
            for _, event in events:
                assert "context" not in event, f"degraded event should omit context: {event}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Runtime_Default:
    """Test that runtime defaults are surfaced without OpenFeature reason."""

    def setup_ffe_evp_flagevaluation_runtime_default(self) -> None:
        rc.tracer_rc_state.reset().apply()

        self.flag_key = "evp-runtime-default-flag"
        self.r = evaluate_flag(self.flag_key, targeting_key="evp-default-user", attributes={})
        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_runtime_default(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        assert any(event.get("runtime_default_used") is True for _, event in events), (
            f"Expected runtime_default_used=true for flag {self.flag_key}, got {events}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Load_Aggregation:
    """Test CI-safe load aggregation without treating system-tests as a perf test."""

    def setup_ffe_evp_flagevaluation_load_aggregation(self) -> None:
        config_id = "ffe-evp-load-aggregation"
        self.flag_keys = ["evp-load-flag-a", "evp-load-flag-b"]
        self.evals_per_flag = 30
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/{config_id}/config", make_multi_flag_fixture(self.flag_keys)
        ).apply()

        self.responses = []
        for flag_key in self.flag_keys:
            for index in range(self.evals_per_flag):
                self.responses.append(
                    evaluate_flag(
                        flag_key,
                        targeting_key=f"evp-load-user-{index % 10}",
                        attributes={"bucket": index % 10, "cohort": f"cohort-{index % 3}"},
                    )
                )

        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_load_aggregation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        for flag_key in self.flag_keys:
            events = find_evp_flagevaluation_events(flag_key)
            assert events, f"Expected EVP flagevaluation events for flag {flag_key}"
            assert_no_duplicate_visible_events(events)

            for _, event in events:
                assert_event_contract(event, flag_key)

            total_count = sum_evaluation_count(events)
            assert total_count >= self.evals_per_flag, (
                f"Expected count >= {self.evals_per_flag} for {flag_key}, got {total_count}"
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
class Test_FFE_EVP_Flagevaluation_Degradation:
    """Test degraded EVP shape when an SDK exposes a test cap override."""

    def setup_ffe_evp_flagevaluation_degradation(self) -> None:
        config_id = "ffe-evp-degradation"
        self.flag_key = "evp-degradation-flag"
        self.eval_count = 150
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.responses = [
            evaluate_flag(
                self.flag_key,
                targeting_key=f"evp-degradation-user-{index}",
                attributes={"distinct": index},
            )
            for index in range(self.eval_count)
        ]
        wait_for_evp_flush()

    def test_ffe_evp_flagevaluation_degradation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation events for flag {self.flag_key}"

        degraded_events = [event for _, event in events if "context" not in event and "targeting_key" not in event]
        if not degraded_events:
            pytest.skip("No SDK/test cap override is available to force degraded EVP flagevaluation buckets")

        for event in degraded_events:
            assert_event_contract(event, self.flag_key)
            assert "context" not in event, f"degraded event must omit context: {event}"
            assert "targeting_key" not in event, f"degraded event must omit targeting_key: {event}"
            assert object_key(event.get("variant"), "variant") == "on"
            assert object_key(event.get("allocation"), "allocation") == "default-allocation"

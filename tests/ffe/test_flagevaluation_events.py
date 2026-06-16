"""Test server-side FFE EVP flagevaluation events."""

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

import pytest

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
FLAGEVALUATIONS_PATH = "/api/v2/flagevaluations"
SCHEMA_MIN_TIMESTAMP_MS = 1759276800000
MAX_CONTEXT_FIELDS = 256
MAX_CONTEXT_STRING_LENGTH = 256


def make_ufc_fixture(flag_key: str, variant_key: str = "on", *, enabled: bool = True):
    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": enabled,
                "variationType": "STRING",
                "variations": {
                    "on": {"key": "on", "value": "on-value"},
                    "off": {"key": "off", "value": "off-value"},
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


def make_targeting_fixture(flag_key: str):
    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": True,
                "variationType": "STRING",
                "variations": {
                    "on": {"key": "on", "value": "on-value"},
                    "off": {"key": "off", "value": "off-value"},
                },
                "allocations": [
                    {
                        "key": "targeted-allocation",
                        "rules": [
                            {
                                "key": "tier-premium-rule",
                                "conditions": [
                                    {
                                        "operator": "ONE_OF",
                                        "attribute": "tier",
                                        "value": ["premium"],
                                    }
                                ],
                            }
                        ],
                        "splits": [{"variationKey": "on", "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def evaluate_flag(flag_key: str, targeting_key: str, attributes: dict | None = None, default_value: str = "default"):
    return weblog.post(
        "/ffe",
        json={
            "flag": flag_key,
            "variationType": "STRING",
            "defaultValue": default_value,
            "targetingKey": targeting_key,
            "attributes": attributes or {},
        },
    )


def _payload_flag_evaluations(data: dict) -> list[dict]:
    if data.get("path") != FLAGEVALUATIONS_PATH:
        return []

    content = data.get("request", {}).get("content")
    assert isinstance(content, dict), f"Expected object payload for {FLAGEVALUATIONS_PATH}, got {content!r}"

    evaluations = content.get("flagEvaluations")
    assert isinstance(evaluations, list), f"Expected flagEvaluations list in payload, got {content!r}"
    return evaluations


def find_flag_evaluations(flag_key: str) -> list[dict]:
    evaluations = []
    for data in interfaces.agent.get_data(path_filters=FLAGEVALUATIONS_PATH):
        for event in _payload_flag_evaluations(data):
            if event.get("flag", {}).get("key") == flag_key:
                evaluations.append(event)
    return evaluations


def _total_count(events: Iterable[dict]) -> int:
    return sum(event.get("evaluation_count", 0) for event in events)


def wait_for_flag_evaluations(flag_key: str, min_count: int = 1, timeout: int = 20) -> list[dict]:
    def observed(data: dict) -> bool:
        _payload_flag_evaluations(data)
        return _total_count(find_flag_evaluations(flag_key)) >= min_count

    assert interfaces.agent.wait_for(observed, timeout=timeout), (
        f"Timed out waiting for at least {min_count} flagevaluation event(s) for flag {flag_key!r}; "
        f"observed {find_flag_evaluations(flag_key)!r}"
    )

    events = find_flag_evaluations(flag_key)
    assert _total_count(events) >= min_count, (
        f"Expected at least {min_count} evaluation(s) for {flag_key!r}, got {events!r}"
    )
    return events


def assert_no_key_recursive(value: object, key_name: str):
    if isinstance(value, dict):
        assert key_name not in value, f"Unexpected {key_name!r} field in {value!r}"
        for child in value.values():
            assert_no_key_recursive(child, key_name)
    elif isinstance(value, list):
        for child in value:
            assert_no_key_recursive(child, key_name)


def assert_common_event_shape(event: dict, flag_key: str):
    allowed_fields = {
        "timestamp",
        "flag",
        "first_evaluation",
        "last_evaluation",
        "evaluation_count",
        "runtime_default_used",
        "targeting_key",
        "context",
        "variant",
        "allocation",
        "targeting_rule",
        "error",
    }
    assert set(event).issubset(allowed_fields), f"Unexpected flagevaluation fields: {event!r}"
    assert_no_key_recursive(event, "reason")

    assert event["flag"]["key"] == flag_key
    assert isinstance(event["timestamp"], int)
    assert isinstance(event["first_evaluation"], int)
    assert isinstance(event["last_evaluation"], int)
    assert event["timestamp"] >= SCHEMA_MIN_TIMESTAMP_MS
    assert event["first_evaluation"] >= SCHEMA_MIN_TIMESTAMP_MS
    assert event["last_evaluation"] >= event["first_evaluation"]
    assert event["evaluation_count"] >= 1

    if "variant" in event:
        assert isinstance(event["variant"].get("key"), str)
    if "allocation" in event:
        assert isinstance(event["allocation"].get("key"), str)
    if "targeting_rule" in event:
        assert isinstance(event["targeting_rule"].get("key"), str)
    if "runtime_default_used" in event:
        assert isinstance(event["runtime_default_used"], bool)


def assert_context_is_bounded(event: dict):
    context = event.get("context")
    if not context:
        return

    evaluation_context = context.get("evaluation")
    if not evaluation_context:
        return

    assert len(evaluation_context) <= MAX_CONTEXT_FIELDS, (
        f"Expected at most {MAX_CONTEXT_FIELDS} context fields, got {len(evaluation_context)}"
    )

    oversized_values = {
        key: value for key, value in evaluation_context.items() if isinstance(value, str) and len(value) > 256
    }
    assert not oversized_values, f"Expected oversized context strings to be pruned, got {oversized_values!r}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Visible_Schema:
    def setup_ffe_flagevaluation_visible_schema(self):
        self.flag_key = "evp-visible-schema-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-visible-schema/config", make_ufc_fixture(self.flag_key)
        ).apply()

        self.r = evaluate_flag(self.flag_key, "user-visible-schema", {"tier": "free"})

    def test_ffe_flagevaluation_visible_schema(self):
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        events = wait_for_flag_evaluations(self.flag_key)
        for event in events:
            assert_common_event_shape(event, self.flag_key)

        matching_event = events[0]
        assert matching_event.get("variant", {}).get("key") == "on"
        assert matching_event.get("allocation", {}).get("key") == "default-allocation"
        assert "targeting_rule" not in matching_event, (
            f"No-rule fixture must omit targeting_rule, got {matching_event!r}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Aggregation_Count:
    def setup_ffe_flagevaluation_aggregation_count(self):
        self.flag_key = "evp-aggregation-count-flag"
        self.eval_count = 5
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-aggregation-count/config", make_ufc_fixture(self.flag_key)
        ).apply()

        self.responses = [evaluate_flag(self.flag_key, "user-count", {"plan": "pro"}) for _ in range(self.eval_count)]

    def test_ffe_flagevaluation_aggregation_count(self):
        for i, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {i + 1} failed: {response.text}"

        events = wait_for_flag_evaluations(self.flag_key, min_count=self.eval_count)
        assert _total_count(events) >= self.eval_count, f"Expected count >= {self.eval_count}, got {events!r}"
        for event in events:
            assert_common_event_shape(event, self.flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Bounded_Context:
    def setup_ffe_flagevaluation_bounded_context(self):
        self.flag_key = "evp-bounded-context-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-bounded-context/config", make_ufc_fixture(self.flag_key)
        ).apply()

        attributes = {f"field_{i:03}": f"value-{i}" for i in range(MAX_CONTEXT_FIELDS + 50)}
        attributes["oversized"] = "x" * (MAX_CONTEXT_STRING_LENGTH + 1)
        self.r = evaluate_flag(self.flag_key, "user-bounded-context", attributes)

    def test_ffe_flagevaluation_bounded_context(self):
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        events = wait_for_flag_evaluations(self.flag_key)
        for event in events:
            assert_common_event_shape(event, self.flag_key)
            assert_context_is_bounded(event)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Runtime_Default:
    def setup_ffe_flagevaluation_runtime_default(self):
        self.config_flag_key = "evp-runtime-default-existing-flag"
        self.missing_flag_key = "evp-runtime-default-missing-flag"
        self.default_value = "runtime-default"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-runtime-default/config", make_ufc_fixture(self.config_flag_key)
        ).apply()

        self.r = evaluate_flag(self.missing_flag_key, "user-runtime-default", default_value=self.default_value)

    def test_ffe_flagevaluation_runtime_default(self):
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"
        assert self.r.json().get("value") == self.default_value

        events = wait_for_flag_evaluations(self.missing_flag_key)
        default_events = [event for event in events if event.get("runtime_default_used") is True]
        assert default_events, f"Expected runtime_default_used=true for {self.missing_flag_key!r}, got {events!r}"
        for event in default_events:
            assert_common_event_shape(event, self.missing_flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Concurrent_Identical_Evaluations:
    def setup_ffe_flagevaluation_concurrent_identical_evaluations(self):
        self.flag_key = "evp-concurrent-identical-flag"
        self.eval_count = 20
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-concurrent-identical/config", make_ufc_fixture(self.flag_key)
        ).apply()

        with ThreadPoolExecutor(max_workers=8) as executor:
            self.responses = list(
                executor.map(
                    lambda _: evaluate_flag(self.flag_key, "user-concurrent", {"cohort": "same"}),
                    range(self.eval_count),
                )
            )

    def test_ffe_flagevaluation_concurrent_identical_evaluations(self):
        for i, response in enumerate(self.responses):
            assert response.status_code == 200, f"Concurrent request {i + 1} failed: {response.text}"

        events = wait_for_flag_evaluations(self.flag_key, min_count=self.eval_count)
        assert _total_count(events) >= self.eval_count, f"Expected count >= {self.eval_count}, got {events!r}"
        for event in events:
            assert_common_event_shape(event, self.flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_High_Cardinality:
    def setup_ffe_flagevaluation_high_cardinality(self):
        self.flag_key = "evp-high-cardinality-flag"
        self.eval_count = 24
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-high-cardinality/config", make_ufc_fixture(self.flag_key)
        ).apply()

        self.responses = [
            evaluate_flag(self.flag_key, f"user-cardinality-{i}", {"account": f"account-{i}"})
            for i in range(self.eval_count)
        ]

    def test_ffe_flagevaluation_high_cardinality(self):
        for i, response in enumerate(self.responses):
            assert response.status_code == 200, f"High-cardinality request {i + 1} failed: {response.text}"

        events = wait_for_flag_evaluations(self.flag_key, min_count=self.eval_count)
        assert _total_count(events) >= self.eval_count, f"Expected count >= {self.eval_count}, got {events!r}"
        for event in events:
            assert_common_event_shape(event, self.flag_key)
            assert_context_is_bounded(event)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Targeting_Rule_Metadata:
    def setup_ffe_flagevaluation_targeting_rule_metadata(self):
        self.flag_key = "evp-targeting-rule-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/evp-targeting-rule/config", make_targeting_fixture(self.flag_key)
        ).apply()

        self.r = evaluate_flag(self.flag_key, "user-targeting-rule", {"tier": "premium"})

    def test_ffe_flagevaluation_targeting_rule_metadata(self):
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        events = wait_for_flag_evaluations(self.flag_key)
        targeted_events = [event for event in events if event.get("allocation", {}).get("key") == "targeted-allocation"]
        assert targeted_events, f"Expected targeted allocation event, got {events!r}"

        for event in targeted_events:
            assert_common_event_shape(event, self.flag_key)
            assert event.get("targeting_rule", {}).get("key") == "tier-premium-rule", (
                f"Expected targeting_rule.key from real rule metadata, got {event!r}"
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_FlagEvaluation_Degraded_Shape:
    def test_ffe_flagevaluation_degraded_shape(self):
        pytest.skip(
            "System tests cannot force tracer aggregation caps or async queue overflow through the public /ffe "
            "weblog endpoint without SDK-specific test-only controls. FFL-2446 reviewers should validate degraded "
            "shape in SDK unit tests and treat this system test as the external-path coverage."
        )

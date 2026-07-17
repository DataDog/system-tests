"""Test server-side feature flag evaluation counts via EVP flagevaluation."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import cast


from tests.ffe.utils.fixtures import JSON, make_ufc_fixture
from utils import HttpResponse
from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import scenarios
from utils import not_yet_implemented
from utils import weblog


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"
EVP_FLAGEVALUATIONS_PATH = "/api/v2/flagevaluation"
EVP_WAIT_TIMEOUT_SECONDS = 30
EVP_LOAD_WAIT_TIMEOUT_SECONDS = 60
EVP_FULL_TIER_PER_FLAG_CAP = 10_000
EVP_DEGRADATION_OVERFLOW_EVALS = 2_000

# Fixed input/output vector for the PII-protection tests. Every SDK's L1 unit tests
# should assert against the same input to prove byte-identical hashing across SDKs.
PII_TARGETING_KEY = "jane.doe@datadoghq.com"
PII_TARGETING_KEY_HASHED = "sha256_b4698f9b6d186781fa8dc59e533578fa2d8379a46b1cf6db85cda6aa9c99e51b"
PII_ATTRIBUTES: dict[str, object] = {
    "org_id": 1234,
    "user_email": "jane.doe@datadoghq.com",
    "plan": "enterprise",
    "region": "us-east-1",
    "account.tier": "gold",
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
    targeting_keys: list[str] | None = None,
    attributes: JSON | None = None,
    variation_type: str = "STRING",
    default_value: object = "default",
) -> HttpResponse:
    payload = {
        "flag": flag_key,
        "variationType": variation_type,
        "defaultValue": default_value,
        "targetingKey": targeting_key,
        "attributes": attributes or {},
    }
    if targeting_keys is not None:
        payload["targetingKeys"] = targeting_keys
    return weblog.post("/ffe", json=payload)


def evp_flagevaluation_events_from_data(data: JSON, flag_key: str) -> list[tuple[JSON, JSON]]:
    if data.get("path") != EVP_FLAGEVALUATIONS_PATH:
        return []

    request = data.get("request")
    if not isinstance(request, dict):
        return []

    content = request.get("content")
    if not isinstance(content, dict):
        return []

    events = content.get("flagEvaluations")
    if not isinstance(events, list):
        return []

    results: list[tuple[JSON, JSON]] = []
    for event in events:
        if not isinstance(event, dict):
            continue

        flag = event.get("flag")
        if isinstance(flag, dict) and flag.get("key") == flag_key:
            results.append((cast("JSON", content), cast("JSON", event)))

    return results


def wait_for_evp_flagevaluation_event(flag_key: str) -> None:
    assert interfaces.agent.wait_for(
        lambda data: bool(evp_flagevaluation_events_from_data(cast("JSON", data), flag_key)),
        timeout=EVP_WAIT_TIMEOUT_SECONDS,
    ), f"Timed out waiting for EVP flagevaluation event for flag {flag_key}"


def find_evp_flagevaluation_events(flag_key: str) -> list[tuple[JSON, JSON]]:
    results: list[tuple[JSON, JSON]] = []

    for data in interfaces.agent.get_data(path_filters=EVP_FLAGEVALUATIONS_PATH):
        results.extend(evp_flagevaluation_events_from_data(cast("JSON", data), flag_key))

    return results


def sum_evaluation_count(events: list[tuple[JSON, JSON]]) -> int:
    total = 0
    for _, event in events:
        count = event.get("evaluation_count")
        if isinstance(count, int):
            total += count
    return total


def wait_for_evp_flagevaluation_count(flag_key: str, expected: int) -> None:
    assert interfaces.agent.wait_for(
        lambda _: sum_evaluation_count(find_evp_flagevaluation_events(flag_key)) >= expected,
        timeout=EVP_LOAD_WAIT_TIMEOUT_SECONDS,
    ), f"Timed out waiting for EVP flagevaluation count >= {expected} for flag {flag_key}"


def assert_total_evaluation_count(events: list[tuple[JSON, JSON]], expected: int, flag_key: str) -> None:
    total_count = sum_evaluation_count(events)
    assert total_count == expected, f"Expected count == {expected} for {flag_key}, got {total_count}"


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


def _assert_hashed_targeting_key(event: JSON) -> None:
    targeting_key = event.get("targeting_key")
    assert targeting_key == PII_TARGETING_KEY_HASHED, (
        f"Expected hashed targeting_key {PII_TARGETING_KEY_HASHED}, got {targeting_key!r}"
    )
    assert isinstance(targeting_key, str)
    assert targeting_key.startswith("sha256_"), f"hashed targeting_key must start with 'sha256_': {targeting_key!r}"
    assert len(targeting_key) == 71, f"hashed targeting_key must be 71 chars, got {len(targeting_key)}"
    hex_suffix = targeting_key[len("sha256_") :]
    assert len(hex_suffix) == 64, f"hashed targeting_key suffix must be 64 chars: {targeting_key!r}"
    assert all(c in "0123456789abcdef" for c in hex_suffix), (
        f"hashed targeting_key suffix must be lowercase hex: {targeting_key!r}"
    )


def assert_no_raw_pii_in_event(event: JSON, forbidden_values: list[str]) -> None:
    """Walk the entire serialized event and assert none of the raw PII strings appear anywhere.

    Guards against SDK bugs that route unhashed values into unexpected fields (e.g., a raw
    email leaking into ``context.user_email`` even when ``context.evaluation`` is correctly
    omitted).
    """
    serialized = json.dumps(event, default=str)
    for value in forbidden_values:
        assert value not in serialized, f"raw PII value {value!r} must not appear anywhere in event: {event}"


def assert_no_duplicate_visible_events(events: list[tuple[JSON, JSON]]) -> None:
    seen_by_batch: dict[int, set[str]] = {}
    duplicates: set[str] = set()
    for batch, event in events:
        seen = seen_by_batch.setdefault(id(batch), set())
        identity = event_identity(event)
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)

    assert not duplicates, f"found duplicate serialized-visible EVP buckets in one payload: {sorted(duplicates)}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_Basic:
    """Test that flag evaluation produces an EVP flagevaluation payload."""

    def setup_ffe_evp_flagevaluation_basic(self) -> None:
        config_id = "ffe-evp-basic"
        self.flag_key = "evp-basic-flag"
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.r = evaluate_flag(self.flag_key, targeting_key="evp-basic-user", attributes={})

    def test_ffe_evp_flagevaluation_basic(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        batch, event = events[0]
        assert_batch_context(batch)
        assert_event_contract(event, self.flag_key)
        assert object_key(event.get("variant"), "variant") == "on"
        assert object_key(event.get("allocation"), "allocation") == "default-allocation"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
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

    def test_ffe_evp_flagevaluation_count(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        assert_no_duplicate_visible_events(events)
        assert_total_evaluation_count(events, self.eval_count, self.flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
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

    def test_ffe_evp_flagevaluation_context_bounds(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
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
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_Runtime_Default:
    """Test that runtime defaults are surfaced without OpenFeature reason."""

    def setup_ffe_evp_flagevaluation_runtime_default(self) -> None:
        rc.tracer_rc_state.reset().apply()

        self.flag_key = "evp-runtime-default-flag"
        self.r = evaluate_flag(self.flag_key, targeting_key="evp-default-user", attributes={})

    def test_ffe_evp_flagevaluation_runtime_default(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        assert any(event.get("runtime_default_used") is True for _, event in events), (
            f"Expected runtime_default_used=true for flag {self.flag_key}, got {events}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
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

    def test_ffe_evp_flagevaluation_load_aggregation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        for flag_key in self.flag_keys:
            wait_for_evp_flagevaluation_event(flag_key)
            events = find_evp_flagevaluation_events(flag_key)
            assert events, f"Expected EVP flagevaluation events for flag {flag_key}"
            assert_no_duplicate_visible_events(events)

            for _, event in events:
                assert_event_contract(event, flag_key)

            assert_total_evaluation_count(events, self.evals_per_flag, flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_Burst_Aggregation:
    """Test a bounded request burst through the async EVP aggregation path."""

    def setup_ffe_evp_flagevaluation_burst_aggregation(self) -> None:
        config_id = "ffe-evp-burst-aggregation"
        self.flag_key = "evp-burst-aggregation-flag"
        self.eval_count = 512
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        with ThreadPoolExecutor(max_workers=32) as executor:
            self.responses = list(
                executor.map(
                    lambda _: evaluate_flag(
                        self.flag_key,
                        targeting_key="evp-burst-user",
                        attributes={"bucket": "burst", "cohort": "stress"},
                    ),
                    range(self.eval_count),
                )
            )

    def test_ffe_evp_flagevaluation_burst_aggregation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation events for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        assert_no_duplicate_visible_events(events)
        assert_total_evaluation_count(events, self.eval_count, self.flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_High_Cardinality_Aggregation:
    """Test many full-tier aggregation buckets stay distinct and counted."""

    def setup_ffe_evp_flagevaluation_high_cardinality_aggregation(self) -> None:
        config_id = "ffe-evp-high-cardinality-aggregation"
        self.flag_key = "evp-high-cardinality-aggregation-flag"
        self.eval_count = 128
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.responses = [
            evaluate_flag(
                self.flag_key,
                targeting_key=f"evp-cardinality-user-{index}",
                attributes={
                    "bucket": index,
                    "cohort": f"cohort-{index % 8}",
                    "typed": index % 2 == 0,
                },
            )
            for index in range(self.eval_count)
        ]

    def test_ffe_evp_flagevaluation_high_cardinality_aggregation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation events for flag {self.flag_key}"

        for _, event in events:
            assert_event_contract(event, self.flag_key)

        assert_no_duplicate_visible_events(events)
        assert_total_evaluation_count(events, self.eval_count, self.flag_key)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_Degradation:
    """Test degraded EVP shape after the production per-flag full-tier cap is exceeded."""

    def setup_ffe_evp_flagevaluation_degradation(self) -> None:
        config_id = "ffe-evp-degradation"
        self.flag_key = "evp-degradation-flag"
        self.eval_count = EVP_FULL_TIER_PER_FLAG_CAP + EVP_DEGRADATION_OVERFLOW_EVALS
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        targeting_keys = [f"evp-degradation-user-{index}" for index in range(self.eval_count)]
        self.responses = [
            evaluate_flag(
                self.flag_key,
                targeting_key=targeting_keys[0],
                targeting_keys=targeting_keys,
                attributes={},
            )
        ]

    def test_ffe_evp_flagevaluation_degradation(self) -> None:
        for index, response in enumerate(self.responses):
            assert response.status_code == 200, f"Request {index + 1} failed: {response.text}"

        wait_for_evp_flagevaluation_count(self.flag_key, self.eval_count)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation events for flag {self.flag_key}"

        degraded_events = [event for _, event in events if "context" not in event and "targeting_key" not in event]
        assert degraded_events, f"Expected degraded EVP flagevaluation buckets for flag {self.flag_key}"
        assert_no_duplicate_visible_events(events)
        assert_total_evaluation_count(events, self.eval_count, self.flag_key)

        for event in degraded_events:
            assert_event_contract(event, self.flag_key)
            assert "context" not in event, f"degraded event must omit context: {event}"
            assert "targeting_key" not in event, f"degraded event must omit targeting_key: {event}"
            assert object_key(event.get("variant"), "variant") == "on"
            assert object_key(event.get("allocation"), "allocation") == "default-allocation"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_ObserveFullData_Absent_Hashed:
    """Test that when observeFullEvaluationData is absent from UFC, targeting_key is hashed and context.evaluation is omitted (default PII-protection)."""

    def setup_ffe_evp_flagevaluation_observe_full_data_absent(self) -> None:
        config_id = "ffe-evp-observe-absent"
        self.flag_key = "evp-observe-absent-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key),
        ).apply()

        self.r = evaluate_flag(
            self.flag_key,
            targeting_key=PII_TARGETING_KEY,
            attributes=PII_ATTRIBUTES,
        )

    def test_ffe_evp_flagevaluation_observe_full_data_absent(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        forbidden_raw_values = [PII_TARGETING_KEY, *[str(v) for v in PII_ATTRIBUTES.values()]]

        for batch, event in events:
            assert_batch_context(batch)
            assert_event_contract(event, self.flag_key)
            _assert_hashed_targeting_key(event)

            context = event.get("context")
            if isinstance(context, dict):
                assert "evaluation" not in context, (
                    f"context.evaluation must be omitted when observeFullEvaluationData is absent: {context}"
                )

            assert_no_raw_pii_in_event(event, forbidden_raw_values)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_ObserveFullData_False_Hashed:
    """Test that when observeFullEvaluationData=false in UFC, targeting_key is hashed and context.evaluation is omitted."""

    def setup_ffe_evp_flagevaluation_observe_full_data_false(self) -> None:
        config_id = "ffe-evp-observe-false"
        self.flag_key = "evp-observe-false-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key, observe_full_evaluation_data=False),
        ).apply()

        self.r = evaluate_flag(
            self.flag_key,
            targeting_key=PII_TARGETING_KEY,
            attributes=PII_ATTRIBUTES,
        )

    def test_ffe_evp_flagevaluation_observe_full_data_false(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        forbidden_raw_values = [PII_TARGETING_KEY, *[str(v) for v in PII_ATTRIBUTES.values()]]

        for batch, event in events:
            assert_batch_context(batch)
            assert_event_contract(event, self.flag_key)
            _assert_hashed_targeting_key(event)

            context = event.get("context")
            if isinstance(context, dict):
                assert "evaluation" not in context, (
                    f"context.evaluation must be omitted when observeFullEvaluationData=false: {context}"
                )

            assert_no_raw_pii_in_event(event, forbidden_raw_values)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evp_flagevaluation
@not_yet_implemented
class Test_FFE_EVP_Flagevaluation_ObserveFullData_True_Unhashed:
    """Test that when observeFullEvaluationData=true in UFC, targeting_key is raw and context.evaluation is populated."""

    def setup_ffe_evp_flagevaluation_observe_full_data_true(self) -> None:
        config_id = "ffe-evp-observe-true"
        self.flag_key = "evp-observe-true-flag"
        rc.tracer_rc_state.reset().set_config(
            f"{RC_PATH}/{config_id}/config",
            make_ufc_fixture(self.flag_key, observe_full_evaluation_data=True),
        ).apply()

        self.r = evaluate_flag(
            self.flag_key,
            targeting_key=PII_TARGETING_KEY,
            attributes=PII_ATTRIBUTES,
        )

    def test_ffe_evp_flagevaluation_observe_full_data_true(self) -> None:
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        wait_for_evp_flagevaluation_event(self.flag_key)
        events = find_evp_flagevaluation_events(self.flag_key)
        assert events, f"Expected EVP flagevaluation event for flag {self.flag_key}"

        for batch, event in events:
            assert_batch_context(batch)
            assert_event_contract(event, self.flag_key)

            targeting_key = event.get("targeting_key")
            assert targeting_key == PII_TARGETING_KEY, (
                f"Expected raw targeting_key {PII_TARGETING_KEY!r}, got {targeting_key!r}"
            )
            assert isinstance(targeting_key, str)
            assert not targeting_key.startswith("sha256_"), (
                f"unhashed targeting_key must not start with 'sha256_': {targeting_key!r}"
            )

            context = event.get("context")
            assert isinstance(context, dict), f"context must be an object when observeFullEvaluationData=true: {event}"
            evaluation_context = context.get("evaluation")
            assert isinstance(evaluation_context, dict), (
                f"context.evaluation must be an object when observeFullEvaluationData=true: {context}"
            )
            for key, expected_value in PII_ATTRIBUTES.items():
                assert key in evaluation_context, f"context.evaluation missing attribute {key!r}: {evaluation_context}"
                assert evaluation_context[key] == expected_value, (
                    f"context.evaluation[{key!r}] expected {expected_value!r}, got {evaluation_context[key]!r}"
                )

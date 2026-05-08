"""Test feature flags dynamic evaluation via Remote Config."""

import copy
import json
import uuid
from http import HTTPStatus

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)
from utils.proxy.mocked_response import StaticJsonMockedTracerResponse


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


# Simple UFC fixture for testing with doLog: true
UFC_FIXTURE_DATA = {
    "createdAt": "2024-04-17T19:40:53.716Z",
    "format": "SERVER",
    "environment": {"name": "Test"},
    "flags": {
        "test-flag": {
            "key": "test-flag",
            "enabled": True,
            "variationType": "STRING",
            "variations": {"on": {"key": "on", "value": "on"}, "off": {"key": "off", "value": "off"}},
            "allocations": [
                {
                    "key": "default-allocation",
                    "rules": [],
                    "splits": [{"variationKey": "on", "shards": []}],
                    "doLog": True,
                }
            ],
        }
    },
}


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_Unknown_Operator_Tolerance:
    """SDKs must ignore only the affected flag when a condition has an unknown operator.

    Two flags share the same UFC config:
    - ``operator-grease-flag``: has a condition with a GREASE operator — the whole
      flag must be ignored; the in-code default is returned.
    - ``valid-flag``: fully valid, no unknown operators — must still evaluate
      correctly, proving the bad flag did not poison config parsing.
    """

    @staticmethod
    def _build_config() -> dict:
        """UFC config with a GREASE operator in a condition.

        Two allocations:
        1. Rule with unknown operator — SDK must ignore the entire flag.
        2. Catch-all returning "on" — must NOT be reached.

        The catch-all distinguishes two wrong behaviours:
        - Falls through to catch-all (returns "on") — SDK only skipped the condition.
        - Raises / returns a variation anyway — SDK failed to handle unknown operator.
        Correct: whole flag ignored, in-code default ("default") returned.
        """
        grease_op = uuid.uuid4().hex  # 32 hex chars — cannot collide with any real operator
        return {
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "operator-grease-flag": {
                    "key": "operator-grease-flag",
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {
                        "trap": {"key": "trap", "value": "trap"},
                        "on": {"key": "on", "value": "on"},
                    },
                    "allocations": [
                        {
                            "key": "grease-allocation",
                            "rules": [
                                {
                                    "conditions": [
                                        {
                                            "attribute": "country",
                                            "operator": grease_op,
                                            "value": "anything",
                                        }
                                    ]
                                }
                            ],
                            "splits": [{"variationKey": "trap", "shards": []}],
                            "doLog": True,
                        },
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "on", "shards": []}],
                            "doLog": True,
                        },
                    ],
                },
                "valid-flag": {
                    "key": "valid-flag",
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {"expected": {"key": "expected", "value": "expected"}},
                    "allocations": [
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "expected", "shards": []}],
                            "doLog": True,
                        }
                    ],
                },
            },
        }

    def _setup(self):
        rc.tracer_rc_state.reset().apply()
        config = self._build_config()
        rc.tracer_rc_state.set_config(f"{RC_PATH}/ffe-unknown-operator/config", config).apply()

    def setup_unknown_operator_errors(self):
        self._setup()
        self.r_grease = weblog.post(
            "/ffe",
            json={
                "flag": "operator-grease-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"country": "US"},
            },
        )

    def test_unknown_operator_errors(self):
        assert self.r_grease.status_code == 200, f"Flag evaluation failed: {self.r_grease.text}"
        result = json.loads(self.r_grease.text)
        assert result["value"] == "default", (
            f"Unknown operator: expected in-code default 'default', got '{result['value']}' "
            f"(SDK must ignore the whole flag, not fall through to catch-all allocations)"
        )

    def setup_valid_flag_unaffected(self):
        self._setup()
        self.r_valid = weblog.post(
            "/ffe",
            json={
                "flag": "valid-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_valid_flag_unaffected(self):
        assert self.r_valid.status_code == 200, f"Valid flag evaluation failed: {self.r_valid.text}"
        result = json.loads(self.r_valid.text)
        assert result["value"] == "expected", (
            f"Valid flag corrupted by bad neighbour: expected 'expected', got '{result['value']}' "
            f"(unknown operator on one flag must not poison parsing of the whole config)"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_Flag_Parse_Error_Isolation:
    """A parse error in one flag must not prevent other flags from evaluating.

    Two flags share the same UFC config:
    - ``malformed-flag``: has a structurally invalid field (``allocations`` is a
      string instead of a list) — the SDK must skip this flag and return the
      in-code default.
    - ``valid-flag``: fully valid — must still evaluate correctly, proving the
      malformed flag did not abort parsing of the whole config.
    """

    @staticmethod
    def _build_config() -> dict:
        return {
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                "malformed-flag": {
                    "key": "malformed-flag",
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {"on": {"key": "on", "value": "on"}},
                    # allocations must be a list; a string is a deliberate parse error
                    "allocations": "this-is-not-a-list",
                },
                "valid-flag": {
                    "key": "valid-flag",
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {"expected": {"key": "expected", "value": "expected"}},
                    "allocations": [
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "expected", "shards": []}],
                            "doLog": True,
                        }
                    ],
                },
            },
        }

    def _setup(self):
        rc.tracer_rc_state.reset().apply()
        config = self._build_config()
        rc.tracer_rc_state.set_config(f"{RC_PATH}/ffe-flag-parse-error/config", config).apply()

    def setup_malformed_flag_returns_default(self):
        self._setup()
        self.r_malformed = weblog.post(
            "/ffe",
            json={
                "flag": "malformed-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_malformed_flag_returns_default(self):
        assert self.r_malformed.status_code == 200, f"Request failed: {self.r_malformed.text}"
        result = json.loads(self.r_malformed.text)
        assert result["value"] == "default", (
            f"Malformed flag: expected in-code default 'default', got '{result['value']}'"
        )

    def setup_valid_flag_unaffected(self):
        self._setup()
        self.r_valid = weblog.post(
            "/ffe",
            json={
                "flag": "valid-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_valid_flag_unaffected(self):
        assert self.r_valid.status_code == 200, f"Valid flag evaluation failed: {self.r_valid.text}"
        result = json.loads(self.r_valid.text)
        assert result["value"] == "expected", (
            f"Valid flag corrupted by malformed neighbour: expected 'expected', got '{result['value']}' "
            f"(parse error on one flag must not abort processing of the whole config)"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_Unknown_Fields_Tolerance:
    """SDKs must silently ignore unknown fields in the UFC configuration.

    Injects nonsensical unknown fields at every level of a valid UFC config
    (top-level, flag, variation, allocation, split) and verifies that flag
    evaluation still returns the correct value.
    """

    @staticmethod
    def _inject_unknown_fields(config: dict) -> dict:
        """Inject random unknown fields at every *fixed-schema* level of a UFC config.

        Skips map-keyed levels (``flags``, ``variations``) because their keys carry
        semantic meaning; injecting there would create phantom flags/variations.
        Targets: top-level config, environment, flag objects, variation objects,
        allocation objects, rule objects, condition objects, split objects,
        shard objects, and range objects.

        Field names are raw UUID hex (RFC 8701 GREASE style) — no recognisable
        prefix, so SDKs cannot pattern-match or special-case them.
        """
        config = copy.deepcopy(config)

        def g() -> str:
            return uuid.uuid4().hex

        # Top-level config object
        config[g()] = "unknown-top-level-string"
        config[g()] = 0
        config[g()] = None

        # environment object
        env = config.get("environment")
        if isinstance(env, dict):
            env[g()] = "unknown-env-field"

        # flags is a map (flag key → flag object) — iterate values only
        for flag_obj in config.get("flags", {}).values():
            flag_obj[g()] = "unknown-flag-field"
            flag_obj[g()] = False

            # variations is a map (variation key → variation object) — iterate values only
            for var_obj in flag_obj.get("variations", {}).values():
                var_obj[g()] = "unknown-variation-field"

            for alloc in flag_obj.get("allocations", []):
                alloc[g()] = "unknown-allocation-field"
                alloc[g()] = []

                for rule in alloc.get("rules", []):
                    rule[g()] = "unknown-rule-field"

                    for condition in rule.get("conditions", []):
                        condition[g()] = "unknown-condition-field"

                for split in alloc.get("splits", []):
                    split[g()] = "unknown-split-field"

                    for shard in split.get("shards", []):
                        shard[g()] = "unknown-shard-field"

                        for range_obj in shard.get("ranges", []):
                            range_obj[g()] = "unknown-range-field"

        return config

    def setup_unknown_fields_are_ignored(self):
        rc.tracer_rc_state.reset().apply()

        poisoned_config = self._inject_unknown_fields(UFC_FIXTURE_DATA)
        rc.tracer_rc_state.set_config(f"{RC_PATH}/ffe-unknown-fields/config", poisoned_config).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": "test-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_unknown_fields_are_ignored(self):
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"
        result = json.loads(self.r.text)
        assert result["value"] == "on", f"Unknown fields corrupted evaluation: expected 'on', got '{result['value']}'"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Unavailable:
    """Test FFE SDK resilience when the Remote Configuration service becomes unavailable.

    This test validates that the local flag configuration cache inside the tracer
    can continue to perform evaluations even when RC returns errors.
    """

    def setup_ffe_rc_unavailable_graceful_degradation(self):
        """Set up FFE with valid config, then simulate RC unavailability and verify cached config still works."""
        self.config_request_data = None

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == "/v0.7/config" and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        rc.tracer_rc_state.reset().apply()

        self.flag_key = "test-flag"  # From UFC_FIXTURE_DATA, returns "on"
        self.not_delivered_flag_key = "test-flag-not-delivered"
        self.default_value = "default_fallback"

        self.config_state = rc.tracer_rc_state.set_config(f"{RC_PATH}/ffe-test/config", UFC_FIXTURE_DATA).apply()

        # Baseline: evaluate flag with RC working
        self.baseline_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

        # Simulate RC unavailability by returning 503 errors
        StaticJsonMockedTracerResponse(
            path="/v0.7/config", mocked_json={"error": "Service Unavailable"}, status_code=503
        ).send()

        # Wait for tracer to receive 503 from RC before evaluating flag
        interfaces.library.wait_for(wait_for_config_503, timeout=60)

        # Evaluate cached flag while RC is unavailable
        self.cached_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-2",
                "attributes": {},
            },
        )

        # Evaluate a flag that was not delivered via RC
        self.not_delivered_eval = weblog.post(
            "/ffe",
            json={
                "flag": self.not_delivered_flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-3",
                "attributes": {},
            },
        )

        # Restore normal RC behavior (empty response)
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()

    def test_ffe_rc_unavailable_graceful_degradation(self):
        """Test that cached flag configs continue working when RC is unavailable."""
        # Verify tracer received 503 from RC
        assert self.config_request_data is not None, "No /v0.7/config request was captured"
        assert self.config_request_data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE, (
            f"Expected 503, got {self.config_request_data['response']['status_code']}"
        )

        expected_value = "on"

        assert self.baseline_eval.status_code == 200, f"Baseline request failed: {self.baseline_eval.text}"
        assert self.cached_eval.status_code == 200, f"Cached eval request failed: {self.cached_eval.text}"
        assert self.not_delivered_eval.status_code == 200, f"Not delivered eval failed: {self.not_delivered_eval.text}"

        baseline_result = json.loads(self.baseline_eval.text)
        assert baseline_result["value"] == expected_value, (
            f"Baseline: expected '{expected_value}', got '{baseline_result['value']}'"
        )

        cached_result = json.loads(self.cached_eval.text)
        assert cached_result["value"] == expected_value, (
            f"Cached eval during RC outage: expected '{expected_value}' from cache, got '{cached_result['value']}'"
        )

        not_delivered_result = json.loads(self.not_delivered_eval.text)
        assert not_delivered_result["value"] == self.default_value, (
            f"Not delivered flag: expected default '{self.default_value}', got '{not_delivered_result['value']}'"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Down_From_Start:
    """Test FFE behavior when RC is unavailable from application start."""

    def setup_ffe_rc_down_from_start(self):
        """Simulate RC being down from the start - no config ever delivered."""
        self.config_request_data = None

        def wait_for_config_503(data: dict) -> bool:
            if data["path"] == "/v0.7/config" and data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE:
                self.config_request_data = data
                return True
            return False

        StaticJsonMockedTracerResponse(
            path="/v0.7/config", mocked_json={"error": "Service Unavailable"}, status_code=503
        ).send()

        # Wait for tracer to receive 503 from RC before evaluating flag
        interfaces.library.wait_for(wait_for_config_503, timeout=60)

        self.flag_key = "test-flag-never-delivered"
        self.default_value = "my-default-value"

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-rc-down",
                "attributes": {},
            },
        )

        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()

    def test_ffe_rc_down_from_start(self):
        """Test that default value is returned when RC is down from start."""
        # Verify tracer received 503 from RC
        assert self.config_request_data is not None, "No /v0.7/config request was captured"
        assert self.config_request_data["response"]["status_code"] == HTTPStatus.SERVICE_UNAVAILABLE, (
            f"Expected 503, got {self.config_request_data['response']['status_code']}"
        )

        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        result = json.loads(self.r.text)
        assert result["value"] == self.default_value, (
            f"Expected default '{self.default_value}', got '{result['value']}'"
        )

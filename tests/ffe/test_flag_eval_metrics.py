"""Test feature flag evaluation metrics via OTel Metrics API."""

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


def make_ufc_fixture(flag_key: str, variant_key: str = "on", variation_type: str = "STRING", *, enabled: bool = True):
    """Create a UFC fixture with the given flag configuration."""
    values: dict[str, dict[str, str | bool | float | int]] = {
        "STRING": {"on": "on-value", "off": "off-value"},
        "BOOLEAN": {"on": True, "off": False},
        "NUMERIC": {"on": 1.5, "off": 0.0},  # Decimal value for type_mismatch testing (NUMERIC→INTEGER)
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


def find_eval_metrics(flag_key: str | None = None):
    """Find feature_flag.evaluations metrics in agent data.

    Returns a list of metric points matching the metric name, optionally filtered by flag key tag.
    """
    results = []
    for _, point in interfaces.agent.get_metrics():
        if point.get("metric") != "feature_flag.evaluations":
            continue

        tags = point.get("tags", [])
        if flag_key is not None:
            tag_match = any(t == f"feature_flag.key:{flag_key}" for t in tags)
            if not tag_match:
                continue

        results.append(point)
    return results


def get_tag_value(tags: list[str], key: str):
    """Extract a tag value from a list of 'key:value' strings."""
    prefix = f"{key}:"
    for tag in tags:
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return None


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Basic:
    """Test that a flag evaluation produces a feature_flag.evaluations metric."""

    def setup_ffe_eval_metric_basic(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-basic"
        self.flag_key = "eval-metric-basic-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_metric_basic(self):
        """Test that flag evaluation produces a metric with correct tags."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected at least one feature_flag.evaluations metric for flag '{self.flag_key}', "
            f"but found none. All eval metrics: {find_eval_metrics()}"
        )

        # Verify tags on the first matching metric point
        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.key") == self.flag_key, (
            f"Expected tag feature_flag.key:{self.flag_key}, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", (
            f"Expected tag feature_flag.result.variant:on, got tags: {tags}"
        )
        # TODO(FFL-2064): align evaluation reasons across SDKs
        # assert get_tag_value(tags, "feature_flag.result.reason") == "static", (
        #     f"Expected tag feature_flag.result.reason:static, got tags: {tags}"
        # )
        assert get_tag_value(tags, "feature_flag.result.allocation_key") == "default-allocation", (
            f"Expected tag feature_flag.result.allocation_key:default-allocation, got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Count:
    """Test that multiple evaluations of the same flag produce correct metric count."""

    def setup_ffe_eval_metric_count(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-count"
        self.flag_key = "eval-metric-count-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.eval_count = 5
        self.responses = []
        for _ in range(self.eval_count):
            r = weblog.post(
                "/ffe",
                json={
                    "flag": self.flag_key,
                    "variationType": "STRING",
                    "defaultValue": "default",
                    "targetingKey": "user-1",
                    "attributes": {},
                },
            )
            self.responses.append(r)

    def test_ffe_eval_metric_count(self):
        """Test that N evaluations produce metric count = N."""
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected at least one feature_flag.evaluations metric for flag '{self.flag_key}', but found none."
        )

        # Sum all data points for this flag (agent may split across multiple series entries)
        total_count = 0
        for point in metrics:
            points = point.get("points", [])
            for p in points:
                # points format: {"value": N, "timestamp": "..."} (v2 series API)
                if isinstance(p, dict):
                    total_count += p.get("value", 0)
                elif isinstance(p, list) and len(p) >= 2:
                    total_count += p[1]

        assert total_count >= self.eval_count, f"Expected metric count >= {self.eval_count}, got {total_count}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Different_Flags:
    """Test that different flags produce separate metric series."""

    def setup_ffe_eval_metric_different_flags(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-diff"
        self.flag_a = "eval-metric-flag-a"
        self.flag_b = "eval-metric-flag-b"

        # Create config with both flags
        fixture = {
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                self.flag_a: {
                    "key": self.flag_a,
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {
                        "on": {"key": "on", "value": "on-value"},
                        "off": {"key": "off", "value": "off-value"},
                    },
                    "allocations": [
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "on", "shards": []}],
                            "doLog": True,
                        }
                    ],
                },
                self.flag_b: {
                    "key": self.flag_b,
                    "enabled": True,
                    "variationType": "STRING",
                    "variations": {
                        "on": {"key": "on", "value": "on-value"},
                        "off": {"key": "off", "value": "off-value"},
                    },
                    "allocations": [
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "on", "shards": []}],
                            "doLog": True,
                        }
                    ],
                },
            },
        }
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", fixture).apply()

        self.r_a = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_a,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )
        self.r_b = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_b,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_metric_different_flags(self):
        """Test that each flag key gets its own metric series."""
        assert self.r_a.status_code == 200, f"Flag A evaluation failed: {self.r_a.text}"
        assert self.r_b.status_code == 200, f"Flag B evaluation failed: {self.r_b.text}"

        metrics_a = find_eval_metrics(self.flag_a)
        metrics_b = find_eval_metrics(self.flag_b)

        assert len(metrics_a) > 0, f"Expected metric for flag '{self.flag_a}', found none. All: {find_eval_metrics()}"
        assert len(metrics_b) > 0, f"Expected metric for flag '{self.flag_b}', found none. All: {find_eval_metrics()}"


# =============================================================================
# Reason Tests
#
# OpenFeature defines several resolution reasons. Test coverage:
#
#   Reason           | Test                              | Scenario
#   -----------------|-----------------------------------|----------------------------------
#   STATIC           | Test_FFE_Eval_Metric_Basic        | No rules, no shards (catch-all)
#   TARGETING_MATCH  | Test_FFE_Eval_Reason_Targeting    | Rules match the context
#   SPLIT            | Test_FFE_Eval_Reason_Split        | Shards determine variant
#   DEFAULT          | Test_FFE_Eval_Reason_Default      | Rules don't match, fallback used
#   DISABLED         | Test_FFE_Eval_Reason_Disabled     | Flag is disabled
#
# =============================================================================


def make_targeting_fixture(flag_key: str, attribute: str, match_value: str):
    """Create a UFC fixture with a targeting rule."""
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
                                "conditions": [
                                    {
                                        "operator": "ONE_OF",
                                        "attribute": attribute,
                                        "value": [match_value],
                                    }
                                ]
                            }
                        ],
                        "splits": [{"variationKey": "on", "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def make_split_fixture(flag_key: str):
    """Create a UFC fixture with shards for percentage-based rollout (50/50 split)."""
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
                        "key": "split-allocation",
                        "rules": [],
                        "splits": [
                            {
                                "variationKey": "on",
                                "shards": [
                                    {
                                        "salt": "test-salt",
                                        "totalShards": 10000,
                                        "ranges": [{"start": 0, "end": 5000}],
                                    }
                                ],
                            },
                            {
                                "variationKey": "off",
                                "shards": [
                                    {
                                        "salt": "test-salt",
                                        "totalShards": 10000,
                                        "ranges": [{"start": 5000, "end": 10000}],
                                    }
                                ],
                            },
                        ],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def make_invalid_regex_fixture(flag_key: str, invalid_regex: str = "[invalid"):
    """Create a UFC fixture with an invalid regex pattern in a MATCHES condition.

    This tests the PARSE_ERROR scenario where the configuration contains
    a syntactically invalid regex pattern that fails during evaluation.
    """
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
                        "key": "regex-allocation",
                        "rules": [
                            {
                                "conditions": [
                                    {
                                        "operator": "MATCHES",
                                        "attribute": "email",
                                        "value": invalid_regex,  # Invalid regex pattern
                                    }
                                ]
                            }
                        ],
                        "splits": [{"variationKey": "on", "shards": []}],
                        "doLog": True,
                    }
                ],
            }
        },
    }


def make_variant_type_mismatch_fixture(flag_key: str):
    """Create a UFC fixture where the variant value doesn't match the declared type.

    This tests the PARSE_ERROR scenario where the configuration declares a flag type
    (e.g., INTEGER) but the variant value is incompatible (e.g., a string).
    This is a configuration error, not a runtime type conversion error.
    """
    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {
            flag_key: {
                "key": flag_key,
                "enabled": True,
                "variationType": "INTEGER",  # Declared as INTEGER
                "variations": {
                    "on": {"key": "on", "value": "not-an-integer"},  # But value is a string!
                    "off": {"key": "off", "value": 0},
                },
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
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Reason_Targeting:
    """Test that matching targeting rules produce reason=targeting_match."""

    def setup_ffe_eval_reason_targeting(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-reason-targeting"
        self.flag_key = "reason-targeting-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_targeting_fixture(self.flag_key, "tier", "premium")
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"tier": "premium"},  # Matches the targeting rule
            },
        )

    def test_ffe_eval_reason_targeting(self):
        """Test that targeting rule match produces reason=targeting_match."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"Expected reason 'targeting_match', got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", f"Expected variant 'on', got tags: {tags}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Reason_Split:
    """Test that shard-based allocation produces reason=split."""

    def setup_ffe_eval_reason_split(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-reason-split"
        self.flag_key = "reason-split-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_split_fixture(self.flag_key)).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_reason_split(self):
        """Test that shard-based evaluation produces reason=split."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "split", (
            f"Expected reason 'split', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Reason_Default:
    """Test that unmatched targeting rules produce reason=default."""

    def setup_ffe_eval_reason_default(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-reason-default"
        self.flag_key = "reason-default-flag"
        # Flag requires tier=premium, but we'll send tier=basic
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_targeting_fixture(self.flag_key, "tier", "premium")
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"tier": "basic"},  # Does NOT match the targeting rule
            },
        )

    def test_ffe_eval_reason_default(self):
        """Test that unmatched rules produce reason=default."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"Expected reason 'default', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Reason_Disabled:
    """Test that a disabled flag produces reason=disabled."""

    def setup_ffe_eval_reason_disabled(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-reason-disabled"
        self.flag_key = "reason-disabled-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, enabled=False)
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_reason_disabled(self):
        """Test that disabled flag produces reason=disabled."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "disabled", (
            f"Expected reason 'disabled', got tags: {tags}"
        )


# =============================================================================
# Error Code Tests
#
# OpenFeature defines 8 error codes. Test coverage:
#
#   Error Code             | Test
#   -----------------------|---------------------------------------------
#   FLAG_NOT_FOUND         | Test_FFE_Eval_Config_Exists_Flag_Missing
#   TYPE_MISMATCH          | Test_FFE_Eval_Metric_Type_Mismatch, Test_FFE_Eval_Metric_Numeric_To_Integer
#   PARSE_ERROR            | Test_FFE_Eval_Metric_Parse_Error
#   GENERAL                | (not tested - catch-all error code)
#   TARGETING_KEY_MISSING  | Test_FFE_Eval_Targeting_Key_Optional (verifies it's NOT returned; JS excluded)
#   INVALID_CONTEXT        | (not tested - per OF.3, nested attrs should be ignored, not error)
#   PROVIDER_NOT_READY     | Test_FFE_Eval_No_Config_Loaded
#   PROVIDER_FATAL         | (not tested - requires fatal provider error)
#
# Note on INVALID_CONTEXT and nested attributes:
#   Per FFE SDK requirements (OF.3): "Evaluation of nested attributes (arrays and maps)
#   is currently not defined. SDKs must ignore such attributes. Passing nested
#   attributes must not raise an error."
#
#   Therefore, Test_FFE_Eval_Nested_Attributes_Ignored verifies that nested attributes
#   do NOT produce INVALID_CONTEXT error - they should be silently ignored.
#
# =============================================================================


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Config_Exists_Flag_Missing:
    """Test error metrics when config exists but requested flag is missing.

    This is distinct from Test_FFE_Eval_No_Config_Loaded:
    - Here: Config IS loaded, but the specific flag doesn't exist → error.type=flag_not_found
    - There: No config loaded at all → error.type=general

    Both should return reason=error, but with different error.type values.
    """

    def setup_ffe_eval_config_exists_flag_missing(self):
        rc.tracer_rc_state.reset().apply()

        # Set up config with a different flag than what we'll request
        config_id = "ffe-eval-metric-error"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture("some-other-flag")).apply()

        self.flag_key = "non-existent-eval-metric-flag"
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_config_exists_flag_missing(self):
        """Test that missing flag (with config loaded) produces error.type=flag_not_found."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected metric for non-existent flag '{self.flag_key}', found none. All: {find_eval_metrics()}"
        )

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error', got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "flag_not_found", (
            f"Expected error.type 'flag_not_found', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Type_Mismatch:
    """Test that requesting the wrong type produces a metric with type_mismatch error.

    This configures a STRING flag but evaluates it as BOOLEAN.  The type
    conversion error happens *after* the core evaluate() returns, inside the
    type-specific method (BooleanEvaluation).  Recording metrics via a
    Finally hook catches this; the old evaluate()-level defer would have
    recorded a success (targeting_match) instead.
    """

    def setup_ffe_eval_metric_type_mismatch(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-type-mismatch"
        self.flag_key = "eval-metric-type-mismatch-flag"
        # Flag is configured as STRING
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, variation_type="STRING")
        ).apply()

        # But we evaluate it as BOOLEAN → type mismatch
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_metric_type_mismatch(self):
        """Test that type conversion errors produce metric with error.type:type_mismatch."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' for type mismatch, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "type_mismatch", (
            f"Expected error.type 'type_mismatch', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Numeric_To_Integer:
    """Test that evaluating a NUMERIC flag as INTEGER produces type_mismatch error.

    This configures a NUMERIC flag with a decimal value (1.5) but evaluates it as INTEGER.
    Since NUMERIC and INTEGER are different types, this produces a type_mismatch error.
    """

    def setup_ffe_eval_metric_numeric_to_integer(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-numeric-to-int"
        self.flag_key = "eval-metric-numeric-to-int-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key, variation_type="NUMERIC")
        ).apply()

        # Evaluate NUMERIC flag as INTEGER → type mismatch
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "INTEGER",
                "defaultValue": 0,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_metric_numeric_to_integer(self):
        """Test that NUMERIC-to-INTEGER evaluation produces error.type:type_mismatch."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' for type mismatch, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "type_mismatch", (
            f"Expected error.type 'type_mismatch', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Parse_Error_Invalid_Regex:
    """Test that an invalid regex pattern produces error.type=parse_error.

    This configures a flag with a MATCHES condition containing an invalid regex pattern
    (e.g., "[invalid" which has an unclosed bracket). When the condition is evaluated,
    the regex compilation fails and produces a parse_error.

    Behavioral differences across SDKs:
    - Python (libdatadog): Returns parse_error during evaluation
    - Go: Validates regex at config load time, rejects config with invalid regex
    """

    def setup_ffe_eval_metric_parse_error_invalid_regex(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-metric-parse-error"
        self.flag_key = "eval-metric-parse-error-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_invalid_regex_fixture(self.flag_key)
        ).apply()

        # Evaluate the flag with an attribute that triggers the invalid regex condition
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"email": "test@example.com"},  # Triggers MATCHES condition
            },
        )

    def test_ffe_eval_metric_parse_error_invalid_regex(self):
        """Test that invalid regex produces error.type:parse_error."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' for parse error, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "parse_error", (
            f"Expected error.type 'parse_error', got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Metric_Parse_Error_Variant_Type_Mismatch:
    """Test that a variant value not matching declared flag type produces parse_error.

    This configures a flag as INTEGER type but gives the variant a string value.
    When the configuration is validated during evaluation, this type mismatch
    produces a parse_error (configuration is invalid).

    This is different from Test_FFE_Eval_Metric_Type_Mismatch which tests
    runtime type conversion (e.g., evaluating a STRING flag as BOOLEAN).
    This test validates that configuration errors are properly detected.
    """

    def setup_ffe_eval_metric_parse_error_variant_type_mismatch(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-eval-variant-type-mismatch"
        self.flag_key = "eval-variant-type-mismatch-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_variant_type_mismatch_fixture(self.flag_key)
        ).apply()

        # Evaluate the flag - the variant value doesn't match the declared type
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "INTEGER",
                "defaultValue": 0,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_metric_parse_error_variant_type_mismatch(self):
        """Test that variant type mismatch produces error.type:parse_error."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' for variant type mismatch, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "parse_error", (
            f"Expected error.type 'parse_error' for variant type mismatch, got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_No_Config_Loaded:
    """Test that evaluating a flag when no configuration is loaded produces error metrics.

    When no FFE configuration has been loaded, tracers should return:
    - feature_flag.result.reason = "error"
    - error.type = "provider_not_ready"
    """

    def setup_ffe_eval_no_config_loaded(self):
        # Reset RC state and do NOT load any configuration
        rc.tracer_rc_state.reset().apply()

        # Evaluate a flag without any config loaded
        self.flag_key = "no-config-flag"
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_eval_no_config_loaded(self):
        """Test that no config loaded produces reason=error and error.type=provider_not_ready.

        This ensures cross-tracer consistency for the 'no config loaded' scenario.
        """
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected metric for flag '{self.flag_key}' with no config, found none. All: {find_eval_metrics()}"
        )

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' when no config loaded, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "provider_not_ready", (
            f"Expected error.type 'provider_not_ready' when no config loaded, got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Targeting_Key_Optional:
    """Test that flag evaluation succeeds without a targeting key.

    The OpenFeature spec defines TARGETING_KEY_MISSING as an error code, but the
    targeting key is optional in the spec. Most Datadog providers do not require
    a targeting key for flag evaluation:

    - Evaluations without sharding work without a targeting key
    - Only shard-based allocations need a targeting key (and they simply won't match)

    Behavioral differences:
    - Python, Go, Ruby, Java, .NET: Targeting key is optional, evaluation succeeds
    - JS: Requires targeting key, returns TARGETING_KEY_MISSING error

    This test verifies that evaluation succeeds without a targeting key for most SDKs.
    """

    def setup_ffe_eval_targeting_key_optional(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-targeting-key-optional"
        self.flag_key = "targeting-key-optional-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        # Evaluate without a targeting key - should still succeed for most SDKs
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "",  # Empty targeting key
                "attributes": {},
            },
        )

    def test_ffe_eval_targeting_key_optional(self):
        """Test that evaluation succeeds without targeting key (no TARGETING_KEY_MISSING error)."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        # Should NOT be an error - targeting key is optional
        reason = get_tag_value(tags, "feature_flag.result.reason")
        assert reason != "error", f"Expected successful evaluation without targeting key, but got error. Tags: {tags}"

        # Should not have TARGETING_KEY_MISSING error
        error_type = get_tag_value(tags, "error.type")
        assert error_type != "targeting_key_missing", (
            f"Got TARGETING_KEY_MISSING error but targeting key should be optional. Tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Nested_Attributes_Ignored:
    """Test that nested attributes are ignored without raising an error (OF.3).

    Per FFE SDK requirements (OF.3):
    "Evaluation of nested attributes (arrays and maps) is currently not defined.
    SDKs must ignore such attributes. Passing nested attributes must not raise an error."

    This test verifies that passing nested attributes:
    1. Does NOT produce an error (no INVALID_CONTEXT)
    2. Evaluation proceeds normally with nested attributes ignored

    SDK compliance status:
    - Ruby: Compliant (silently filters nested attributes in C extension)
    - Python: Non-compliant (returns INVALID_CONTEXT) - tracked in FFL-1980
    - Go: Non-compliant (transforms to dot notation) - tracked in FFL-1980
    - Java, .NET, JS: TBD
    """

    def setup_ffe_eval_nested_attributes_ignored(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-nested-attrs"
        self.flag_key = "nested-attrs-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        # Pass a nested dict as an attribute value - this should be IGNORED, not error
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"nested": {"inner": "value"}, "flat": "value"},  # Nested dict should be ignored
            },
        )

    def test_ffe_eval_nested_attributes_ignored(self):
        """Test that nested attributes are ignored and evaluation succeeds (OF.3)."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        # Per OF.3: Passing nested attributes must NOT raise an error
        reason = get_tag_value(tags, "feature_flag.result.reason")
        assert reason != "error", (
            f"Expected successful evaluation (nested attrs should be ignored per OF.3), but got error. Tags: {tags}"
        )

        # Should not have INVALID_CONTEXT error
        error_type = get_tag_value(tags, "error.type")
        assert error_type is None or error_type != "invalid_context", (
            f"Got INVALID_CONTEXT error but nested attributes should be ignored per OF.3. Tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_Eval_Lowercase_Consistency:
    """Test that all metric tag values are lowercase.

    OpenFeature telemetry conventions require lowercase values for reason and error codes.
    This test ensures tracers emit lowercase values without relying on fallback logic.
    """

    def setup_ffe_lowercase_reason(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-lowercase-test"
        self.flag_key = "lowercase-test-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_lowercase_reason(self):
        """Test that reason values are lowercase."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.flag_key}', found none."

        for point in metrics:
            tags = point.get("tags", [])
            reason = get_tag_value(tags, "feature_flag.result.reason")
            if reason:
                assert reason == reason.lower(), f"Reason '{reason}' is not lowercase. Tags: {tags}"

    def setup_ffe_lowercase_error_type(self):
        rc.tracer_rc_state.reset().apply()

        # Set up config with a different flag than what we'll request
        config_id = "ffe-lowercase-error-test"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture("some-other-flag")).apply()

        # Request non-existent flag to trigger error
        self.error_flag_key = "lowercase-error-flag"
        self.r_error = weblog.post(
            "/ffe",
            json={
                "flag": self.error_flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_lowercase_error_type(self):
        """Test that error.type values are lowercase."""
        assert self.r_error.status_code == 200, f"Flag evaluation request failed: {self.r_error.text}"

        metrics = find_eval_metrics(self.error_flag_key)
        assert len(metrics) > 0, f"Expected metric for flag '{self.error_flag_key}', found none."

        for point in metrics:
            tags = point.get("tags", [])
            error_type = get_tag_value(tags, "error.type")
            if error_type:
                assert error_type == error_type.lower(), f"Error type '{error_type}' is not lowercase. Tags: {tags}"

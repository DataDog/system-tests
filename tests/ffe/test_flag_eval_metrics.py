"""Test feature flag evaluation metrics via OTel Metrics API."""

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
    context,
    irrelevant,
)


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


def make_ufc_fixture(flag_key: str, variant_key: str = "on", variation_type: str = "STRING", *, enabled: bool = True):
    """Create a UFC fixture with the given flag configuration."""
    values: dict[str, dict[str, str | bool | float | int]] = {
        "STRING": {"on": "on-value", "off": "off-value"},
        "BOOLEAN": {"on": True, "off": False},
        "NUMERIC": {"on": 1.5, "off": 0.0},  # Decimal value for parse_error testing
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
        assert get_tag_value(tags, "feature_flag.result.reason") == "static", (
            f"Expected tag feature_flag.result.reason:static, got tags: {tags}"
        )
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
#   PARSE_ERROR            | (not tested - no cross-SDK consistent scenario)
#   GENERAL                | (not tested - catch-all error code)
#   TARGETING_KEY_MISSING  | Test_FFE_Eval_Targeting_Key_Optional (verifies it's NOT returned; JS excluded)
#   INVALID_CONTEXT        | Test_FFE_Eval_Invalid_Context_Nested_Attribute (Python only)
#   PROVIDER_NOT_READY     | Test_FFE_Eval_No_Config_Loaded
#   PROVIDER_FATAL         | (not tested - requires fatal provider error)
#
# INVALID_CONTEXT behavioral differences:
#   - Python: Returns for nested dict/list attributes (PyO3 conversion failure)
#   - Go: Flattens nested objects to dot notation instead
#   - Ruby: Silently skips unsupported attribute types
#   - Java: Returns only for null context, not nested attributes
#   - .NET: Relies on native library; not yet standardized
#   - JS: Does not use INVALID_CONTEXT at all
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
@irrelevant(
    context.library == "nodejs", reason="JS SDK requires targeting key and returns TARGETING_KEY_MISSING when missing"
)
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
@irrelevant(
    context.library == "golang",
    reason="Go flattens nested attributes to dot notation instead of returning INVALID_CONTEXT",
)
@irrelevant(
    context.library == "ruby",
    reason="Ruby silently skips unsupported attribute types instead of returning INVALID_CONTEXT",
)
@irrelevant(
    context.library == "java", reason="Java uses INVALID_CONTEXT only for null context, not for nested attributes"
)
@irrelevant(
    context.library == "dotnet", reason=".NET INVALID_CONTEXT behavior for nested attributes is not yet standardized"
)
@irrelevant(context.library == "nodejs", reason="JS SDK does not use INVALID_CONTEXT error code")
class Test_FFE_Eval_Invalid_Context_Nested_Attribute:
    """Test that nested/unsupported attribute types produce error.type=invalid_context.

    The datadog-ffe native library (used by Python) only supports primitive attribute types:
    str, int, float, bool, and None. Nested objects (dicts) and lists are NOT
    supported and will trigger an INVALID_CONTEXT error.

    Behavioral differences across SDKs for nested attributes:
    - Python: Returns INVALID_CONTEXT (PyO3 conversion failure)
    - Go: Flattens to dot notation (e.g., {"a": {"b": 1}} → {"a.b": 1})
    - Ruby: Silently skips unsupported attribute types
    - Java: Uses INVALID_CONTEXT only for null context, not nested attributes
    - .NET: Relies on native library; behavior not yet standardized
    - JS: Does not use INVALID_CONTEXT at all

    This test currently only runs for Python.
    """

    def setup_ffe_eval_invalid_context_nested_attribute(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-invalid-context"
        self.flag_key = "invalid-context-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_ufc_fixture(self.flag_key)).apply()

        # Pass a nested dict as an attribute value - this should trigger INVALID_CONTEXT
        # The native library only supports: str, int, float, bool, None
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"nested": {"inner": "value"}},  # Nested dict - not supported
            },
        )

    def test_ffe_eval_invalid_context_nested_attribute(self):
        """Test that nested attribute values produce error.type=invalid_context."""
        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected metric for flag '{self.flag_key}' with invalid context, found none. All: {find_eval_metrics()}"
        )

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"Expected reason 'error' for invalid context, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "invalid_context", (
            f"Expected error.type 'invalid_context' for nested attribute, got tags: {tags}"
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

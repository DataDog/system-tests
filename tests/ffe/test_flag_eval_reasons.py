"""Tests for FFE evaluation reasons and error codes per Appendix B of the RFC.

Reference: Feature Flag Evaluation Reasons and Error Codes RFC, Appendix B
https://datadoghq.atlassian.net/...

Appendix B defines 26 test cases covering all valid (return value type, reason, error code)
combinations. This file covers the cases not already exercised in test_flag_eval_metrics.py.

Coverage map (B-N = Appendix B row N):
  REASON-1  PROVIDER_NOT_READY        → test_flag_eval_metrics.py :: Test_FFE_Eval_No_Config_Loaded
  REASON-2  PROVIDER_FATAL            → Test_FFE_REASON_2_ProviderFatal (below)
  REASON-3  FLAG_NOT_FOUND (missing)  → test_flag_eval_metrics.py :: Test_FFE_Eval_Config_Exists_Flag_Missing
  REASON-3  FLAG_NOT_FOUND (disabled) → Test_FFE_REASON_3_DisabledFlagNotFound (below)
  REASON-4  TYPE_MISMATCH             → test_flag_eval_metrics.py :: Test_FFE_Eval_Metric_Type_Mismatch
  REASON-5  PARSE_ERROR               → not testable via RC mock (see notes at bottom)
  REASON-6  GENERAL                   → not testable (see notes at bottom)
  REASON-7  TARGETING_KEY_MISSING     → Test_FFE_REASON_7_TargetingKeyMissing
  REASON-8  TARGETING_MATCH (no key)  → Test_FFE_REASON_8_RuleOnlyNoKey
  REASON-9  zero allocations → DEFAULT → Test_FFE_REASON_9_ZeroAllocations
  REASON-10 no-default-alloc → DEFAULT → Test_FFE_REASON_10_NoDefaultAlloc
  REASON-11 STATIC (no split/rules)   → Test_FFE_REASON_11_StaticNoSplit (uses vacuous split in UFC,
                                     structurally same as REASON-12; see fixture docstring)
  REASON-12 STATIC (vacuous split)    → test_flag_eval_metrics.py :: Test_FFE_Eval_Metric_Basic
  REASON-13 TARGETING_MATCH multi     → Test_FFE_REASON_13_MultiAllocRuleMatch
  REASON-14 DEFAULT multi (rule fails) → Test_FFE_REASON_14_MultiAllocRuleFail
  REASON-15 SPLIT (non-vacuous)       → test_flag_eval_metrics.py :: Test_FFE_Eval_Reason_Split
  REASON-16 DEFAULT (rule+shard, miss) → Test_FFE_REASON_16_RulePassShardMiss
  REASON-17 SPLIT (rule+shard, both)  → Test_FFE_REASON_17_RulePassShardWin
  REASON-18 DEFAULT (rule+shard, rule fails) → Test_FFE_REASON_18_RuleFail
  REASON-19 TARGETING_MATCH after miss → Test_FFE_REASON_19_SplitMissRuleMatch
  REASON-20 DEFAULT after split miss  → Test_FFE_REASON_20_SplitMissDefault
  REASON-21 DEFAULT (active window, single) → Test_FFE_REASON_21_ActiveWindowSingle
  REASON-22 DEFAULT (inactive window) → Test_FFE_REASON_22_InactiveWindowSingle
  REASON-23 DEFAULT (active window, multi) → Test_FFE_REASON_23_ActiveWindowMulti
  REASON-24 DEFAULT (inactive window, multi) → Test_FFE_REASON_24_InactiveWindowMulti
  REASON-25 TARGETING_MATCH (window+rules) → Test_FFE_REASON_25_WindowActiveRuleMatch
  REASON-26 DEFAULT (window+rules, fail) → Test_FFE_REASON_26_WindowRuleFail
"""

from typing import Any

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

# ---------------------------------------------------------------------------
# Shard helpers
# ---------------------------------------------------------------------------
# 100% shard: always buckets the subject. A non-empty shard spec always triggers
# hash computation, so a targeting key is required to use this constant.
SHARD_ALWAYS_HIT = [{"salt": "rfc-salt", "totalShards": 10000, "ranges": [{"start": 0, "end": 10000}]}]
# 0% shard: guaranteed miss — the shard entry is present (salt + totalShards), so the
# SDK still computes the hash (targeting key required), but the empty ranges list means
# no subject falls in any bucket. Distinct from shards:[] (vacuous split, no hash at all).
SHARD_ALWAYS_MISS = [{"salt": "rfc-salt", "totalShards": 10000, "ranges": []}]

# Date windows
WINDOW_ACTIVE_START = "2020-01-01T00:00:00Z"
WINDOW_ACTIVE_END = "2099-01-01T00:00:00Z"
WINDOW_INACTIVE_START = "2020-01-01T00:00:00Z"
WINDOW_INACTIVE_END = "2020-12-31T00:00:00Z"

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
# These are intentionally duplicated from test_flag_eval_metrics.py rather than
# imported. Cross-module imports between test files are fragile: selective test
# runs and different collection roots can cause ImportError at setup time, which
# per the project guidelines must never happen in setup methods. The functions
# are small enough that duplication is the lesser risk.


def find_eval_metrics(flag_key: str | None = None) -> list[dict[str, Any]]:
    results = []
    for _, point in interfaces.agent.get_metrics():
        if point.get("metric") != "feature_flag.evaluations":
            continue
        tags = point.get("tags", [])
        if flag_key is not None:
            if not any(t == f"feature_flag.key:{flag_key}" for t in tags):
                continue
        results.append(point)
    return results


def get_tag_value(tags: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for tag in tags:
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return None


# ---------------------------------------------------------------------------
# UFC fixture builders
# ---------------------------------------------------------------------------


def _base_flag(flag_key: str, variation_type: str = "STRING", *, enabled: bool = True) -> dict:
    """Minimal flag definition with no allocations yet."""
    values: dict[str, dict[str, str | bool | float | int]] = {
        "STRING": {"on": "on-value", "off": "off-value"},
        "BOOLEAN": {"on": True, "off": False},
        "NUMERIC": {"on": 1.5, "off": 0.0},
        "INTEGER": {"on": 42, "off": 0},
    }
    v = values[variation_type]
    return {
        "key": flag_key,
        "enabled": enabled,
        "variationType": variation_type,
        "variations": {
            "on": {"key": "on", "value": v["on"]},
            "off": {"key": "off", "value": v["off"]},
        },
        "allocations": [],
    }


def _wrap_fixture(flag_key: str, flag_def: dict) -> dict:
    return {
        "createdAt": "2024-04-17T19:40:53.716Z",
        "format": "SERVER",
        "environment": {"name": "Test"},
        "flags": {flag_key: flag_def},
    }


def make_zero_alloc_fixture(flag_key: str) -> dict:
    """REASON-9: Flag with zero allocations."""
    fd = _base_flag(flag_key)
    fd["allocations"] = []
    return _wrap_fixture(flag_key, fd)


def make_no_default_alloc_fixture(flag_key: str, attribute: str, match_value: str) -> dict:
    """REASON-10: Non-empty waterfall but no default allocation and rule won't match."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "rule-only-alloc",
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_pure_static_fixture(flag_key: str) -> dict:
    """REASON-11: Single allocation, no rules, no date window → STATIC.

    Uses shards:[] (vacuous split) which, like an absent shards key, means no
    hash computation is performed. Both forms produce STATIC per ADR-003. We use
    the vacuous-split form (shards:[]) because it is the established pattern across
    the codebase and is guaranteed parseable by all SDK implementations. A split
    entry with a missing shards field is not tested in any other fixture and may
    trigger a parse error in strict-deserialisation SDKs.
    """
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "static-alloc",
            "rules": [],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_multi_alloc_rule_then_default(flag_key: str, attribute: str, match_value: str) -> dict:
    """REASON-13/REASON-14: Rule-based alloc + unconditional default alloc."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "rule-alloc",
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


def make_real_shard_fixture(flag_key: str) -> dict:
    """REASON-7: Non-trivial shard; requires targeting key for hash computation."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "shard-alloc",
            "rules": [],
            "splits": [{"variationKey": "on", "shards": SHARD_ALWAYS_HIT}],
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_rule_only_no_shard_fixture(flag_key: str, attribute: str, match_value: str) -> dict:
    """REASON-8: Targeting rule + vacuous split (no hash computed). Matching without key."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "rule-alloc",
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": []}],  # Vacuous split → no hash
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_rule_plus_shard_with_default(flag_key: str, attribute: str, match_value: str, shard_spec: list) -> dict:
    """REASON-16/REASON-17/REASON-18: Same alloc has rule + non-trivial shard; default alloc follows."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "rule-shard-alloc",
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": shard_spec}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


def make_split_first_then_rule_then_default(flag_key: str, attribute: str, match_value: str) -> dict:
    """REASON-19/REASON-20: Shard alloc (guaranteed miss) → rule alloc → default alloc."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "split-alloc",
            "rules": [],
            "splits": [{"variationKey": "on", "shards": SHARD_ALWAYS_MISS}],
            "doLog": True,
        },
        {
            "key": "rule-alloc",
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


def make_active_window_single_alloc(flag_key: str) -> dict:
    """REASON-21: Single alloc with active startAt/endAt, no rules, no split."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "window-alloc",
            "startAt": WINDOW_ACTIVE_START,
            "endAt": WINDOW_ACTIVE_END,
            "rules": [],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_inactive_window_single_alloc(flag_key: str) -> dict:
    """REASON-22: Single alloc with expired window → no allocation matches → coded default."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "window-alloc",
            "startAt": WINDOW_INACTIVE_START,
            "endAt": WINDOW_INACTIVE_END,
            "rules": [],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        }
    ]
    return _wrap_fixture(flag_key, fd)


def make_active_window_multi_alloc(flag_key: str) -> dict:
    """REASON-23: First alloc has active window (no rules/split); default alloc follows."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "window-alloc",
            "startAt": WINDOW_ACTIVE_START,
            "endAt": WINDOW_ACTIVE_END,
            "rules": [],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


def make_inactive_window_multi_alloc(flag_key: str) -> dict:
    """REASON-24: First alloc has expired window; default alloc catches."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "window-alloc",
            "startAt": WINDOW_INACTIVE_START,
            "endAt": WINDOW_INACTIVE_END,
            "rules": [],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


def make_window_plus_rules_multi_alloc(flag_key: str, attribute: str, match_value: str) -> dict:
    """REASON-25/REASON-26: First alloc has active window + targeting rules; default alloc follows."""
    fd = _base_flag(flag_key)
    fd["allocations"] = [
        {
            "key": "window-rule-alloc",
            "startAt": WINDOW_ACTIVE_START,
            "endAt": WINDOW_ACTIVE_END,
            "rules": [{"conditions": [{"operator": "ONE_OF", "attribute": attribute, "value": [match_value]}]}],
            "splits": [{"variationKey": "on", "shards": []}],
            "doLog": True,
        },
        {
            "key": "default-alloc",
            "rules": [],
            "splits": [{"variationKey": "off", "shards": []}],
            "doLog": True,
        },
    ]
    return _wrap_fixture(flag_key, fd)


# ---------------------------------------------------------------------------
# REASON-2: PROVIDER_FATAL
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_2_ProviderFatal:
    """REASON-2: Provider received non-retryable 4XX → ERROR / PROVIDER_FATAL.

    Simulates a 401 Unauthorized from the RC endpoint. Per ADR-009, a non-retryable
    4XX (400, 401, 403, 404) from the assignments endpoint puts the provider into an
    unrecoverable PROVIDER_FATAL state.

    Testability note: this depends on the SDK treating an RC-level 401 as a fatal
    provider error. SDKs that only treat 4XX from a separate assignments endpoint
    may not enter PROVIDER_FATAL via this path; the test is marked accordingly.
    """

    def setup_ffe_reason_2_provider_fatal(self):
        self.config_request_data = None

        def wait_for_config_401(data: dict) -> bool:
            if data["path"] == "/v0.7/config" and data["response"]["status_code"] == 401:
                self.config_request_data = data
                return True
            return False

        # Return 401 before any valid config has been received
        StaticJsonMockedTracerResponse(
            path="/v0.7/config", mocked_json={"error": "Unauthorized"}, status_code=401
        ).send()

        # wait_for is the framework's sequencing mechanism, not time.sleep(). It
        # blocks until the tracer has observed the 401 response, which ensures the
        # provider has had the opportunity to enter PROVIDER_FATAL state before the
        # evaluation request is made. Without this gate the evaluation would race
        # the tracer's RC polling cycle and could arrive before the 401 is processed.
        # The same pattern is used in test_dynamic_evaluation.py (setup_ffe_rc_*).
        interfaces.library.wait_for(wait_for_config_401, timeout=60)

        self.flag_key = "b2-provider-fatal-flag"
        self.default_value = "coded-default"

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

        # Restore normal RC behavior
        StaticJsonMockedTracerResponse(path="/v0.7/config", mocked_json={}).send()

    def test_ffe_reason_2_provider_fatal(self):
        """REASON-2: 401 from config endpoint → ERROR / PROVIDER_FATAL; coded default returned."""
        assert self.config_request_data is not None, "No 401 response was captured from /v0.7/config"

        assert self.r.status_code == 200, f"Flag evaluation request failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"REASON-2: Expected reason=error, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "provider_fatal", (
            f"REASON-2: Expected error.type=provider_fatal, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-3: Disabled flag → FLAG_NOT_FOUND (ADR-005)
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_3_DisabledFlagNotFound:
    """REASON-3: Disabled flag is absent from the dataset → ERROR / FLAG_NOT_FOUND.

    Per ADR-005, DISABLED is not produced by this system. A disabled flag is
    excluded from the precomputed dataset, making it operationally absent.
    The SDK must return FLAG_NOT_FOUND, not DISABLED.
    """

    def setup_ffe_reason_3_disabled_flag_not_found(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b3-disabled"
        self.flag_key = "b3-disabled-flag"

        # Disabled flags are absent from the precomputed dataset the SDK receives.
        # Model this by loading a config that contains a *different* flag key — our
        # flag is simply not present, which is operationally identical to disabled.
        other_flag = _base_flag("some-other-flag")
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", _wrap_fixture("some-other-flag", other_flag)
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

    def test_ffe_reason_3_disabled_flag_not_found(self):
        """REASON-3: Flag absent from config (as disabled flags are) → ERROR / FLAG_NOT_FOUND."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"REASON-3: Expected reason=error, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "flag_not_found", (
            f"REASON-3: Expected error.type=flag_not_found (not 'disabled'), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-7: TARGETING_KEY_MISSING — shard computation reached without targeting key
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_7_TargetingKeyMissing:
    """REASON-7: Evaluation path reaches a non-trivial shard; no targeting key → ERROR / TARGETING_KEY_MISSING.

    Per ADR-008, TARGETING_KEY_MISSING fires only when a shard hash computation
    is required and no targeting key is available. Evaluations that never reach a
    shard proceed normally without a key.
    """

    def setup_ffe_reason_7_targeting_key_missing(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b7-tkm"
        self.flag_key = "b7-targeting-key-missing-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_real_shard_fixture(self.flag_key)).apply()

        # Evaluate with no targeting key — shard computation requires one
        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "",  # Missing key
                "attributes": {},
            },
        )

    def test_ffe_reason_7_targeting_key_missing(self):
        """REASON-7: Shard computation without targeting key → ERROR / TARGETING_KEY_MISSING."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "error", (
            f"REASON-7: Expected reason=error, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") == "targeting_key_missing", (
            f"REASON-7: Expected error.type=targeting_key_missing, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-8: TARGETING_MATCH — rule-only, no shard, no targeting key required
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_8_RuleOnlyNoKey:
    """REASON-8: Rule matches via attribute; vacuous split (no hash); no targeting key needed → TARGETING_MATCH.

    Per ADR-008, a targeting key is not required unless a shard computation is
    reached. A flag with targeting rules but only a vacuous split can match
    without a targeting key.
    """

    def setup_ffe_reason_8_rule_only_no_key(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b8-rule-no-key"
        self.flag_key = "b8-rule-only-no-key-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_rule_only_no_shard_fixture(self.flag_key, "tier", "gold"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "",  # No targeting key
                "attributes": {"tier": "gold"},  # Attribute match
            },
        )

    def test_ffe_reason_8_rule_only_no_key(self):
        """REASON-8: Rule matches without targeting key (no shard) → TARGETING_MATCH."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"REASON-8: Expected reason=targeting_match, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") is None, (
            f"REASON-8: Expected no error.type for successful eval, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-9: Zero allocations → DEFAULT (coded default, ADR-001)
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_9_ZeroAllocations:
    """REASON-9: Flag has zero allocations → coded default / DEFAULT (no error code, ADR-001).

    Per ADR-001, an empty waterfall returns the coded default with reason DEFAULT
    and no error code. This is not an SDK error — it represents a data invariant
    violation on the platform side.
    """

    def setup_ffe_reason_9_zero_allocations(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b9-zero-alloc"
        self.flag_key = "b9-zero-alloc-flag"
        self.default_value = "coded-default"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_zero_alloc_fixture(self.flag_key)).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_reason_9_zero_allocations(self):
        """REASON-9: Zero allocations → DEFAULT (coded default); no error code."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-9: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") is None, (
            f"REASON-9: Expected no error.type (ADR-001: not an SDK error), got tags: {tags}"
        )
        # Empty waterfall → no allocation matched → no platform variation selected.
        # SDKs may emit the tag as absent (None) or use a sentinel like "n/a"; both are valid.
        assert get_tag_value(tags, "feature_flag.result.variant") in (None, "n/a"), (
            f"REASON-9: Expected no platform variation (coded default returned, no allocation matched), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-10: Non-empty waterfall, no default allocation, no rule matches → DEFAULT
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_10_NoDefaultAlloc:
    """REASON-10: Waterfall has allocations; none matched; no default allocation → coded default / DEFAULT.

    Per ADR-001, this is the same treatment as an empty waterfall. The coded
    default is returned with reason DEFAULT and no error code.
    """

    def setup_ffe_reason_10_no_default_alloc(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b10-no-default"
        self.flag_key = "b10-no-default-alloc-flag"
        self.default_value = "coded-default"
        # Rule requires tier=platinum; we'll send tier=bronze → no match, no default alloc
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_no_default_alloc_fixture(self.flag_key, "tier", "platinum"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {"tier": "bronze"},  # Does not match "platinum"
            },
        )

    def test_ffe_reason_10_no_default_alloc(self):
        """REASON-10: Waterfall exhausted, no default alloc → DEFAULT (coded default); no error code."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-10: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") is None, (
            f"REASON-10: Expected no error.type (ADR-001: not an SDK error), got tags: {tags}"
        )
        # Waterfall exhausted, no allocation matched → no platform variation selected.
        # SDKs may emit the tag as absent (None) or use a sentinel like "n/a"; both are valid.
        assert get_tag_value(tags, "feature_flag.result.variant") in (None, "n/a"), (
            f"REASON-10: Expected no platform variation (coded default returned, no allocation matched), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-11: STATIC — single allocation, no rules, no date window
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_11_StaticNoSplit:
    """REASON-11: Single allocation; no targeting rules, no date window → STATIC.

    The RFC distinguishes REASON-11 ("no split") from REASON-12 ("vacuous split, shards:[]"),
    but in the UFC format used by this framework both are represented as a split entry
    with an empty shards array — omitting the shards key entirely is not tested across
    SDKs and may trigger strict-deserialisation errors. The fixture therefore uses the
    same vacuous-split form as REASON-12. Both forms produce STATIC per ADR-003 (no hash
    computation, no targeting rules, no date window). This test exercises the STATIC
    path via a distinct config ID and flag key, providing independent signal from the
    REASON-12 coverage in test_flag_eval_metrics.py :: Test_FFE_Eval_Metric_Basic.
    """

    def setup_ffe_reason_11_static_no_split(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b11-static"
        self.flag_key = "b11-static-no-split-flag"
        rc.tracer_rc_state.set_config(f"{RC_PATH}/{config_id}/config", make_pure_static_fixture(self.flag_key)).apply()

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

    def test_ffe_reason_11_static_no_split(self):
        """REASON-11: Single alloc, no rules, no split → STATIC (platform value)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "static", (
            f"REASON-11: Expected reason=static, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-13: TARGETING_MATCH — multi-alloc, rule matches, no split
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_13_MultiAllocRuleMatch:
    """REASON-13: Multi-allocation waterfall; rule-based alloc matches; no split in matching alloc → TARGETING_MATCH."""

    def setup_ffe_reason_13_multi_alloc_rule_match(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b13-multi-rule"
        self.flag_key = "b13-multi-alloc-rule-match-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_multi_alloc_rule_then_default(self.flag_key, "plan", "enterprise"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "user-1",
                "attributes": {"plan": "enterprise"},  # Matches rule
            },
        )

    def test_ffe_reason_13_multi_alloc_rule_match(self):
        """REASON-13: Multi-alloc, rule matches → TARGETING_MATCH (platform value)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"REASON-13: Expected reason=targeting_match, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", (
            f"REASON-13: Expected variant=on (from rule alloc), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-14: DEFAULT — multi-alloc, rule-based allocs fail, default alloc catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_14_MultiAllocRuleFail:
    """REASON-14: Multi-alloc; rule-based allocations fail; default allocation catches → DEFAULT (platform value)."""

    def setup_ffe_reason_14_multi_alloc_rule_fail(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b14-multi-default"
        self.flag_key = "b14-multi-alloc-rule-fail-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_multi_alloc_rule_then_default(self.flag_key, "plan", "enterprise"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"plan": "starter"},  # Does NOT match "enterprise"
            },
        )

    def test_ffe_reason_14_multi_alloc_rule_fail(self):
        """REASON-14: Rule fails, default alloc catches → DEFAULT (platform value, not coded default)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-14: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-14: Expected variant=off (from default alloc), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-16: DEFAULT — same alloc: rule passes, shard misses, default catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_16_RulePassShardMiss:
    """REASON-16: Same allocation has targeting rule + split; rule passes; shard misses (0%); default catches → DEFAULT."""

    def setup_ffe_reason_16_rule_pass_shard_miss(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b16-rule-shard-miss"
        self.flag_key = "b16-rule-pass-shard-miss-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_rule_plus_shard_with_default(self.flag_key, "group", "beta", SHARD_ALWAYS_MISS),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"group": "beta"},  # Rule matches; shard guaranteed miss
            },
        )

    def test_ffe_reason_16_rule_pass_shard_miss(self):
        """REASON-16: Rule passes, shard misses → allocation skipped; default alloc → DEFAULT."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-16: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-16: Expected variant=off (from default-alloc, not rule-shard-alloc), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-17: SPLIT — same alloc: rule passes, shard wins (SPLIT overrides TARGETING_MATCH)
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_17_RulePassShardWin:
    """REASON-17: Same allocation: targeting rule passes AND shard wins → SPLIT (ADR-004: SPLIT overrides TARGETING_MATCH)."""

    def setup_ffe_reason_17_rule_pass_shard_win(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b17-rule-shard-win"
        self.flag_key = "b17-rule-pass-shard-win-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_rule_plus_shard_with_default(self.flag_key, "group", "alpha", SHARD_ALWAYS_HIT),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"group": "alpha"},  # Rule matches; shard always hits
            },
        )

    def test_ffe_reason_17_rule_pass_shard_win(self):
        """REASON-17: Rule passes and shard wins → SPLIT (ADR-004: SPLIT takes precedence)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "split", (
            f"REASON-17: Expected reason=split (SPLIT overrides TARGETING_MATCH per ADR-004), got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", (
            f"REASON-17: Expected variant=on (rule-shard-alloc won), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-18: DEFAULT — same alloc: rule fails, default catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_18_RuleFail:
    """REASON-18: Same allocation: rule fails; default allocation catches → DEFAULT."""

    def setup_ffe_reason_18_rule_fail(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b18-rule-fail"
        self.flag_key = "b18-rule-fail-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_rule_plus_shard_with_default(self.flag_key, "group", "alpha", SHARD_ALWAYS_HIT),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"group": "beta"},  # Rule requires "alpha" → fails
            },
        )

    def test_ffe_reason_18_rule_fail(self):
        """REASON-18: Rule fails; default alloc catches → DEFAULT."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-18: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-18: Expected variant=off (default-alloc caught; rule-shard-alloc rule failed), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-19: TARGETING_MATCH — split alloc skipped (miss), rule-based alloc 2 matches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_19_SplitMissRuleMatch:
    """REASON-19: Split alloc skipped (shard miss); rule-based alloc 2 matches; no split → TARGETING_MATCH."""

    def setup_ffe_reason_19_split_miss_rule_match(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b19-split-miss-rule"
        self.flag_key = "b19-split-miss-rule-match-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_split_first_then_rule_then_default(self.flag_key, "region", "us-east"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"region": "us-east"},  # Matches rule alloc
            },
        )

    def test_ffe_reason_19_split_miss_rule_match(self):
        """REASON-19: Split alloc skipped (guaranteed miss); rule alloc 2 matches → TARGETING_MATCH."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"REASON-19: Expected reason=targeting_match, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-20: DEFAULT — split alloc skipped (miss), default catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_20_SplitMissDefault:
    """REASON-20: Split alloc skipped (shard miss); default alloc catches → DEFAULT."""

    def setup_ffe_reason_20_split_miss_default(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b20-split-miss-default"
        self.flag_key = "b20-split-miss-default-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_split_first_then_rule_then_default(self.flag_key, "region", "us-east"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"region": "eu-west"},  # Does NOT match rule; split guaranteed miss
            },
        )

    def test_ffe_reason_20_split_miss_default(self):
        """REASON-20: Split miss, rule fails, default alloc catches → DEFAULT."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-20: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-20: Expected variant=off (default-alloc caught; split-alloc missed, rule-alloc failed), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-21: DEFAULT — single alloc with active date window, no rules, no split
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_21_ActiveWindowSingle:
    """REASON-21: Single allocation; startAt/endAt present; window active; no rules, no split → DEFAULT.

    Per ADR-003, startAt/endAt are scheduling metadata, not targeting rules.
    A single alloc with an active date window does NOT produce STATIC because
    the result could change when the window expires. Reason is DEFAULT.
    """

    def setup_ffe_reason_21_active_window_single(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b21-active-window-single"
        self.flag_key = "b21-active-window-single-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_active_window_single_alloc(self.flag_key)
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_reason_21_active_window_single(self):
        """REASON-21: Active date window, single alloc, no rules → DEFAULT (platform value)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-21: Expected reason=default (not static — date window precludes STATIC per ADR-003), got tags: {tags}"
        )
        # Variant assertion confirms the window-alloc fired (variant "on"), not a fallback.
        # Without this, a coded-default return of "coded-default" would also satisfy reason=default.
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", (
            f"REASON-21: Expected variant=on (window-alloc fired), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-22: DEFAULT — single alloc with inactive (expired) date window
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_22_InactiveWindowSingle:
    """REASON-22: Single allocation; startAt/endAt present; window inactive (expired) → coded default / DEFAULT.

    The allocation's window has closed. The flag is present in config (not absent),
    but its only allocation is outside its time window. Per ADR-001, this is the
    non-empty-waterfall / no-match / no-default-allocation case → coded default, DEFAULT.
    This is NOT FLAG_NOT_FOUND (the flag exists in config).
    """

    def setup_ffe_reason_22_inactive_window_single(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b22-inactive-window"
        self.flag_key = "b22-inactive-window-single-flag"
        self.default_value = "coded-default"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_inactive_window_single_alloc(self.flag_key)
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": self.default_value,
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_reason_22_inactive_window_single(self):
        """REASON-22: Expired window → no active allocation; coded default / DEFAULT; no error code."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-22: Expected reason=default (ADR-001 data-invariant case, not FLAG_NOT_FOUND), got tags: {tags}"
        )
        assert get_tag_value(tags, "error.type") is None, f"REASON-22: Expected no error.type (ADR-001), got tags: {tags}"
        # No allocation matched (window expired), so no platform variation was selected.
        # SDKs may emit the tag as absent (None) or use a sentinel like "n/a"; both are valid.
        # This distinguishes REASON-22 from REASON-24 where the default-alloc fires and produces variant=off.
        assert get_tag_value(tags, "feature_flag.result.variant") in (None, "n/a"), (
            f"REASON-22: Expected no platform variation (coded default, window expired — no alloc matched), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-23: DEFAULT — multi-alloc, first alloc active window, no rules/split
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_23_ActiveWindowMulti:
    """REASON-23: Multi-alloc; first alloc has active startAt/endAt; no rules, no split → DEFAULT."""

    def setup_ffe_reason_23_active_window_multi(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b23-active-window-multi"
        self.flag_key = "b23-active-window-multi-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_active_window_multi_alloc(self.flag_key)
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_reason_23_active_window_multi(self):
        """REASON-23: Multi-alloc, first has active window (no rules/split) → DEFAULT."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-23: Expected reason=default, got tags: {tags}"
        )
        # Variant "on" confirms the window-alloc (first alloc) fired, distinguishing this from
        # the default-alloc catching (variant "off") or a coded-default return.
        assert get_tag_value(tags, "feature_flag.result.variant") == "on", (
            f"REASON-23: Expected variant=on (window-alloc fired, not default-alloc), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-24: DEFAULT — multi-alloc, first alloc window inactive, default catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_24_InactiveWindowMulti:
    """REASON-24: Multi-alloc; first alloc has expired window; default alloc catches → DEFAULT (platform value).

    Per the row-24 note in Appendix B: this is the ADR-001 data-invariant case
    (non-empty waterfall, no match, default alloc provides platform value).
    The flag is present in config; an inactive window gate is not FLAG_NOT_FOUND.
    """

    def setup_ffe_reason_24_inactive_window_multi(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b24-inactive-window-multi"
        self.flag_key = "b24-inactive-window-multi-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_inactive_window_multi_alloc(self.flag_key)
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {},
            },
        )

    def test_ffe_reason_24_inactive_window_multi(self):
        """REASON-24: First alloc window expired; default alloc catches → DEFAULT (platform value)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-24: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-24: Expected variant=off (from default alloc, platform value), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-25: TARGETING_MATCH — window active + rule matches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_25_WindowActiveRuleMatch:
    """REASON-25: Multi-alloc; alloc has active startAt/endAt + targeting rules; rule matches; no split → TARGETING_MATCH."""

    def setup_ffe_reason_25_window_active_rule_match(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b25-window-rule-match"
        self.flag_key = "b25-window-active-rule-match-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_window_plus_rules_multi_alloc(self.flag_key, "segment", "vip"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"segment": "vip"},  # Matches rule
            },
        )

    def test_ffe_reason_25_window_active_rule_match(self):
        """REASON-25: Active window + rule matches → TARGETING_MATCH (window alone doesn't imply TARGETING_MATCH)."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"REASON-25: Expected reason=targeting_match, got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# REASON-26: DEFAULT — window + rules, rule fails, default catches
# ---------------------------------------------------------------------------


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_eval_metrics
class Test_FFE_REASON_26_WindowRuleFail:
    """REASON-26: Multi-alloc; alloc has startAt/endAt + targeting rules; rule fails; default catches → DEFAULT."""

    def setup_ffe_reason_26_window_rule_fail(self):
        rc.tracer_rc_state.reset().apply()

        config_id = "ffe-b26-window-rule-fail"
        self.flag_key = "b26-window-rule-fail-flag"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config",
            make_window_plus_rules_multi_alloc(self.flag_key, "segment", "vip"),
        ).apply()

        self.r = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "STRING",
                "defaultValue": "coded-default",
                "targetingKey": "user-1",
                "attributes": {"segment": "standard"},  # Does NOT match "vip"
            },
        )

    def test_ffe_reason_26_window_rule_fail(self):
        """REASON-26: Active window + rule fails; default alloc catches → DEFAULT."""
        assert self.r.status_code == 200, f"Flag evaluation failed: {self.r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, f"Expected metric for '{self.flag_key}', found none. All: {find_eval_metrics()}"

        point = metrics[0]
        tags = point.get("tags", [])

        assert get_tag_value(tags, "feature_flag.result.reason") == "default", (
            f"REASON-26: Expected reason=default, got tags: {tags}"
        )
        assert get_tag_value(tags, "feature_flag.result.variant") == "off", (
            f"REASON-26: Expected variant=off (default-alloc caught; window-rule-alloc rule failed), got tags: {tags}"
        )


# ---------------------------------------------------------------------------
# Untestable / deferred cases (noted for completeness)
# ---------------------------------------------------------------------------
#
# REASON-5  PARSE_ERROR (entire payload): StaticJsonMockedTracerResponse always
#      serialises a Python dict through json.dumps and sends valid JSON. There
#      is no current mechanism in the mock framework to inject a raw non-JSON
#      body. Even sending a valid-JSON body with unexpected structure (e.g.,
#      {"corrupted": true}) will not trigger PARSE_ERROR — SDKs will treat it as
#      an empty/unknown config and produce FLAG_NOT_FOUND or DEFAULT, not
#      PARSE_ERROR. This case requires either raw-body mock support or a
#      lower-level fault injection mechanism not currently available.
#
# REASON-6  GENERAL: No reliable way to trigger an unclassified SDK error via the
#      weblog/RC interface. GENERAL is a catch-all for internal SDK failures
#      that don't fit a more specific code. Requires SDK internals access or
#      fault injection at a layer below what system tests can reach.
#
# REASON-2  PROVIDER_FATAL: Test_FFE_REASON_2_ProviderFatal above sends a 401 via
#      the RC mock. Whether this triggers PROVIDER_FATAL depends on whether the
#      SDK treats RC-level 4XX responses as fatal provider errors vs. transient
#      config fetch failures. SDKs where the FFE provider has a separate
#      assignments endpoint (not RC) will not enter PROVIDER_FATAL via this
#      path. The test is a best-effort probe; SDK teams must verify their
#      specific PROVIDER_FATAL transition path independently.
#
# REASON-13 INVALID_CONTEXT: Per the RFC, this error code is reserved and likely to
#      be deprecated pending OF.3 dot-flattening resolution. Not tested here.
#      The OF.3 behavior (nested attributes ignored vs. error) is covered by
#      Test_FFE_Eval_Nested_Attributes_Ignored in test_flag_eval_metrics.py.

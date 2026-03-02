"""Test feature flag evaluation metrics via OTel Metrics API."""

import time

from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    remote_config as rc,
)


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"

# Wait time in seconds for OTLP metrics pipeline:
# OTel SDK export interval (10s) + Agent metric flush (10s) + buffer
METRICS_PIPELINE_WAIT = 25


def make_ufc_fixture(flag_key, variant_key="on", variation_type="STRING", enabled=True):
    """Create a UFC fixture with the given flag configuration."""
    values = {
        "STRING": {"on": "on-value", "off": "off-value"},
        "BOOLEAN": {"on": True, "off": False},
    }
    var_values = values.get(variation_type, values["STRING"])

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


def find_eval_metrics(flag_key=None):
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


def get_tag_value(tags, key):
    """Extract a tag value from a list of 'key:value' strings."""
    prefix = f"{key}:"
    for tag in tags:
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return None


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
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

        # Wait for OTLP metrics pipeline
        time.sleep(METRICS_PIPELINE_WAIT)

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
        assert get_tag_value(tags, "feature_flag.result.reason") == "targeting_match", (
            f"Expected tag feature_flag.result.reason:targeting_match, got tags: {tags}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
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

        time.sleep(METRICS_PIPELINE_WAIT)

    def test_ffe_eval_metric_count(self):
        """Test that N evaluations produce metric count = N."""
        for i, r in enumerate(self.responses):
            assert r.status_code == 200, f"Request {i + 1} failed: {r.text}"

        metrics = find_eval_metrics(self.flag_key)
        assert len(metrics) > 0, (
            f"Expected at least one feature_flag.evaluations metric for flag '{self.flag_key}', "
            f"but found none."
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

        assert total_count >= self.eval_count, (
            f"Expected metric count >= {self.eval_count}, got {total_count}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
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

        time.sleep(METRICS_PIPELINE_WAIT)

    def test_ffe_eval_metric_different_flags(self):
        """Test that each flag key gets its own metric series."""
        assert self.r_a.status_code == 200, f"Flag A evaluation failed: {self.r_a.text}"
        assert self.r_b.status_code == 200, f"Flag B evaluation failed: {self.r_b.text}"

        metrics_a = find_eval_metrics(self.flag_a)
        metrics_b = find_eval_metrics(self.flag_b)

        assert len(metrics_a) > 0, (
            f"Expected metric for flag '{self.flag_a}', found none. All: {find_eval_metrics()}"
        )
        assert len(metrics_b) > 0, (
            f"Expected metric for flag '{self.flag_b}', found none. All: {find_eval_metrics()}"
        )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_exposures
class Test_FFE_Eval_Metric_Error:
    """Test that evaluating a non-existent flag produces metric with error tags."""

    def setup_ffe_eval_metric_error(self):
        rc.tracer_rc_state.reset().apply()

        # Set up config with a different flag than what we'll request
        config_id = "ffe-eval-metric-error"
        rc.tracer_rc_state.set_config(
            f"{RC_PATH}/{config_id}/config", make_ufc_fixture("some-other-flag")
        ).apply()

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

        time.sleep(METRICS_PIPELINE_WAIT)

    def test_ffe_eval_metric_error(self):
        """Test that error evaluations produce metric with error.type tag."""
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

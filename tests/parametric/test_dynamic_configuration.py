"""
Test the dynamic configuration via Remote Config (RC) feature of the APM libraries.
"""
import json
import random
from typing import Any
from typing import Dict

from utils import missing_feature, context, scenarios

import pytest


parametrize = pytest.mark.parametrize


base_env = {
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}

DEFAULT_SAMPLE_RATE = 1.0


def send_and_wait_trace(test_library, test_agent, **span_kwargs):
    with test_library.start_span(**span_kwargs):
        pass
    traces = test_agent.wait_for_num_traces(num=1, clear=True)
    assert len(traces) == 1
    return traces[0]


def set_and_wait_rc(test_agent, config: Dict[str, Any]):
    cfg = {
        # v1 dynamic config
        "tracing_sampling_rate": None,
        "log_injection_enabled": None,
        "tracing_header_tags": None,
        # v2 dynamic config
        "runtime_metrics_enabled": None,
        "tracing_debug": None,
        "tracing_service_mapping": None,
        "tracing_sampling_rules": None,
        "span_sampling_rules": None,
        "data_streams_enabled": None,
    }
    for k, v in config.items():
        cfg[k] = v

    cfg_id = "%032x" % random.getrandbits(128)
    test_agent.set_remote_config(
        path="datadog/2/APM_TRACING/%s/config" % cfg_id,
        payload={
            # These values don't matter, can be anything
            "action": "enable",
            "service_target": {"service": "myservice", "env": "dev"},
            "lib_config": cfg,
        },
    )
    test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
    return test_agent.wait_for_apply_status("APM_TRACING", clear=True, state=2)


def assert_sampling_rate(span: Dict, rate: float):
    """Asserts that a span returned from the test agent is consistent with the given sample rate.

    It is assumed that the span is the root span of the trace.
    """
    # TODO: find the right heuristics to assert the sample rate
    # if "_dd.agent_psr" in span["metrics"]:
    #     assert span["metrics"]["_dd.agent_psr"] == rate
    if "_dd.rule_psr" in span["metrics"]:
        assert span["metrics"]["_dd.rule_psr"] == pytest.approx(rate)


ENV_SAMPLING_RULE_RATE = 0.55


@scenarios.parametric
class TestDynamicConfig:
    @parametrize("library_env", [{"DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"}])
    def test_telemetry_app_started(self, library_env, test_agent, test_library):
        """Ensure that the app-started telemetry event is being submitted.

        Telemetry events are used as a signal for the configuration being applied
        by the library.
        """
        # Python doesn't start writing telemetry until the first trace.
        with test_library.start_span("test"):
            pass
        events = test_agent.wait_for_telemetry_event("app-started")
        assert len(events) > 0

    @parametrize("library_env", [{**base_env}])
    def test_apply_status(self, library_env, test_agent, test_library):
        """Create a default RC record and ensure the apply_status is correctly set.

        This signal, along with the telemetry event, is used to determine when the
        configuration has been applied by the tracer.
        """
        set_and_wait_rc(test_agent, {})
        cfg_state = test_agent.wait_for_apply_status("APM_TRACING", state=2)
        assert cfg_state["apply_state"] == 2
        assert cfg_state["product"] == "APM_TRACING"

    @parametrize("library_env", [{**base_env}])
    def test_trace_sampling_rate_override_default(self, test_agent, test_library):
        """The RC sampling rate should override the default sampling rate.

        When RC is unset, the default should be used again.
        """
        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], DEFAULT_SAMPLE_RATE)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": 0.5})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], 0.5)

        # Unset the RC sample rate to ensure the default setting is used.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], DEFAULT_SAMPLE_RATE)

    @parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": r, **base_env,} for r in ["0.1", "1.0"]])
    def test_trace_sampling_rate_override_env(self, library_env, test_agent, test_library):
        """The RC sampling rate should override the environment variable.

        When RC is unset, the environment variable should be used.
        """
        trace_sample_rate_env = library_env["DD_TRACE_SAMPLE_RATE"]
        if trace_sample_rate_env is None:
            initial_sample_rate = DEFAULT_SAMPLE_RATE
        else:
            initial_sample_rate = float(trace_sample_rate_env)

        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], initial_sample_rate)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": 0.5})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], 0.5)

        # Create another remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": 0.6})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], 0.6)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace[0], initial_sample_rate)

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "name": "env_name"}]),
                **base_env,
            }
        ],
    )
    def test_trace_sampling_rate_with_sampling_rules(self, library_env, test_agent, test_library):
        """Ensure that sampling rules still apply when the sample rate is set via remote config."""
        RC_SAMPLING_RULE_RATE = 0.56
        assert RC_SAMPLING_RULE_RATE != ENV_SAMPLING_RULE_RATE

        # Create an initial trace to assert that the rule is correctly applied.
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace[0], ENV_SAMPLING_RULE_RATE)

        # Create a remote config entry with a different sample rate. This rate should not
        # apply to env_service spans but should apply to all others.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": RC_SAMPLING_RULE_RATE})

        trace = send_and_wait_trace(test_library, test_agent, name="env_name", service="")
        assert_sampling_rate(trace[0], ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace[0], RC_SAMPLING_RULE_RATE)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace[0], ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace[0], DEFAULT_SAMPLE_RATE)

    @parametrize(
        "library_env",
        [
            {"DD_TRACE_LOGS_INJECTION": "true", **base_env,},
            {"DD_TRACE_LOGS_INJECTION": "false", **base_env,},
            {**base_env,},
        ],
    )
    def test_log_injection_enabled(self, library_env, test_agent, test_library):
        cfg_state = set_and_wait_rc(test_agent, config={"tracing_sample_rate": None})
        assert cfg_state["apply_state"] == 2

    @pytest.mark.skip(reason="TODO: enable once the http request support is added")
    @parametrize(
        "library_env",
        [{**base_env, "DD_TRACE_HEADER_TAGS": "X-Test-Header:test_header_env, X-Test-Header-2:test_header_env2"},],
    )
    def test_tracing_header_tags(self, library_env, test_agent, test_library):
        cfg_state = set_and_wait_rc(
            test_agent, config={"tracing_header_tags": [{"header": "X-Test-Header", "tag_name": "test_header",}]}
        )
        assert cfg_state["apply_state"] == 2

        trace = do_http_request(
            test_library, headers={"X-Test-Header": "test-value", "X-Test-Header-2": "test-value-2"}
        )
        assert trace[0]["meta"]["test_header"] == "test-value"
        assert trace[0]["meta"]["test_header_env2"] == "test-value-2"


# TODO test case for new version of config, ensure it doesn't break libraries

"""
Test the dynamic configuration via Remote Config (RC) feature of the APM libraries.
"""
from typing import Dict
from typing import Union

import pytest


parametrize = pytest.mark.parametrize


base_env = {
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    "DD_REMOTE_CONFIG_POLL_SECONDS": "0.1",
}

def send_and_wait_trace(test_library, test_agent, **span_kwargs):
    with test_library.start_span(**span_kwargs):
        pass
    traces = test_agent.wait_for_num_traces(num=1, clear=True)
    assert len(traces) == 1
    return traces[0]


def set_and_wait_rc(test_agent, config: Dict[str, Union[str, bool, float, None]]):
    cfg = {
        "runtime_metrics_enabled": None,
        "trace_debug_enabled": None,
        "trace_http_header_tags": None,
        "trace_service_mapping": None,
        "trace_sample_rate": None,
    }
    for k, v in config.items():
        cfg[k] = v

    test_agent.set_remote_config(path="datadog/2/APM_TRACING/override_config/config", payload=cfg)
    # TODO: ensure this is the correct config-change event
    test_agent.wait_for_telemetry_event("app-client-configuration-change")


@parametrize("library_env", [{"DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"}])
def test_telemetry_app_started(library_env, test_agent, test_library):
    # Python doesn't start writing telemetry until the first trace.
    with test_library.start_span("test"):
        pass
    events = test_agent.wait_for_telemetry_event("app-started")
    assert len(events) > 0


@parametrize("library_env", [{
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
    "DD_REMOTE_CONFIG_POLL_SECONDS": "0.1",
    "DD_TRACE_SAMPLE_RATE": r,
} for r in [None, "0.75", "1.0"]])
def test_trace_sampling_rate(library_env, test_agent, test_library):
    trace_sample_rate_env = library_env["DD_TRACE_SAMPLE_RATE"]
    if trace_sample_rate_env is None:
        # Default sample rate is 1.0
        initial_sample_rate = 1.0
    else:
        initial_sample_rate = float(trace_sample_rate_env)

    # Create an initial trace to assert the default sampling settings.
    trace = send_and_wait_trace(test_library, test_agent, name="test")
    assert trace[0]["metrics"]["_dd.rule_psr"] == initial_sample_rate

    # Create a remote config entry, wait for the configuration change telemetry event to be received
    # and then create a new trace to assert the configuration has been applied.
    set_and_wait_rc(test_agent, config={"trace_sample_rate": 0.5})
    trace = send_and_wait_trace(test_library, test_agent, name="test")
    assert trace[0]["metrics"]["_dd.rule_psr"] == 0.5

    # Unset the sample rate to ensure the previous setting is reapplied.
    set_and_wait_rc(test_agent, config={"trace_sample_rate": None})
    trace = send_and_wait_trace(test_library, test_agent, name="test")
    assert trace[0]["metrics"]["_dd.agent_psr"] == initial_sample_rate
    # TODO: shouldn't this assertion pass?
    # assert trace[0]["metrics"]["_dd.rule_psr"] == initial_sample_rate


@parametrize("library_env", [{"DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1", "DD_REMOTE_CONFIG_POLL_SECONDS": "0.1"}])
def test_trace_service_mapping(library_env, test_agent, test_library):
    with test_library.start_span("test", service="svc1"):
        pass
    traces = test_agent.wait_for_num_traces(num=1, clear=True)
    assert traces[0][0]["service"] == "svc1"

    test_agent.set_remote_config(
        path="datadog/2/APM_TRACING/override_config/config",
        payload={
            "runtime_metrics_enabled": None,
            "trace_debug_enabled": None,
            "trace_http_header_tags": None,
            "trace_service_mapping": None,
            "trace_sample_rate": 0.5,
        },
    )
    events = test_agent.wait_for_telemetry_event("app-client-configuration-change")
    with test_library.start_span("test"):
        pass
    traces = test_agent.wait_for_num_traces(num=1)
    assert traces[0][0]["metrics"]["_dd.rule_psr"] == 0.5
    assert len(events) > 0

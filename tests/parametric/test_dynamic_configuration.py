"""
Test the dynamic configuration via Remote Config (RC) feature of the APM libraries.
"""
import json
from typing import Any, Dict, List

import pytest
from ddapm_test_agent.trace import root_span

from utils import bug, context, features, irrelevant, missing_feature, rfc, scenarios
from utils.parametric.spec.remoteconfig import Capabilities
from utils.parametric.spec.trace import Span, assert_trace_has_tags

parametrize = pytest.mark.parametrize


DEFAULT_SAMPLE_RATE = 1.0
TEST_SERVICE = "test_service"
TEST_ENV = "test_env"
DEFAULT_ENVVARS = {
    "DD_SERVICE": TEST_SERVICE,
    "DD_ENV": TEST_ENV,
    # Needed for .NET until Telemetry V2 is released
    "DD_INTERNAL_TELEMETRY_V2_ENABLED": "1",
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def send_and_wait_trace(test_library, test_agent, **span_kwargs) -> List[Span]:
    with test_library.start_span(**span_kwargs):
        pass
    test_library.flush()
    traces = test_agent.wait_for_num_traces(num=1, clear=True)
    assert len(traces) == 1
    return traces[0]


def _default_config(service: str, env: str) -> Dict[str, Any]:
    return {
        "action": "enable",
        "revision": 1698167126064,
        "service_target": {"service": service, "env": env},
        "lib_config": {
            # v1 dynamic config
            "tracing_sampling_rate": None,
            "log_injection_enabled": None,
            "tracing_header_tags": None,
            # v2 dynamic config
            "runtime_metrics_enabled": None,
            "tracing_debug": None,
            "tracing_service_mapping": None,
            "tracing_sampling_rules": None,
            "data_streams_enabled": None,
        },
    }


def _set_rc(test_agent, config: Dict[str, Any]) -> None:
    cfg_id = hash(json.dumps(config))

    config["id"] = str(cfg_id)
    test_agent.set_remote_config(
        path="datadog/2/APM_TRACING/%s/config" % cfg_id, payload=config,
    )


def _create_rc_config(config_overrides: Dict[str, Any]) -> Dict:
    rc_config = _default_config(TEST_SERVICE, TEST_ENV)
    for k, v in config_overrides.items():
        rc_config["lib_config"][k] = v
    return rc_config


def set_and_wait_rc(test_agent, config_overrides: Dict[str, Any]) -> Dict:
    """Helper to create an RC configuration with the given settings and wait for it to be applied.

    It is assumed that the configuration is successfully applied.
    """
    rc_config = _create_rc_config(config_overrides)

    _set_rc(test_agent, rc_config)

    # Wait for both the telemetry event and the RC apply status.
    test_agent.wait_for_telemetry_event(
        "app-client-configuration-change", clear=True,
    )
    return test_agent.wait_for_rc_apply_state("APM_TRACING", state=2, clear=True)


def assert_sampling_rate(trace: List[Dict], rate: float):
    """Asserts that a trace returned from the test agent is consistent with the given sample rate.

    This function assumes that all traces are sent to the agent regardless of sample rate.

    For the day when that is not the case, we likely need to generate enough traces to
        1) Validate the sample rate is effective (approx sample_rate% of traces should be received)
        2) The `_dd.rule_psr` metric is set to the correct value.
    """
    # This tag should be set on the first span in a chunk (first span in the list of spans sent to the agent).
    assert trace[0]["metrics"].get("_dd.rule_psr", 1.0) == pytest.approx(rate)


def is_sampled(trace: List[Dict]):
    """Asserts that a trace returned from the test agent is consistent with the given sample rate.

    This function assumes that all traces are sent to the agent regardless of sample rate.

    For the day when that is not the case, we likely need to generate enough traces to
        1) Validate the sample rate is effective (approx sample_rate% of traces should be received)
        2) The `_dd.rule_psr` metric is set to the correct value.
    """

    # This tag should be set on the first span in a chunk (first span in the list of spans sent to the agent).
    return trace[0]["metrics"].get("_sampling_priority_v1", 0) > 0


def get_sampled_trace(test_library, test_agent, service, name, tags=None):
    trace = None
    while not trace or not is_sampled(trace):
        trace = send_and_wait_trace(test_library, test_agent, service=service, name=name, tags=tags)
    return trace


ENV_SAMPLING_RULE_RATE = 0.55


@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigHeaderTags:
    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_HEADER_TAGS": "X-Test-Header:test_header_env,X-Test-Header-2:test_header_env2,Content-Length:content_length_env",
            },
        ],
    )
    def test_tracing_client_http_header_tags(
        self, library_env, test_agent, test_library, test_agent_hostname, test_agent_port
    ):
        """Ensure the tracing http header tags can be set via RC.

        Testing is done using a http client request RPC and asserting the span tags.

        Requests are made to the test agent.
        """

        # Test without RC.
        test_library.http_client_request(
            method="GET",
            url=f"http://{test_agent_hostname}:{test_agent_port}",
            headers=[("X-Test-Header", "test-value"), ("X-Test-Header-2", "test-value-2"), ("Content-Length", "35"),],
        )
        trace = test_agent.wait_for_num_traces(num=1, clear=True)
        assert trace[0][0]["meta"]["test_header_env"] == "test-value"
        assert trace[0][0]["meta"]["test_header_env2"] == "test-value-2"
        assert int(trace[0][0]["meta"]["content_length_env"]) > 0

        # Set and test with RC.
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_header_tags": [
                    {"header": "X-Test-Header", "tag_name": "test_header_rc"},
                    {"header": "X-Test-Header-2", "tag_name": "test_header_rc2"},
                    {"header": "Content-Length", "tag_name": ""},
                ]
            },
        )
        test_library.http_client_request(
            method="GET",
            url=f"http://{test_agent_hostname}:{test_agent_port}",
            headers=[("X-Test-Header", "test-value"), ("X-Test-Header-2", "test-value-2"), ("Content-Length", "0")],
        )
        trace = test_agent.wait_for_num_traces(num=1, clear=True)
        assert trace[0][0]["meta"]["test_header_rc"] == "test-value"
        assert trace[0][0]["meta"]["test_header_rc2"] == "test-value-2"
        assert trace[0][0]["meta"]["http.request.headers.content-length"] == "0"
        assert (
            trace[0][0]["meta"]["http.response.headers.content-length"] == "14"
        ), "response content-length header tag value matches the header value set by the server"
        assert "test_header_env" not in trace[0][0]["meta"]
        assert "test_header_env2" not in trace[0][0]["meta"]

        # Unset RC.
        set_and_wait_rc(test_agent, config_overrides={})
        test_library.http_client_request(
            method="GET",
            url=f"http://{test_agent_hostname}:{test_agent_port}",
            headers=[("X-Test-Header", "test-value"), ("X-Test-Header-2", "test-value-2"), ("Content-Length", "35"),],
        )
        trace = test_agent.wait_for_num_traces(num=1, clear=True)
        assert trace[0][0]["meta"]["test_header_env"] == "test-value"
        assert trace[0][0]["meta"]["test_header_env2"] == "test-value-2"
        assert int(trace[0][0]["meta"]["content_length_env"]) > 0


@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigTracingEnabled:
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_enabled(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the tracing enabled capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_ENABLED])

    @parametrize(
        "library_env", [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "false"},],
    )
    def test_tracing_client_tracing_enabled(self, library_env, test_agent, test_library):
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED", "true") == "true"
        if trace_enabled_env:
            with test_library:
                with test_library.start_span("allowed"):
                    pass
            test_agent.wait_for_num_traces(num=1, clear=True)
            assert True, (
                "DD_TRACE_ENABLED=true and unset results in a trace being sent."
                "wait_for_num_traces does not raise an exception."
            )

        _set_rc(test_agent, _create_rc_config({"tracing_enabled": False}))
        # if tracing is disabled via DD_TRACE_ENABLED, the RC should not re-enable it
        # nor should it send RemoteConfig apply state
        if trace_enabled_env:
            test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
            test_agent.wait_for_rc_apply_state("APM_TRACING", state=2, clear=True)
        with test_library:
            with test_library.start_span("disabled"):
                pass
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)
        assert True, "no traces are sent after RC response with tracing_enabled: false"

    @parametrize(
        "library_env", [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "false"},],
    )
    @irrelevant(library="golang")
    def test_tracing_client_tracing_disable_one_way(self, library_env, test_agent, test_library):
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED", "true") == "true"

        _set_rc(test_agent, _create_rc_config({"tracing_enabled": False}))
        if trace_enabled_env:
            test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
            test_agent.wait_for_rc_apply_state("APM_TRACING", state=2, clear=True)

        _set_rc(test_agent, _create_rc_config({}))
        with test_library:
            with test_library.start_span("test"):
                pass

        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)
        assert (
            True
        ), "no traces are sent after tracing_enabled: false, even after an RC response with a different setting"


def reverse_case(s):
    return "".join([char.lower() if char.isupper() else char.upper() for char in s])


@rfc("https://docs.google.com/document/d/1SVD0zbbAAXIsobbvvfAEXipEUO99R9RMsosftfe9jx0")
@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigV1:
    """Tests covering the v1 release of the dynamic configuration feature.

    v1 includes support for:
        - tracing_sampling_rate
        - log_injection_enabled
    """

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

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_apply_state(self, library_env, test_agent, test_library):
        """Create a default RC record and ensure the apply_state is correctly set.

        This signal, along with the telemetry event, is used to determine when the
        configuration has been applied by the tracer.
        """
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.5})
        cfg_state = test_agent.wait_for_rc_apply_state("APM_TRACING", state=2)
        assert cfg_state["apply_state"] == 2
        assert cfg_state["product"] == "APM_TRACING"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_trace_sampling_rate_override_default(self, test_agent, test_library):
        """The RC sampling rate should override the default sampling rate.

        When RC is unset, the default should be used again.
        """
        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(
            test_agent, config_overrides={"tracing_sampling_rate": 0.5,},
        )
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.5)

        # Unset the RC sample rate to ensure the default setting is used.
        set_and_wait_rc(
            test_agent, config_overrides={"tracing_sampling_rate": None,},
        )
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @parametrize(
        "library_env", [{"DD_TRACE_SAMPLE_RATE": r, **DEFAULT_ENVVARS,} for r in ["0.1", "1.0"]],
    )
    @bug(library="cpp", reason="Trace sampling RC creates another sampler which makes the computation wrong")
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
        assert_sampling_rate(trace, initial_sample_rate)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.5})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.5)

        # Create another remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.6})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.6)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, initial_sample_rate)

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "name": "env_name"}]),
            }
        ],
    )
    @bug(library="cpp", reason="empty service default to '*'")
    def test_trace_sampling_rate_with_sampling_rules(self, library_env, test_agent, test_library):
        """Ensure that sampling rules still apply when the sample rate is set via remote config."""
        RC_SAMPLING_RULE_RATE = 0.56
        assert RC_SAMPLING_RULE_RATE != ENV_SAMPLING_RULE_RATE

        # Create an initial trace to assert that the rule is correctly applied.
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)

        # Create a remote config entry with a different sample rate. This rate should not
        # apply to env_service spans but should apply to all others.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": RC_SAMPLING_RULE_RATE})

        trace = send_and_wait_trace(test_library, test_agent, name="env_name", service="")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace, RC_SAMPLING_RULE_RATE)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @missing_feature(context.library in ("cpp", "golang"), reason="Tracer doesn't support automatic logs injection")
    @parametrize(
        "library_env",
        [
            {"DD_TRACE_LOGS_INJECTION": "true", **DEFAULT_ENVVARS,},
            {"DD_TRACE_LOGS_INJECTION": "false", **DEFAULT_ENVVARS,},
            {**DEFAULT_ENVVARS,},
        ],
    )
    def test_log_injection_enabled(self, library_env, test_agent, test_library):
        """Ensure that the log injection setting can be set.

        There is no way (at the time of writing) to check the logs produced by the library.
        """
        cfg_state = set_and_wait_rc(test_agent, config_overrides={"tracing_sample_rate": None})
        assert cfg_state["apply_state"] == 2


@rfc("https://docs.google.com/document/d/1SVD0zbbAAXIsobbvvfAEXipEUO99R9RMsosftfe9jx0")
@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigV1_ServiceTargets:
    """Tests covering the Service Target matching of the dynamic configuration feature.

    - ignore mismatching targets
    - matching service target case-insensitively
    """

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                # Override service and env
                "DD_SERVICE": s,
                "DD_ENV": e,
            }
            for (s, e) in [
                (DEFAULT_ENVVARS["DD_SERVICE"] + "-override", DEFAULT_ENVVARS["DD_ENV"]),
                (DEFAULT_ENVVARS["DD_SERVICE"], DEFAULT_ENVVARS["DD_ENV"] + "-override"),
                (DEFAULT_ENVVARS["DD_SERVICE"] + "-override", DEFAULT_ENVVARS["DD_ENV"] + "-override"),
            ]
        ],
    )
    def test_not_match_service_target(self, library_env, test_agent, test_library):
        """Test that the library reports an erroneous apply_state when the service targeting is not correct.

        This can occur if the library requests Remote Configuration with an initial service + env pair and then
        one or both of the values changes.

        We simulate this condition by setting DD_SERVICE and DD_ENV to values that differ from the service
        target in the RC record.
        """
        _set_rc(test_agent, _default_config(TEST_SERVICE, TEST_ENV))

        rc_args = {}
        if context.library == "cpp":
            # C++ make RC requests every second -> update is a bit slower to propagate.
            rc_args["wait_loops"] = 1000

        cfg_state = test_agent.wait_for_rc_apply_state("APM_TRACING", state=3, **rc_args)
        assert cfg_state["apply_state"] == 3
        assert cfg_state["apply_error"] != ""

    @missing_feature(
        context.library in ["golang", "cpp"], reason="Tracer does case-sensitive checks for service and env"
    )
    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                # Override service and env
                "DD_SERVICE": s,
                "DD_ENV": e,
            }
            for (s, e) in [
                (reverse_case(DEFAULT_ENVVARS["DD_SERVICE"]), DEFAULT_ENVVARS["DD_ENV"]),
                (DEFAULT_ENVVARS["DD_SERVICE"], reverse_case(DEFAULT_ENVVARS["DD_ENV"])),
                (reverse_case(DEFAULT_ENVVARS["DD_SERVICE"]), reverse_case(DEFAULT_ENVVARS["DD_ENV"])),
            ]
        ],
    )
    def test_match_service_target_case_insensitively(self, library_env, test_agent, test_library):
        """Test that the library reports a non-erroneous apply_state when the service targeting is correct but differ in case.

        This can occur if the library requests Remote Configuration with an initial service + env pair and then
        one or both of the values changes its case.

        We simulate this condition by setting DD_SERVICE and DD_ENV to values that differ only in case from the service
        target in the RC record.
        """
        _set_rc(test_agent, _default_config(TEST_SERVICE, TEST_ENV))
        cfg_state = test_agent.wait_for_rc_apply_state("APM_TRACING", state=2)
        assert cfg_state["apply_state"] == 2


@rfc("https://docs.google.com/document/d/1V4ZBsTsRPv8pAVG5WCmONvl33Hy3gWdsulkYsE4UZgU/edit")
@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigV2:
    @parametrize(
        "library_env", [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TAGS": "key1:val1,key2:val2"},],
    )
    def test_tracing_client_tracing_tags(self, library_env, test_agent, test_library):
        expected_local_tags = {}
        if "DD_TAGS" in library_env:
            expected_local_tags = dict([p.split(":") for p in library_env["DD_TAGS"].split(",")])

        # Ensure tags are applied from the env
        with test_library:
            with test_library.start_span("test") as span:
                with test_library.start_span("test2", parent_id=span.span_id):
                    pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True)
        assert_trace_has_tags(traces[0], expected_local_tags)

        # Ensure local tags are overridden and RC tags applied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_tags": ["rc_key1:val1", "rc_key2:val2"]})
        with test_library:
            with test_library.start_span("test") as span:
                with test_library.start_span("test2", parent_id=span.span_id):
                    pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True)
        assert_trace_has_tags(traces[0], {"rc_key1": "val1", "rc_key2": "val2"})

        # Ensure previous tags are restored.
        set_and_wait_rc(test_agent, config_overrides={})
        with test_library:
            with test_library.start_span("test") as span:
                with test_library.start_span("test2", parent_id=span.span_id):
                    pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True)
        assert_trace_has_tags(traces[0], expected_local_tags)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_sample_rate(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the trace sampling rate capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_SAMPLE_RATE])

    @irrelevant(context.library in ("cpp", "golang"), reason="Tracer doesn't support automatic logs injection")
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_logs_injection(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the logs injection capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_LOGS_INJECTION])

    @irrelevant(library="cpp", reason="The CPP tracer doesn't support automatic logs injection")
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_http_header_tags(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the http header tags capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_HTTP_HEADER_TAGS])

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_custom_tags(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the custom tags capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_CUSTOM_TAGS])


@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigSamplingRules:
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_sample_rules(self, library_env, test_agent, test_library):
        """Ensure the RC request contains the trace sampling rules capability."""
        test_agent.wait_for_rc_capabilities([Capabilities.APM_TRACING_SAMPLE_RULES])

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "service": "*"}]),
            }
        ],
    )
    def test_trace_sampling_rules_override_env(self, library_env, test_agent, test_library):
        """The RC sampling rules should override the environment variable and decision maker is set appropriately.

        When RC is unset, the environment variable should be used.
        """
        RC_SAMPLING_RULE_RATE_CUSTOMER = 0.8
        RC_SAMPLING_RULE_RATE_DYNAMIC = 0.4
        assert RC_SAMPLING_RULE_RATE_CUSTOMER != ENV_SAMPLING_RULE_RATE
        assert RC_SAMPLING_RULE_RATE_DYNAMIC != ENV_SAMPLING_RULE_RATE
        assert RC_SAMPLING_RULE_RATE_CUSTOMER != DEFAULT_SAMPLE_RATE
        assert RC_SAMPLING_RULE_RATE_DYNAMIC != DEFAULT_SAMPLE_RATE

        trace = get_sampled_trace(test_library, test_agent, service="", name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is set to "-3" (i.e., local RULE_RATE)
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Create a remote config entry with two rules at different sample rates.
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rules": [
                    {
                        "sample_rate": RC_SAMPLING_RULE_RATE_CUSTOMER,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "provenance": "customer",
                    },
                    {
                        "sample_rate": RC_SAMPLING_RULE_RATE_DYNAMIC,
                        "service": "*",
                        "resource": "*",
                        "provenance": "dynamic",
                    },
                ]
            },
        )

        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, RC_SAMPLING_RULE_RATE_CUSTOMER)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user rule)
        span = root_span(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-11"

        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, RC_SAMPLING_RULE_RATE_DYNAMIC)
        # Make sure `_dd.p.dm` is set to "-12" (i.e., remote dynamic rule)
        span = root_span(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-12"

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rules": None})
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is restored to "-3"
        span = root_span(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_trace_sampling_rules_override_rate(self, library_env, test_agent, test_library):
        """The RC sampling rules should override the RC sampling rate."""
        RC_SAMPLING_RULE_RATE_CUSTOMER = 0.8
        RC_SAMPLING_RATE = 0.9
        assert RC_SAMPLING_RULE_RATE_CUSTOMER != DEFAULT_SAMPLE_RATE
        assert RC_SAMPLING_RATE != DEFAULT_SAMPLE_RATE

        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rate": RC_SAMPLING_RATE,
                "tracing_sampling_rules": [
                    {"sample_rate": RC_SAMPLING_RULE_RATE_CUSTOMER, "service": TEST_SERVICE, "provenance": "customer"}
                ],
            },
        )

        # trace/span matching the rule gets applied the rule's rate
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, RC_SAMPLING_RULE_RATE_CUSTOMER)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user rule)
        span = root_span(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-11"

        # trace/span not matching the rule gets applied the RC global rate
        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, RC_SAMPLING_RATE)
        # `_dd.p.dm` is set to "-3" (rule rate, this is the legacy behavior)
        span = root_span(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Unset RC to ensure local settings
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rules": None, "tracing_sampling_rules": None})
        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "service": "*"}]),
            }
        ],
    )
    @bug(
        context.library == "cpp",
        reason="JSON tag format in RC differs from the JSON tag format used in DD_TRACE_SAMPLING_RULES",
    )

    @missing_feature(library="nodejs")
    @missing_feature(library="python")
    @bug(context.library == "ruby", reason="RC_SAMPLING_TAGS_RULE_RATE is not respected")
    def test_trace_sampling_rules_with_tags(self, test_agent, test_library):
        """RC sampling rules with tags should match/skip spans with/without corresponding tag values.

        When a sampling rule contains a tag clause/pattern, it should be used to match against a trace/span.
        If span does not contain the tag or the tag value matches the pattern, sampling decisions are made using the corresponding rule rate.
        Otherwise, sampling decision is made using the next precedence mechanism (remote global rate in our test case).
        """
        RC_SAMPLING_TAGS_RULE_RATE = 0.8
        RC_SAMPLING_RATE = 0.3
        RC_SAMPLING_ADAPTIVE_RATE = 0.1
        assert RC_SAMPLING_TAGS_RULE_RATE != ENV_SAMPLING_RULE_RATE
        assert RC_SAMPLING_RATE != ENV_SAMPLING_RULE_RATE
        assert RC_SAMPLING_ADAPTIVE_RATE != ENV_SAMPLING_RULE_RATE

        trace = get_sampled_trace(
            test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[("tag-a", "tag-a-val")]
        )
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is set to "-3" (i.e., local RULE_RATE)
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Create a remote config entry with two rules at different sample rates.
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rate": RC_SAMPLING_RATE,
                "tracing_sampling_rules": [
                    {
                        "sample_rate": RC_SAMPLING_TAGS_RULE_RATE,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "tags": [{"key": "tag-a", "value_glob": "tag-a-val*"}],
                        "provenance": "customer",
                    },
                ],
            },
        )

        # A span with matching tag and value. The remote matching tag rule should apply.
        trace = get_sampled_trace(
            test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[("tag-a", "tag-a-val")]
        )
        assert_sampling_rate(trace, RC_SAMPLING_TAGS_RULE_RATE)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user RULE_RATE)
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-11"

        # A span with the tag but value does not match. Remote global rate should apply.
        trace = get_sampled_trace(
            test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[("tag-a", "NOT-tag-a-val")]
        )
        assert_sampling_rate(trace, RC_SAMPLING_RATE)
        # Make sure `_dd.p.dm` is set to "-3"
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # A different tag key, value does not matter. Remote global rate should apply.
        trace = get_sampled_trace(
            test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[("not-tag-a", "tag-a-val")]
        )
        assert_sampling_rate(trace, RC_SAMPLING_RATE)
        # Make sure `_dd.p.dm` is set to "-3"
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # A span without the tag. Remote global rate should apply.
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[])
        assert_sampling_rate(trace, RC_SAMPLING_RATE)
        # Make sure `_dd.p.dm` is set to "-3"
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # RC config using dynamic sampling
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "dynamic_sampling_enabled": "true",
                "tracing_sampling_rules": [
                    {
                        "sample_rate": RC_SAMPLING_TAGS_RULE_RATE,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "tags": [{"key": "tag-a", "value_glob": "tag-a-val*"}],
                        "provenance": "customer",
                    },
                    {
                        "sample_rate": RC_SAMPLING_ADAPTIVE_RATE,
                        "service": "*",
                        "resource": "*",
                        "provenance": "dynamic",
                    },
                ],
            },
        )

        # A span with non-matching tags. Adaptive rate should apply.
        trace = get_sampled_trace(
            test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[("tag-a", "NOT-tag-a-val")]
        )
        assert_sampling_rate(trace, RC_SAMPLING_ADAPTIVE_RATE)
        # Make sure `_dd.p.dm` is set to "-12" (i.e., remote adaptive/dynamic sampling RULE_RATE)
        span = trace[0]
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-12"

    @bug(library="cpp", reason="unknown")
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_remote_sampling_rules_retention(self, library_env, test_agent, test_library):
        """Only the last set of sampling rules should be applied"""
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rules": [{"service": "svc*", "sample_rate": 0.5, "provenance": "customer"}],
            },
        )

        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rules": [{"service": "foo*", "sample_rate": 0.1, "provenance": "customer"}],
            },
        )

        trace = send_and_wait_trace(test_library, test_agent, name="test", service="foo")
        assert_sampling_rate(trace, 0.1)

        trace = send_and_wait_trace(test_library, test_agent, name="test2", service="svc")
        assert_sampling_rate(trace, 1)

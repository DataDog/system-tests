"""
Test configuration consistency for features across supported APM SDKs.
"""
import pytest
from utils import scenarios, features, context, bug, missing_feature
from utils.parametric.spec.trace import find_span_in_traces
import re

parametrize = pytest.mark.parametrize


def enable_tracing_enabled():
    env1 = {}
    env2 = {"DD_TRACE_ENABLED": "true"}
    return parametrize("library_env", [env1, env2])


def enable_tracing_disabled():
    env = {"DD_TRACE_ENABLED": "false"}
    return parametrize("library_env", [env])


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_TraceEnabled:
    @enable_tracing_enabled()
    def test_tracing_enabled(self, library_env, test_agent, test_library):
        assert library_env.get("DD_TRACE_ENABLED", "true") == "true"
        with test_library:
            with test_library.start_span("allowed"):
                pass
        test_agent.wait_for_num_traces(num=1, clear=True)
        assert (
            True
        ), "DD_TRACE_ENABLED=true and wait_for_num_traces does not raise an exception after waiting for 1 trace."

    @enable_tracing_disabled()
    def test_tracing_disabled(self, library_env, test_agent, test_library):
        assert library_env.get("DD_TRACE_ENABLED") == "false"
        with test_library:
            with test_library.start_span("allowed"):
                pass
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)
        assert (
            True
        ), "wait_for_num_traces raises an exception after waiting for 1 trace."  # wait_for_num_traces will throw an error if not received within 2 sec, so we expect to see an exception


@scenarios.parametric
@features.tracing_configuration_consistency
@bug(context.library == "php", reason="Can't create /parametric-tracer-logs at build step")
class Test_Config_TraceLogDirectory:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_ENABLED": "true", "DD_TRACE_LOG_DIRECTORY": "/parametric-tracer-logs"}]
    )
    def test_trace_log_directory_configured_with_existing_directory(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.start_span("allowed"):
                pass

        success, message = test_library.container_exec_run("ls /parametric-tracer-logs")
        assert success, message
        assert len(message.splitlines()) > 0, "No tracer logs detected"


def set_service_version_tags():
    env1 = {}
    env2 = {"DD_SERVICE": "test_service", "DD_VERSION": "5.2.0"}
    return parametrize("library_env", [env1, env2])


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging:
    @parametrize("library_env", [{}])
    def test_default_config(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="s1") as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1

        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["service"] != "version_test"
        assert "version" not in span["meta"]
        assert "env" not in span["meta"]

    # Assert that iff a span has service name set by DD_SERVICE, it also gets the version specified in DD_VERSION
    @parametrize("library_env", [{"DD_SERVICE": "version_test", "DD_VERSION": "5.2.0"}])
    def test_specific_version(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="s1") as s1:
                pass
            with test_library.start_span(name="s2", service="no dd_service") as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        assert len(traces) == 2

        span1 = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span1["service"] == "version_test"
        assert span1["meta"]["version"] == "5.2.0"

        span2 = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        assert span2["service"] == "no dd_service"
        assert "version" not in span2["meta"]

    @parametrize("library_env", [{"DD_ENV": "dev"}])
    def test_specific_env(self, library_env, test_agent, test_library):
        assert library_env.get("DD_ENV") == "dev"
        with test_library:
            with test_library.start_span(name="s1") as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1

        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["meta"]["env"] == "dev"


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_TraceAgentURL:
    # DD_TRACE_AGENT_URL is validated using the tracer configuration. This approach avoids the need to modify the setup file to create additional containers at the specified URL, which would be unnecessarily complex.
    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_AGENT_URL": "unix:///var/run/datadog/apm.socket",
                "DD_AGENT_HOST": "localhost",
                "DD_AGENT_PORT": "8126",
            }
        ],
    )
    def test_dd_trace_agent_unix_url_nonexistent(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        if context.library == "golang":
            match = re.match(r"^http://uds__var_run_datadog_apm.socket/.*", resp["dd_trace_agent_url"])
            assert match is not None, "trace_agent_url does not match expected pattern"
        else:
            assert resp["dd_trace_agent_url"] == "unix:///var/run/datadog/apm.socket"
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)

    # The DD_TRACE_AGENT_URL is validated using the tracer configuration. This approach avoids the need to modify the setup file to create additional containers at the specified URL, which would be unnecessarily complex.
    @parametrize(
        "library_env",
        [{"DD_TRACE_AGENT_URL": "http://random-host:9999/", "DD_AGENT_HOST": "localhost", "DD_AGENT_PORT": "8126"}],
    )
    def test_dd_trace_agent_http_url_nonexistent(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        # Go tracer reports `<url>/<protocol>/traces` as agent_url in startup log, so use a regex to match the expected suffix
        if context.library == "golang":
            match = re.match(r"^http://random-host:9999/.*", resp["dd_trace_agent_url"])
            assert match is not None, "trace_agent_url does not match expected pattern"
        else:
            assert resp["dd_trace_agent_url"] == "http://random-host:9999/"
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_RateLimit:
    # The default value of DD_TRACE_RATE_LIMIT is validated using the tracer configuration.
    # This approach avoids the need to create a new weblog endpoint that generates 100 traces per second,
    # which would be unreliable for testing and require significant effort for each tracer's weblog application.
    # The feature is mainly tested in the second test case, where the rate limit is set to 1 to ensure it works as expected.
    @parametrize("library_env", [{"DD_TRACE_SAMPLE_RATE": "1"}])
    def test_default_trace_rate_limit(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_rate_limit"] == "100"

    @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1", "DD_TRACE_SAMPLE_RATE": "1"}])
    def test_setting_trace_rate_limit(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="s1") as s1:
                pass
            with test_library.start_span(name="s2") as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
        trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]
        assert trace_0_sampling_priority == 2
        assert trace_1_sampling_priority == -1

    # DD_TRACE_RATE_LIMIT should have no effect if DD_TRACE_SAMPLE_RATE or DD_TRACE_SAMPLING_RULES is not set
    # @missing_feature(context.library == "python", reason="Not implemented")
    # @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1"}])
    # def test_trace_rate_limit_without_trace_sample_rate(self, library_env, test_agent, test_library):
    #     with test_library:
    #         with test_library.start_span(name="s1") as s1:
    #             pass
    #         with test_library.start_span(name="s2") as s2:
    #             pass

    #     traces = test_agent.wait_for_num_traces(2)
    #     trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
    #     trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]
    #     assert trace_0_sampling_priority == 2
    #     assert trace_1_sampling_priority == 2

"""
Test configuration consistency for features across supported APM SDKs.
"""
import pytest
from utils import scenarios, features

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
    return parametrize("library_env", [env1,env2])

@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging:
    @set_service_version_tags()
    def test_version_tag(self, library_env, test_agent, test_library):
        assert library_env.get("DD_SERVICE", "test_service") == "test_service"
        assert library_env.get("DD_VERSION", "5.2.0") == "5.2.0"
        
        with test_library:
            with test_library.start_span(name="s1"):
                pass
            with test_library.start_span(name="s2", service="no dd_service"):
                pass

        traces = test_agent.wait_for_num_traces(2)
        assert len(traces) == 2
        
        for trace in traces:
            for span in trace:
                if span['service'] == "test_service":
                    assert span['meta']['version'] == "5.2.0"
                else:
                    assert "version" not in span['meta']

"""
Test configuration consistency for functions among different languages for APM.
"""
import pytest

from utils import scenarios
parametrize = pytest.mark.parametrize

TEST_SERVICE = "test_service"
TEST_ENV = "test_env"
DEFAULT_ENVVARS = {
    "DD_SERVICE": TEST_SERVICE,
    "DD_ENV": TEST_ENV,
}

@scenarios.parametric
class TestTraceEnabled:
    
    @parametrize(
        "library_env", [{**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "true"},],
    )
    def test_tracing_enabled(self, library_env, test_agent, test_library):
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED") == "true"
        if trace_enabled_env:
            with test_library:
                with test_library.start_span("allowed"):
                    pass
            test_agent.wait_for_num_traces(num=1, clear=True)
            assert True, "DD_TRACE_ENABLED=true and wait_for_num_traces does not raise an exception after waiting for 1 trace."
        else:
            assert False, f"Assertion failed: expected {"true"}, but got {library_env.get("DD_TRACE_ENABLED")}"

    @parametrize(
        "library_env", [{**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "false"},],
    )
    def test_tracing_disabled(self, library_env, test_agent, test_library):
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED") == "false"
        if trace_enabled_env:
            with test_library:
                with test_library.start_span("allowed"):
                    pass
            with pytest.raises(ValueError):
                test_agent.wait_for_num_traces(num=1, clear=True)

            assert True, "DD_TRACE_ENABLED=true and wait_for_num_traces does not raise an exception after waiting for 1 trace." #wait_for_num_traces will throw an error if not received within 2 sec

        else:
            assert False, f"Assertion failed: expected {"false"}, but got {library_env.get("DD_TRACE_ENABLED")}"
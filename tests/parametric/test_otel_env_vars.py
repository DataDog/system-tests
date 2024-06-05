import pytest, os
from utils import missing_feature, context, scenarios, features


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Env_Vars:
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SERVICE": "service",
                "OTEL_SERVICE_NAME": "otel_service",
                "DD_TRACE_LOG_LEVEL": "error",  # Node uses DD_TRACE_LOG_LEVEL
                "DD_LOG_LEVEL": "error",
                "DD_TRACE_DEBUG": "false",
                "OTEL_LOG_LEVEL": "debug",
                "DD_TRACE_SAMPLE_RATE": "0.5",
                "OTEL_TRACES_SAMPLER": "traceidratio",
                "OTEL_TRACES_SAMPLER_ARG": "0.1",
                "DD_TRACE_ENABLED": "true",
                "OTEL_TRACES_EXPORTER": "none",
                "DD_RUNTIME_METRICS_ENABLED": "true",
                "OTEL_METRICS_EXPORTER": "none",
                "DD_TAGS": "foo:bar,baz:qux",
                "OTEL_RESOURCE_ATTRIBUTES": "foo=otel_bar,baz=otel_qux",
                "DD_TRACE_PROPAGATION_STYLE_INJECT": "b3,tracecontext",
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "b3,tracecontext",
                "OTEL_PROPAGATORS": "datadog,tracecontext",
                "DD_TRACE_OTEL_ENABLED": "false",
                "OTEL_SDK_DISABLED": "false",
            }
        ],
    )
    def test_dd_env_var_take_precedence(self, test_agent, test_library):
        resp = test_library.get_tracer_config()

        assert resp["dd_service"] == "service"
        assert resp["dd_log_level"] == "error"
        assert resp["dd_trace_sample_rate"] == 0.5
        assert resp["dd_trace_enabled"] == True
        assert resp["dd_runtime_metrics_enabled"] == True
        tags = resp["dd_tags"]
        assert tags.get("foo") == "bar"
        assert tags.get("baz") == "qux"
        assert resp["dd_trace_propagation_style"] == "b3,tracecontext"
        assert resp["dd_trace_debug"] == False
        if context.library != "nodejs":
            assert resp["dd_trace_otel_enabled"] == False  # node does not expose this variable in the config
            assert resp["dd_trace_sample_ignore_parent"] == True  # node does not implement this env variable

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SERVICE_NAME": "otel_service",
                "OTEL_LOG_LEVEL": "error",
                "OTEL_TRACES_SAMPLER": "traceidratio",
                "OTEL_TRACES_SAMPLER_ARG": "0.1",
                "OTEL_METRICS_EXPORTER": "none",
                "OTEL_RESOURCE_ATTRIBUTES": "foo=bar1,baz=qux1",
                "OTEL_PROPAGATORS": "b3,datadog",
                "OTEL_SDK_DISABLED": "true",
            }
        ],
    )
    def test_otel_env_vars_set(self, test_agent, test_library):
        resp = test_library.get_tracer_config()

        assert resp["dd_service"] == "otel_service"
        assert resp["dd_log_level"] == "error"
        assert resp["dd_trace_sample_rate"] == 0.1
        assert resp["dd_trace_enabled"] == True
        assert resp["dd_runtime_metrics_enabled"] == False
        tags = resp["dd_tags"]
        assert tags.get("foo") == "bar1"
        assert tags.get("baz") == "qux1"
        assert resp["dd_trace_propagation_style"] == "b3,datadog"
        if context.library != "nodejs":
            assert resp["dd_trace_otel_enabled"] == False
            assert resp["dd_trace_sample_ignore_parent"] == True

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1"
            }
        ],
    )
    def test_otel_attribute_mapping(self, test_agent, test_library):
        resp = test_library.get_tracer_config()

        assert resp["dd_service"] == "test2"
        assert resp["dd_env"] == "test1"
        assert resp["dd_version"] == "5"
        tags = resp["dd_tags"]
        assert tags.get("foo") == "bar1"
        assert tags.get("baz") == "qux1"

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "always_on",}],
    )
    def test_otel_traces_always_on(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == True
        assert resp["dd_trace_sample_rate"] == 1.0

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "always_off",}],
    )
    def test_otel_traces_always_off(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == True
        assert resp["dd_trace_sample_rate"] == 0.0

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "traceidratio", "OTEL_TRACES_SAMPLER_ARG": "0.1"}],
    )
    def test_otel_traces_traceidratio(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == True
        assert resp["dd_trace_sample_rate"] == 0.1

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_always_on",}],
    )
    def test_otel_traces_parentbased_on(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == False
        assert resp["dd_trace_sample_rate"] == 1.0

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_always_off",}],
    )
    def test_otel_traces_parentbased_off(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == False
        assert resp["dd_trace_sample_rate"] == 0.0

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_traceidratio", "OTEL_TRACES_SAMPLER_ARG": "0.1"}],
    )
    def test_otel_traces_parentbased_ratio(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        if context.library != "nodejs":
            assert resp["dd_trace_sample_ignore_parent"] == False
        assert resp["dd_trace_sample_rate"] == 0.1

    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_EXPORTER": "none"}],
    )
    def test_otel_traces_exporter_none(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        assert resp["dd_trace_enabled"] == False

    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env", [{"OTEL_LOG_LEVEL": "debug"}],
    )
    def test_otel_log_level_to_debug_mapping(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        assert resp["dd_log_level"] == "debug"
        assert resp["dd_trace_debug"] == True

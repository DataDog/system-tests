import pytest, os
from utils import missing_feature, context, scenarios, features


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Env_Vars:
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
                "DD_TRACE_PROPAGATION_STYLE": "b3,tracecontext",
                "OTEL_PROPAGATORS": "datadog,tracecontext",
            }
        ],
    )
    def test_dd_env_var_take_precedence(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()

        assert resp["dd_service"] == "service"
        # Some languages do not support the DD_TRACE_LOG_LEVEL env var
        # Here we can test that the OTEL_LOG_LEVEL is not used
        assert resp["dd_log_level"] != "debug"
        assert float(resp["dd_trace_sample_rate"]) == 0.5
        assert resp["dd_trace_enabled"] == "true"
        assert resp["dd_runtime_metrics_enabled"]
        tags = resp["dd_tags"]
        assert "foo:bar" in tags
        assert "baz:qux" in tags
        assert "foo:otel_bar" not in tags
        assert "baz:otel_qux" not in tags
        assert resp["dd_trace_propagation_style"] == "b3,tracecontext"
        assert resp["dd_trace_debug"] == "false"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_SERVICE_NAME": "otel_service",
                "OTEL_TRACES_SAMPLER": "traceidratio",
                "OTEL_TRACES_SAMPLER_ARG": "0.1",
                "OTEL_METRICS_EXPORTER": "none",
                "OTEL_RESOURCE_ATTRIBUTES": "foo=bar1,baz=qux1",
                "OTEL_PROPAGATORS": "b3,tracecontext",
            }
        ],
    )
    def test_otel_env_vars_set(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()

        assert resp["dd_service"] == "otel_service"
        assert float(resp["dd_trace_sample_rate"]) == 0.1
        assert resp["dd_trace_enabled"] == "true"
        assert resp["dd_runtime_metrics_enabled"] == "false"
        tags = resp["dd_tags"]
        assert "foo:bar1" in tags
        assert "baz:qux1" in tags
        assert resp["dd_trace_propagation_style"] == "b3,tracecontext"

    @missing_feature(context.library == "python", reason="DD_LOG_LEVEL is not supported in Python")
    @pytest.mark.parametrize("library_env", [{"OTEL_LOG_LEVEL": "error"}])
    def test_otel_log_level_env(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()

        assert resp["dd_log_level"] == "error"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "OTEL_RESOURCE_ATTRIBUTES": "deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1"
            }
        ],
    )
    def test_otel_attribute_mapping(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()

        assert resp["dd_service"] == "test2"
        assert resp["dd_env"] == "test1"
        assert resp["dd_version"] == "5"
        tags = resp["dd_tags"]
        assert "foo:bar1" in tags
        assert "baz:qux1" in tags

    @pytest.mark.parametrize("library_env", [{"OTEL_TRACES_SAMPLER": "always_on",}])
    def test_otel_traces_always_on(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
            assert float(resp["dd_trace_sample_rate"]) == 1.0

    @pytest.mark.parametrize("library_env", [{"OTEL_TRACES_SAMPLER": "always_off",}])
    def test_otel_traces_always_off(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert float(resp["dd_trace_sample_rate"]) == 0.0

    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "traceidratio", "OTEL_TRACES_SAMPLER_ARG": "0.1"}],
    )
    def test_otel_traces_traceidratio(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert float(resp["dd_trace_sample_rate"]) == 0.1

    @pytest.mark.parametrize("library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_always_on",}])
    def test_otel_traces_parentbased_on(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert float(resp["dd_trace_sample_rate"]) == 1.0

    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_always_off",}],
    )
    def test_otel_traces_parentbased_off(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert float(resp["dd_trace_sample_rate"]) == 0.0

    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_traceidratio", "OTEL_TRACES_SAMPLER_ARG": "0.1"}],
    )
    def test_otel_traces_parentbased_ratio(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert float(resp["dd_trace_sample_rate"]) == 0.1

    @pytest.mark.parametrize(
        "library_env", [{"OTEL_TRACES_EXPORTER": "none"}],
    )
    def test_otel_traces_exporter_none(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_enabled"] == "false"

    @pytest.mark.parametrize("library_env", [{"OTEL_LOG_LEVEL": "debug"}])
    def test_otel_log_level_to_debug_mapping(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_debug"] == "true"
        # If dd_log_level is set it must be consistent with dd_trace_debug
        assert (resp["dd_log_level"] == "debug") or (resp["dd_log_level"] is None)

    @missing_feature(context.library == "nodejs", reason="this setting is not exposed in the Node.js config object")
    @missing_feature(
        context.library == "ruby", reason="does not support enabling opentelemetry via DD_TRACE_OTEL_ENABLED"
    )
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "OTEL_SDK_DISABLED": "true"}])
    def test_dd_trace_otel_enabled_takes_precedence(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_otel_enabled"] == "true"

    @missing_feature(context.library == "nodejs", reason="this setting is not exposed in the Node.js config object")
    @pytest.mark.parametrize("library_env", [{"OTEL_SDK_DISABLED": "true"}])
    def test_otel_sdk_disabled_set(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_otel_enabled"] == "false"

    @missing_feature(
        True, reason="dd_trace_sample_ignore_parent requires an RFC, this feature is not implemented in any language"
    )
    @pytest.mark.parametrize("library_env", [{"OTEL_TRACES_SAMPLER": "always_on"}])
    def test_dd_trace_sample_ignore_parent_true(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_sample_ignore_parent"] == "true"

    @missing_feature(
        True, reason="dd_trace_sample_ignore_parent requires an RFC, this feature is not implemented in any language"
    )
    @pytest.mark.parametrize("library_env", [{"OTEL_TRACES_SAMPLER": "parentbased_always_off"}])
    def test_dd_trace_sample_ignore_parent_false(self, test_agent, test_library):
        with test_library as t:
            resp = t.get_tracer_config()
        assert resp["dd_trace_sample_ignore_parent"] == "false"

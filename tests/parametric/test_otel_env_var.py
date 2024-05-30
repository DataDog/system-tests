
import pytest
from utils import missing_feature, context, scenarios

otel_env_var_to_internal_name_mapper = {
    'nodejs': {
        'OTEL_SERVICE_NAME': 'service',
        'OTEL_LOG_LEVEL': 'logLevel',
        'OTEL_TRACES_SAMPLER': 'sampleRate',
        #'OTEL_TRACES_EXPORTER' not exposed by the tracer
        'OTEL_METRICS_EXPORTER': 'runtimeMetrics',
        'OTEL_RESOURCE_ATTRIBUTES': 'tags',
        # both tracePropagationStyle.inject & tracePropagationStyle.extract set the value of OTEL_PROPAGATORS, so test either
        'OTEL_PROPAGATORS': 'tracePropagationStyle.inject',
        'OTEL_VERSION': 'version',
        'OTEL_ENV': 'env'
    }
}

def get_nested_dict_value(data, dot_key):
    keys = dot_key.split('.')
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return None
    return data

def get_config_value(config, language, env_var):
    return get_nested_dict_value(config, otel_env_var_to_internal_name_mapper[language][env_var])

@scenarios.parametric
class Test_Otel_Env_Var:
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SERVICE": 'service',
                "OTEL_SERVICE_NAME":  'otel_service',
                "DD_TRACE_LOG_LEVEL": 'error',
                "OTEL_LOG_LEVEL": 'debug',
                "DD_TRACE_SAMPLE_RATE": '0.5',
                "OTEL_TRACES_SAMPLER": 'traceidratio',
                "OTEL_TRACES_SAMPLER_ARG": '0.1',
                "DD_TRACE_ENABLED": 'true',
                "OTEL_TRACES_EXPORTER": 'none',
                "DD_RUNTIME_METRICS_ENABLED": 'true',
                "OTEL_METRICS_EXPORTER": 'none',
                "DD_TAGS": 'foo:bar,baz:qux',
                "OTEL_RESOURCE_ATTRIBUTES": 'foo=bar,baz=qux',
                "DD_TRACE_PROPAGATION_STYLE_INJECT": 'b3,tracecontext',
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": 'b3,tracecontext',
                "OTEL_PROPAGATORS": 'datadog,tracecontext'
            }
        ],
    )
    def test_dd_env_var_take_precedence(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']

        assert get_config_value(config, lang, 'OTEL_SERVICE_NAME') == 'service'
        assert get_config_value(config, lang, 'OTEL_LOG_LEVEL') == 'error'
        assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.5
        assert get_config_value(config, lang, 'OTEL_METRICS_EXPORTER') == True
        attr = get_config_value(config, lang, 'OTEL_RESOURCE_ATTRIBUTES')
        assert attr.get("foo") == "bar"
        assert attr.get("baz") == "qux"
        assert get_config_value(config, lang, 'OTEL_PROPAGATORS') == ['b3', 'tracecontext']

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
              'OTEL_SERVICE_NAME': 'otel_service',
              'OTEL_LOG_LEVEL': 'warn',
              'OTEL_TRACES_SAMPLER': 'traceidratio',
              'OTEL_TRACES_SAMPLER_ARG': '0.1',
              # when set this disables the tracer for Node and thus it cant return a config object
              # 'OTEL_TRACES_EXPORTER': 'none',
              'OTEL_METRICS_EXPORTER': 'none',
              'OTEL_RESOURCE_ATTRIBUTES': 'foo=bar1,baz=qux1',
              'OTEL_PROPAGATORS': 'b3,datadog'
            }
        ],
    )
    def test_otel_env_vars_set(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']
        
        assert get_config_value(config, lang, 'OTEL_SERVICE_NAME') == 'otel_service'
        assert get_config_value(config, lang, 'OTEL_LOG_LEVEL') == 'warn'
        assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.1
        assert get_config_value(config, lang, 'OTEL_METRICS_EXPORTER') == False
        attr = get_config_value(config, lang, 'OTEL_RESOURCE_ATTRIBUTES')
        assert attr.get("foo") == "bar1"
        assert attr.get("baz") == "qux1"
        assert get_config_value(config, lang, 'OTEL_PROPAGATORS') == ['b3', 'datadog']

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
              'OTEL_RESOURCE_ATTRIBUTES': 
                'deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1'
            }
        ],
    )
    def test_otel_attribute_mapping(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']

        assert get_config_value(config, lang, 'OTEL_SERVICE_NAME') == 'test2'
        assert get_config_value(config, lang, 'OTEL_ENV') == 'test1'
        assert get_config_value(config, lang, 'OTEL_VERSION') == '5'
        attr = get_config_value(config, lang, 'OTEL_RESOURCE_ATTRIBUTES')
        assert attr.get("foo") == "bar1"
        assert attr.get("baz") == "qux1"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
              'OTEL_TRACES_SAMPLER': 'always_on',
            }
        ],
    )
    def test_otel_traces_always_on(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']
        assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 1.0

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
              'OTEL_TRACES_SAMPLER': 'always_off',
            }
        ],
    )
    def test_otel_traces_always_off(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']
        assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.0

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
              'OTEL_TRACES_SAMPLER': 'traceidratio',
              'OTEL_TRACES_SAMPLER_ARG': '0.1'
            }
        ],
    )
    def test_otel_traces_traceidratio(self, test_agent, test_library):
        resp = test_library.get_tracer_config()
        config = resp['config']
        lang = resp['language']

        assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.1

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
      "library_env",
      [
          {
            'OTEL_TRACES_SAMPLER': 'parentbased_always_on',
          }
      ],
    )
    def test_otel_traces_parentbased_on(self, test_agent, test_library):
      resp = test_library.get_tracer_config()
      config = resp['config']
      lang = resp['language']

      assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 1.0

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
      "library_env",
      [
          {
            'OTEL_TRACES_SAMPLER': 'parentbased_always_off',
          }
      ],
    )
    def test_otel_traces_parentbased_off(self, test_agent, test_library):
      resp = test_library.get_tracer_config()
      config = resp['config']
      lang = resp['language']

      assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.0

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.11.0", reason="Implemented in v5.11.0, v4.35.0, &v3.56.0")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @pytest.mark.parametrize(
      "library_env",
      [
          {
            'OTEL_TRACES_SAMPLER': 'parentbased_traceidratio',
            'OTEL_TRACES_SAMPLER_ARG': '0.1'
          }
      ],
    )
    def test_otel_traces_parentbased_ratio(self, test_agent, test_library):
      resp = test_library.get_tracer_config()
      config = resp['config']
      lang = resp['language']

      assert get_config_value(config, lang, 'OTEL_TRACES_SAMPLER') == 0.1
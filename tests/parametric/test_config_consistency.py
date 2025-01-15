"""
Test configuration consistency for features across supported APM SDKs.
"""

from urllib.parse import urlparse
import pytest
from utils import scenarios, features, context, missing_feature, irrelevant, flaky
from utils.parametric.spec.trace import find_span_in_traces, find_only_span

parametrize = pytest.mark.parametrize


def enable_tracing_enabled():
    env1: dict = {}
    env2: dict = {"DD_TRACE_ENABLED": "true"}
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
            with test_library.dd_start_span("allowed"):
                pass
        assert test_agent.wait_for_num_traces(
            num=1
        ), "DD_TRACE_ENABLED=true and wait_for_num_traces does not raise an exception after waiting for 1 trace."

    @enable_tracing_disabled()
    def test_tracing_disabled(self, library_env, test_agent, test_library):
        assert library_env.get("DD_TRACE_ENABLED") == "false"
        with test_library:
            with test_library.dd_start_span("allowed"):
                pass
        with pytest.raises(ValueError) as e:
            test_agent.wait_for_num_traces(num=1)
        assert e.match(".*traces not available from test agent, got 0.*")


@scenarios.parametric
@features.tracing_configuration_consistency
@missing_feature(context.library == "php", reason="Can't create /parametric-tracer-logs at build step")
class Test_Config_TraceLogDirectory:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_ENABLED": "true", "DD_TRACE_LOG_DIRECTORY": "/parametric-tracer-logs"}]
    )
    def test_trace_log_directory_configured_with_existing_directory(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span("allowed"):
                pass

        success, message = test_library.container_exec_run("ls /parametric-tracer-logs")
        assert success, message
        assert len(message.splitlines()) > 0, "No tracer logs detected"


def set_service_version_tags():
    env1: dict = {}
    env2: dict = {"DD_SERVICE": "test_service", "DD_VERSION": "5.2.0"}
    return parametrize("library_env", [env1, env2])


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging:
    @parametrize("library_env", [{}])
    def test_default_config(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1") as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1

        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["service"] != "version_test"
        # in Node.js version can automatically be grabbed from the package.json on default, thus this test does not apply
        if test_library.lang != "nodejs":
            assert "version" not in span["meta"]
        assert "env" not in span["meta"]

    # Assert that iff a span has service name set by DD_SERVICE, it also gets the version specified in DD_VERSION
    @parametrize("library_env", [{"DD_SERVICE": "version_test", "DD_VERSION": "5.2.0"}])
    @missing_feature(context.library < "ruby@2.7.1-dev")
    def test_specific_version(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1") as s1:
                pass
            with test_library.dd_start_span(name="s2", service="no dd_service") as s2:
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
            with test_library.dd_start_span(name="s1") as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1

        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["meta"]["env"] == "dev"


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_TraceAgentURL:
    """
    DD_TRACE_AGENT_URL is validated using the tracer configuration.
    This approach avoids the need to modify the setup file to create additional containers at the specified URL,
    which would be unnecessarily complex.
    """

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
            resp = t.config()

        url = urlparse(resp["dd_trace_agent_url"])
        assert "unix" in url.scheme
        assert url.path == "/var/run/datadog/apm.socket"

    # The DD_TRACE_AGENT_URL is validated using the tracer configuration. This approach avoids the need to modify the setup file to create additional containers at the specified URL, which would be unnecessarily complex.
    @parametrize(
        "library_env",
        [{"DD_TRACE_AGENT_URL": "http://random-host:9999/", "DD_AGENT_HOST": "localhost", "DD_AGENT_PORT": "8126"}],
    )
    def test_dd_trace_agent_http_url_nonexistent(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()

        url = urlparse(resp["dd_trace_agent_url"])
        assert url.scheme == "http"
        assert url.hostname == "random-host"
        assert url.port == 9999

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_AGENT_URL": "http://[::1]:5000",
                "DD_AGENT_HOST": "localhost",
                "DD_AGENT_PORT": "8126",
            }
        ],
    )
    def test_dd_trace_agent_http_url_ipv6(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()

        url = urlparse(resp["dd_trace_agent_url"])
        assert url.scheme == "http"
        assert url.hostname == "::1"
        assert url.port == 5000

    @parametrize(
        "library_env",
        [
            {
                "DD_AGENT_HOST": "[::1]",
                "DD_AGENT_PORT": "5000",
            }
        ],
    )
    @missing_feature(context.library == "java", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "dotnet", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "golang", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "nodejs", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "python", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "ruby", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "php", reason="does not support ipv6 hostname")
    def test_dd_agent_host_ipv6(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()

        url = urlparse(resp["dd_trace_agent_url"])
        assert url.scheme == "http"
        assert url.hostname == "::1"
        assert url.port == 5000


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
            resp = t.config()
        assert resp["dd_trace_rate_limit"] == "100"

    @irrelevant(
        context.library == "php",
        reason="PHP backfill model does not support strict two-trace limit, see test below for its behavior",
    )
    @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1", "DD_TRACE_SAMPLE_RATE": "1"}])
    @flaky(library="java", reason="APMAPI-908")
    def test_setting_trace_rate_limit_strict(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1") as s1:
                pass
            with test_library.dd_start_span(name="s2") as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
        trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]

        assert trace_0_sampling_priority == 2
        assert trace_1_sampling_priority == -1

    @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1"}])
    def test_trace_rate_limit_without_trace_sample_rate(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1") as s1:
                pass
            with test_library.dd_start_span(name="s2") as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
        trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]
        assert trace_0_sampling_priority == 1
        assert trace_1_sampling_priority == 1

    @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1", "DD_TRACE_SAMPLE_RATE": "1"}])
    def test_setting_trace_rate_limit(self, library_env, test_agent, test_library):
        # In PHP the rate limiter is continuously backfilled, i.e. if the rate limit is 2, and 0.2 seconds have passed, an allowance of 0.4 is backfilled.
        # As long as the amount of allowance is greater than zero, the request is allowed.
        # Meaning that if the rate limit is 2 and you do two requests within 0.2 seconds, the remaining limit is 0.4, allowing for one more request.
        # Then it gets negative and no more requests are allowed until 0.3 seconds later, when it's positive again.

        with test_library:
            # Generate three traces to demonstrate rate limiting in PHP's backfill model
            for i in range(3):
                with test_library.dd_start_span(name=f"s{i+1}") as span:
                    pass

        traces = test_agent.wait_for_num_traces(3)
        assert any(
            trace[0]["metrics"]["_sampling_priority_v1"] == -1 for trace in traces
        ), "Expected at least one trace to be rate-limited with sampling priority -1."


def tag_scenarios():
    env1: dict = {"DD_TAGS": "key1:value1,key2:value2"}
    env2: dict = {"DD_TAGS": "key1:value1 key2:value2"}
    env3: dict = {"DD_TAGS": "env:test aKey:aVal bKey:bVal cKey:"}
    env4: dict = {"DD_TAGS": "env:test,aKey:aVal,bKey:bVal,cKey:"}
    env5: dict = {"DD_TAGS": "env:test,aKey:aVal bKey:bVal cKey:"}
    env6: dict = {"DD_TAGS": "env:test     bKey :bVal dKey: dVal cKey:"}
    env7: dict = {"DD_TAGS": "env :test, aKey : aVal bKey:bVal cKey:"}
    env8: dict = {"DD_TAGS": "env:keyWithA:Semicolon bKey:bVal cKey"}
    env9: dict = {"DD_TAGS": "env:keyWith:  , ,   Lots:Of:Semicolons "}
    env10: dict = {"DD_TAGS": "a:b,c,d"}
    env11: dict = {"DD_TAGS": "a,1"}
    env12: dict = {"DD_TAGS": "a:b:c:d"}
    return parametrize("library_env", [env1, env2, env3, env4, env5, env6, env7, env8, env9, env10, env11, env12])


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_Tags:
    @tag_scenarios()
    def test_comma_space_tag_separation(self, library_env, test_agent, test_library):
        expected_local_tags = []
        if "DD_TAGS" in library_env:
            expected_local_tags = _parse_dd_tags(library_env["DD_TAGS"])
        with test_library:
            with test_library.dd_start_span(name="sample_span"):
                pass
        span = find_only_span(test_agent.wait_for_num_traces(1))
        for k, v in expected_local_tags:
            assert k in span["meta"]
            assert span["meta"][k] == v

    @parametrize(
        "library_env",
        [
            {
                "DD_TAGS": "service:random-service2,env:dev2,version:1.2.4",
                "DD_ENV": "dev",
                "DD_VERSION": "5.2.0",
                "DD_SERVICE": "random-service",
            }
        ],
    )
    def test_dd_service_override(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="sample_span"):
                pass
        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span["service"] == "random-service"
        assert "env" in span["meta"]
        assert span["meta"]["env"] == "dev"
        assert "version" in span["meta"]
        assert span["meta"]["version"] == "5.2.0"


def _parse_dd_tags(tags):
    result = []
    key_value_pairs = tags.split(",") if "," in tags else tags.split()  # First try to split by comma, then by space
    for pair in key_value_pairs:
        if ":" in pair:
            key, value = pair.split(":", 1)
        else:
            key, value = pair, ""
        key, value = key.strip(), value.strip()
        if key:
            result.append((key, value))
    return result


@scenarios.parametric
@features.tracing_configuration_consistency
class Test_Config_Dogstatsd:
    @parametrize(
        "library_env", [{"DD_AGENT_HOST": "localhost"}]
    )  # Adding DD_AGENT_HOST because some SDKs use DD_AGENT_HOST to set the dogstatsd host if unspecified
    def test_dogstatsd_default(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_host"] == "localhost"
        assert resp["dd_dogstatsd_port"] == "8125"

    @parametrize("library_env", [{"DD_DOGSTATSD_HOST": "192.168.10.1"}])
    def test_dogstatsd_custom_ip_address(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_host"] == "192.168.10.1"

    @parametrize("library_env", [{"DD_DOGSTATSD_HOST": "randomname"}])
    def test_dogstatsd_custom_hostname(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_host"] == "randomname"

    @parametrize("library_env", [{"DD_DOGSTATSD_PORT": "8150"}])
    def test_dogstatsd_custom_port(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_port"] == "8150"

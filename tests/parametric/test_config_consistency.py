"""Test configuration consistency for features across supported APM SDKs."""

from urllib.parse import urlparse

import pytest
import yaml
from utils import scenarios, features, context, missing_feature, irrelevant, flaky, bug, rfc, incomplete_test_app
from .conftest import StableConfigWriter
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
@features.trace_enablement
class Test_Config_TraceEnabled:
    @enable_tracing_enabled()
    def test_tracing_enabled(self, library_env, test_agent, test_library):
        assert library_env.get("DD_TRACE_ENABLED", "true") == "true"
        with test_library, test_library.dd_start_span("allowed"):
            pass
        assert test_agent.wait_for_num_traces(
            num=1
        ), "DD_TRACE_ENABLED=true and wait_for_num_traces does not raise an exception after waiting for 1 trace."

    @enable_tracing_disabled()
    def test_tracing_disabled(self, library_env, test_agent, test_library):
        assert library_env.get("DD_TRACE_ENABLED") == "false"
        with test_library, test_library.dd_start_span("allowed"):
            pass
        with pytest.raises(ValueError) as e:
            test_agent.wait_for_num_traces(num=1)
        assert e.match(".*traces not available from test agent, got 0.*")


@scenarios.parametric
@features.trace_log_directory
@missing_feature(context.library == "php", reason="Can't create /parametric-tracer-logs at build step")
class Test_Config_TraceLogDirectory:
    @pytest.mark.parametrize(
        "library_env", [{"DD_TRACE_ENABLED": "true", "DD_TRACE_LOG_DIRECTORY": "/parametric-tracer-logs"}]
    )
    def test_trace_log_directory_configured_with_existing_directory(self, library_env, test_agent, test_library):
        with test_library, test_library.dd_start_span("allowed"):
            pass

        success, message = test_library.container_exec_run("ls /parametric-tracer-logs")
        assert success, message
        assert len(message.splitlines()) > 0, "No tracer logs detected"


def set_service_version_tags():
    env1: dict = {}
    env2: dict = {"DD_SERVICE": "test_service", "DD_VERSION": "5.2.0"}
    return parametrize("library_env", [env1, env2])


@scenarios.parametric
@features.unified_service_tagging
class Test_Config_UnifiedServiceTagging:
    @parametrize("library_env", [{}])
    def test_default_config(self, library_env, test_agent, test_library):
        with test_library, test_library.dd_start_span(name="s1") as s1:
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
        with test_library, test_library.dd_start_span(name="s1") as s1:
            pass

        traces = test_agent.wait_for_num_traces(1)
        assert len(traces) == 1

        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["meta"]["env"] == "dev"


@scenarios.parametric
@features.trace_agent_connection
class Test_Config_TraceAgentURL:
    """DD_TRACE_AGENT_URL is validated using the tracer configuration.
    This approach avoids the need to modify the setup file to create additional containers at the specified URL,
    which would be unnecessarily complex.
    """

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_AGENT_URL": "unix:///var/run/datadog/apm.socket",
                "DD_AGENT_HOST": "localhost",
                "DD_TRACE_AGENT_PORT": "8126",
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
        [
            {
                "DD_TRACE_AGENT_URL": "http://random-host:9999/",
                "DD_AGENT_HOST": "localhost",
                "DD_TRACE_AGENT_PORT": "8126",
            }
        ],
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
                "DD_TRACE_AGENT_PORT": "8126",
            }
        ],
    )
    @missing_feature(context.library == "ruby", reason="does not support ipv6")
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
                "DD_TRACE_AGENT_URL": "",  # Empty string passed to make sure conftest.py does not set trace agent url
                "DD_AGENT_HOST": "[::1]",
                "DD_TRACE_AGENT_PORT": "5000",
            }
        ],
    )
    @missing_feature(context.library == "ruby", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "php", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "golang", reason="does not support ipv6 hostname")
    @missing_feature(context.library == "python", reason="does not support ipv6 hostname")
    def test_dd_agent_host_ipv6(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()

        url = urlparse(resp["dd_trace_agent_url"])
        assert url.scheme == "http"
        assert url.hostname == "::1"
        assert url.port == 5000


@scenarios.parametric
@features.trace_rate_limiting
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
    @parametrize(
        "library_env",
        [{"DD_TRACE_RATE_LIMIT": "1", "DD_TRACE_SAMPLE_RATE": "1", "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":1}]'}],
    )
    @flaky(library="java", reason="APMAPI-908")
    @bug(context.library == "golang", reason="APMAPI-1030")
    def test_setting_trace_rate_limit_strict(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1"):
                pass
            with test_library.dd_start_span(name="s2"):
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
        trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]

        assert trace_0_sampling_priority == 2
        assert trace_1_sampling_priority == -1

    @parametrize("library_env", [{"DD_TRACE_RATE_LIMIT": "1"}])
    def test_trace_rate_limit_without_trace_sample_rate(self, library_env, test_agent, test_library):
        with test_library:
            with test_library.dd_start_span(name="s1"):
                pass
            with test_library.dd_start_span(name="s2"):
                pass

        traces = test_agent.wait_for_num_traces(2)
        trace_0_sampling_priority = traces[0][0]["metrics"]["_sampling_priority_v1"]
        trace_1_sampling_priority = traces[1][0]["metrics"]["_sampling_priority_v1"]
        assert trace_0_sampling_priority == 1
        assert trace_1_sampling_priority == 1

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_RATE_LIMIT": "1",
                "DD_TRACE_SAMPLE_RATE": "1",
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":1}]',
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
            }
        ],
    )
    def test_setting_trace_rate_limit(self, library_env, test_agent, test_library):
        # In PHP the rate limiter is continuously backfilled, i.e. if the rate limit is 2, and 0.2 seconds have passed, an allowance of 0.4 is backfilled.
        # As long as the amount of allowance is greater than zero, the request is allowed.
        # Meaning that if the rate limit is 2 and you do two requests within 0.2 seconds, the remaining limit is 0.4, allowing for one more request.
        # Then it gets negative and no more requests are allowed until 0.3 seconds later, when it's positive again.

        with test_library:
            # Generate three traces to demonstrate rate limiting in PHP's backfill model
            for i in range(3):
                with test_library.dd_start_span(name=f"s{i+1}"):
                    pass

        traces = test_agent.wait_for_num_traces(3)
        assert any(
            trace[0]["metrics"]["_sampling_priority_v1"] == -1 for trace in traces
        ), "Expected at least one trace to be rate-limited with sampling priority -1."


tag_scenarios: dict = {
    "key1:value1,key2:value2": [("key1", "value1"), ("key2", "value2")],
    "key1:value1 key2:value2": [("key1", "value1"), ("key2", "value2")],
    "env:test aKey:aVal bKey:bVal cKey:": [("env", "test"), ("aKey", "aVal"), ("bKey", "bVal"), ("cKey", "")],
    "env:test,aKey:aVal,bKey:bVal,cKey:": [("env", "test"), ("aKey", "aVal"), ("bKey", "bVal"), ("cKey", "")],
    "env:test,aKey:aVal bKey:bVal cKey:": [("env", "test"), ("aKey", "aVal bKey:bVal cKey:")],
    "env:test     bKey :bVal dKey: dVal cKey:": [
        ("env", "test"),
        ("bKey", ""),
        ("dKey", ""),
        ("dVal", ""),
        ("cKey", ""),
    ],
    "env :test, aKey : aVal bKey:bVal cKey:": [("env", "test"), ("aKey", "aVal bKey:bVal cKey:")],
    "env:keyWithA:Semicolon bKey:bVal cKey": [("env", "keyWithA:Semicolon"), ("bKey", "bVal"), ("cKey", "")],
    "env:keyWith:  , ,   Lots:Of:Semicolons ": [("env", "keyWith:"), ("Lots", "Of:Semicolons")],
    "a:b,c,d": [("a", "b"), ("c", ""), ("d", "")],
    "a,1": [("a", ""), ("1", "")],
    "a:b:c:d": [("a", "b:c:d")],
}


@scenarios.parametric
@features.trace_global_tags
class Test_Config_Tags:
    @parametrize(
        "library_env", [{"DD_TRACE_EXPERIMENTAL_FEATURES_ENABLED": "all", "DD_TAGS": key} for key in tag_scenarios]
    )
    def test_comma_space_tag_separation(self, library_env, test_agent, test_library):
        expected_local_tags = []
        if "DD_TAGS" in library_env:
            expected_local_tags = tag_scenarios[library_env["DD_TAGS"]]
        with test_library, test_library.dd_start_span(name="sample_span"):
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
        with test_library, test_library.dd_start_span(name="sample_span"):
            pass
        span = find_only_span(test_agent.wait_for_num_traces(1))
        assert span["service"] == "random-service"
        assert "env" in span["meta"]
        assert span["meta"]["env"] == "dev"
        assert "version" in span["meta"]
        assert span["meta"]["version"] == "5.2.0"


@scenarios.parametric
@features.dogstatsd_agent_connection
class Test_Config_Dogstatsd:
    @parametrize(
        "library_env", [{"DD_AGENT_HOST": "localhost"}]
    )  # Adding DD_AGENT_HOST because some SDKs use DD_AGENT_HOST to set the dogstatsd host if unspecified
    @incomplete_test_app(
        reason="PHP parameteric app can not access the dogstatsd default values, this logic is internal to the tracer"
    )
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

    @parametrize("library_env", [{"DD_DOGSTATSD_HOST": "127.0.0.1"}])
    def test_dogstatsd_custom_hostname(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_host"] == "127.0.0.1"

    @parametrize("library_env", [{"DD_DOGSTATSD_PORT": "8150"}])
    def test_dogstatsd_custom_port(self, library_env, test_agent, test_library):
        with test_library as t:
            resp = t.config()
        assert resp["dd_dogstatsd_port"] == "8150"


SDK_DEFAULT_STABLE_CONFIG = {
    "dd_runtime_metrics_enabled": "false" if context.library != "java" else "true",
    "dd_profiling_enabled": "1"
    if context.library == "php"
    else "true"
    if context.library == "golang"
    else "false",  # Profiling is enabled as "1" by default in PHP if loaded. As for Go, the profiler must be started manually, so it is enabled by default when started
    "dd_data_streams_enabled": "false",
    "dd_logs_injection": {
        "ruby": "true",
        "java": "true",
        "golang": None,
        "python": "true",
        "nodejs": "true",
        "php": "true",
    }.get(context.library.name, "false"),  # Enabled by default in ruby
}


class QuotedStr(str):
    __slots__ = ()


def quoted_presenter(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


class CustomDumper(yaml.Dumper):
    pass


CustomDumper.add_representer(QuotedStr, quoted_presenter)


@scenarios.parametric
@features.stable_configuration_support
@rfc("https://docs.google.com/document/d/1MNI5d3g6R8uU3FEWf2e08aAsFcJDVhweCPMjQatEb0o")
class Test_Stable_Config_Default(StableConfigWriter):
    """Verify that stable config works as intended"""

    @pytest.mark.parametrize("library_env", [{}])
    @pytest.mark.parametrize(
        ("name", "apm_configuration_default", "expected"),
        [
            (
                "profiling",
                {"DD_PROFILING_ENABLED": True},
                {
                    **SDK_DEFAULT_STABLE_CONFIG,
                    "dd_profiling_enabled": "true",
                },
            ),
            (
                "runtime_metrics",
                {
                    "DD_RUNTIME_METRICS_ENABLED": True,
                },
                {
                    **SDK_DEFAULT_STABLE_CONFIG,
                    "dd_runtime_metrics_enabled": "true"
                    if context.library != "php"
                    else "false",  # PHP does not support runtime metrics
                },
            ),
            (
                "data_streams",
                {
                    "DD_DATA_STREAMS_ENABLED": True,
                },
                {
                    **SDK_DEFAULT_STABLE_CONFIG,
                    "dd_data_streams_enabled": "true"
                    if context.library not in ("php", "ruby")
                    else "false",  # PHP and Ruby do not support data streams
                },
            ),
            (
                "logs_injection",
                {
                    "DD_LOGS_INJECTION": context.library != "ruby",  # Ruby defaults logs injection to true
                },
                {
                    **SDK_DEFAULT_STABLE_CONFIG,
                    "dd_logs_injection": None
                    if context.library == "golang"
                    else "false"
                    if context.library in ("ruby", "php")
                    else "true",  # Logs injection is not supported in dd-trace-go and enabled by default in ruby
                },
            ),
        ],
        ids=lambda name: name,
    )
    @pytest.mark.parametrize(
        "path",
        [
            "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml",
            "/etc/datadog-agent/application_monitoring.yaml",
        ],
    )
    def test_default_config(
        self, test_agent, test_library, path, library_env, name, apm_configuration_default, expected
    ):
        with test_library:
            self.write_stable_config(
                {
                    "apm_configuration_default": apm_configuration_default,
                },
                path,
                test_library,
            )
            test_library.container_restart()
            config = test_library.config()
            assert expected.items() <= config.items()

    # @pytest.mark.parametrize("library_env", [{}])
    @pytest.mark.parametrize(
        "test",
        [
            {
                "apm_configuration_default": {
                    "DD_LOGS_INJECTION": context.library != "ruby",  # Ruby defaults logs injection to true
                    "DD_FOOBAR_ENABLED": "baz",
                },
                "expected": {
                    **SDK_DEFAULT_STABLE_CONFIG,
                    "dd_logs_injection": None
                    if context.library == "golang"
                    else "false"
                    if context.library == "ruby"
                    else "true",  # Logs injection is not supported in dd-trace-go and enabled by default in ruby
                },
            },
        ],
    )
    @pytest.mark.parametrize(
        "path",
        [
            "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml",
            "/etc/datadog-agent/application_monitoring.yaml",
        ],
    )
    def test_unknown_key_skipped(self, test_agent, test_library, path, library_env, test):
        with test_library:
            self.write_stable_config(
                {
                    "apm_configuration_default": test["apm_configuration_default"],
                    "extra_key": 123,
                },
                path,
                test_library,
            )
            test_library.container_restart()
            config = test_library.config()
            assert test["expected"].items() <= config.items()

    @pytest.mark.parametrize(
        "path",
        [
            "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml",
            "/etc/datadog-agent/application_monitoring.yaml",
        ],
    )
    def test_invalid_files(self, test_agent, test_library, path, library_env):
        with test_library:
            self.write_stable_config_content(
                "🤖 👾; 🤖\t\n\n --- `💣",
                path,
                test_library,
            )
            test_library.container_restart()
            config = test_library.config()
            assert SDK_DEFAULT_STABLE_CONFIG.items() <= config.items()

    @pytest.mark.parametrize(
        ("name", "local_cfg", "library_env", "fleet_cfg", "expected"),
        [
            (
                "fleet>local",
                {"DD_PROFILING_ENABLED": True},
                {},
                {"DD_PROFILING_ENABLED": False},
                {"dd_profiling_enabled": "false"},  # expected
            ),
            (
                "fleet>env",
                {},
                {"DD_PROFILING_ENABLED": True},
                {"DD_PROFILING_ENABLED": False},
                {"dd_profiling_enabled": "false"},  # expected
            ),
            pytest.param(
                "env>local",
                {"DD_PROFILING_ENABLED": True},
                {"DD_PROFILING_ENABLED": False},
                {},
                {"dd_profiling_enabled": "false"},  # expected
            ),
            (
                "orthogonal_priorities",
                {"DD_PROFILING_ENABLED": True, "DD_RUNTIME_METRICS_ENABLED": True},
                {"DD_ENV": "abc"},
                {"DD_PROFILING_ENABLED": False},
                {
                    "dd_profiling_enabled": "false",
                    "dd_runtime_metrics_enabled": "true"
                    if context.library != "php"
                    else "false",  # PHP does not support runtime metrics
                    "dd_env": "abc",
                },  # expected
            ),
        ],
        ids=lambda name: name,
    )
    def test_config_precedence(self, name, test_agent, test_library, local_cfg, library_env, fleet_cfg, expected):
        with test_library:
            self.write_stable_config(
                {
                    "apm_configuration_default": local_cfg,
                },
                "/etc/datadog-agent/application_monitoring.yaml",
                test_library,
            )
            self.write_stable_config(
                {
                    "apm_configuration_default": fleet_cfg,
                },
                "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml",
                test_library,
            )

            test_library.container_restart()
            config = test_library.config()
            assert expected.items() <= config.items(), format(
                "unexpected values for the following configurations: {}"
            ).format([k for k in config.keys() & expected.keys() if config[k] != expected[k]])

    @pytest.mark.parametrize("library_env", [{"STABLE_CONFIG_SELECTOR": "true", "DD_SERVICE": "not-my-service"}])
    @missing_feature(
        context.library in ["ruby", "cpp", "dotnet", "golang", "nodejs", "php", "python"],
        reason="UST stable config is phase 2",
    )
    def test_config_stable(self, library_env, test_agent, test_library):
        path = "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml"
        with test_library:
            self.write_stable_config(
                {
                    "apm_configuration_rules": [
                        {
                            "selectors": [
                                {
                                    "origin": "environment_variables",
                                    "key": "STABLE_CONFIG_SELECTOR",
                                    "operator": "equals",
                                    "matches": ["true"],
                                }
                            ],
                            "configuration": {"DD_SERVICE": "my-service"},
                        }
                    ]
                },
                path,
                test_library,
            )
            test_library.container_restart()
            config = test_library.config()
            assert (
                config["dd_service"] == "my-service"
            ), f"Service name is '{config["dd_service"]}' instead of 'my-service'"

    @missing_feature(
        context.library in ["ruby", "cpp", "dotnet", "golang", "nodejs", "php", "python"],
        reason="UST stable config is phase 2",
    )
    @pytest.mark.parametrize(
        "library_extra_command_arguments",
        [
            ["-Darg1=value"]
        ],  # Note: This test was written for Java, so if this arg is not compatible for other libs, we may need to dynamically set library_extra_command_arguments based on context.library.name
    )
    def test_process_arguments(self, library_env, test_agent, test_library):
        path = "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml"
        with test_library:
            config = {
                "apm_configuration_rules": [
                    {
                        "selectors": [
                            {
                                "origin": "process_arguments",
                                "key": "-Darg1",
                                "operator": "equals",
                                "matches": ["value"],
                            }
                        ],
                        "configuration": {"DD_SERVICE": QuotedStr("{{process_arguments['-Darg1']}}")},
                    }
                ]
            }
            # Use custom dumper for this specific test
            stable_config_content = yaml.dump(config, Dumper=CustomDumper)
            self.write_stable_config_content(stable_config_content, path, test_library)
            test_library.container_restart()
            config = test_library.config()
            assert config["dd_service"] == "value", f"Service name is '{config["dd_service"]}' instead of 'value'"

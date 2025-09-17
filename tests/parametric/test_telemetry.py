"""Test the telemetry that should be emitted from the library."""

import base64
import copy
import json
import time
from collections.abc import Generator
import uuid

import pytest

from .conftest import StableConfigWriter
from utils.telemetry_utils import TelemetryUtils
from utils import context, scenarios, rfc, features, missing_feature


telemetry_name_mapping = {
    "ssi_injection_enabled": {
        "nodejs": "DD_INJECTION_ENABLED",
        "python": "DD_INJECTION_ENABLED",
    },
    "ssi_forced_injection_enabled": {
        "nodejs": "DD_INJECT_FORCE",
        "python": "DD_INJECT_FORCE",
    },
    "trace_sample_rate": {
        "dotnet": "DD_TRACE_SAMPLE_RATE",
        "nodejs": "DD_TRACE_SAMPLE_RATE",
        "python": "DD_TRACE_SAMPLE_RATE",
        "ruby": "DD_TRACE_SAMPLE_RATE",
    },
    "logs_injection_enabled": {
        "dotnet": "DD_LOGS_INJECTION",
        "nodejs": "DD_LOG_INJECTION",  # TODO: rename to DD_LOGS_INJECTION in subsequent PR
        "python": "DD_LOGS_INJECTION",
        "php": "trace.logs_enabled",
        "ruby": "tracing.log_injection",
    },
    "trace_header_tags": {
        "dotnet": "DD_TRACE_HEADER_TAGS",
        "nodejs": "DD_TRACE_HEADER_TAGS",
        "python": "DD_TRACE_HEADER_TAGS",
    },
    "trace_tags": {"dotnet": "DD_TAGS", "nodejs": "DD_TAGS", "python": "DD_TAGS"},
    "trace_enabled": {
        "dotnet": "DD_TRACE_ENABLED",
        "nodejs": "tracing",
        "python": "DD_TRACE_ENABLED",
        "ruby": "tracing.enabled",
    },
    "profiling_enabled": {
        "dotnet": "DD_PROFILING_ENABLED",
        "nodejs": "profiling.enabled",
        "python": "DD_PROFILING_ENABLED",
        "ruby": "profiling.enabled",
    },
    "appsec_enabled": {
        "dotnet": "DD_APPSEC_ENABLED",
        "nodejs": "appsec.enabled",
        "python": "DD_APPSEC_ENABLED",
        "ruby": "appsec.enabled",
    },
    "data_streams_enabled": {
        "dotnet": "DD_DATA_STREAMS_ENABLED",
        "nodejs": "dsmEnabled",
        "python": "DD_DATA_STREAMS_ENABLED",
    },
    "runtime_metrics_enabled": {
        "dotnet": "DD_RUNTIME_METRICS_ENABLED",
        "nodejs": "runtime.metrics.enabled",
        "python": "DD_RUNTIME_METRICS_ENABLED",
        "ruby": "runtime_metrics_enabled",
    },
    "dynamic_instrumentation_enabled": {
        "dotnet": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "nodejs": "dynamicInstrumentation.enabled",
        "python": "DD_DYNAMIC_INSTRUMENTATION_ENABLED",
        "php": "dynamic_instrumentation.enabled",
        "ruby": "dynamic_instrumentation.enabled",
    },
    "trace_debug_enabled": {
        "php": "trace.debug",
        "golang": "trace_debug",
    }
}


def _mapped_telemetry_name(context, apm_telemetry_name):
    if apm_telemetry_name in telemetry_name_mapping:
        mapped_name = telemetry_name_mapping[apm_telemetry_name].get(context.library.name)
        if mapped_name is not None:
            return mapped_name
    return apm_telemetry_name


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1In4TfVBbKEztLzYg4g0si5H56uzAbYB3OfqzRGP2xhg/edit")
@features.telemetry_app_started_event
class Test_Defaults:
    """Clients should use and report the same default values for features."""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                # Decrease the heartbeat/poll intervals to speed up the tests
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
            }
        ],
    )
    @missing_feature(context.library <= "python@2.16.0", reason="Reports configurations with unexpected names")
    @missing_feature(context.library >= "dotnet@3.22.0", reason="Disabled for migration, will be re-enabled shortly")
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass

        configuration_by_name = test_agent.wait_for_telemetry_configurations()
        # DSM is enabled by default in .NET, but not in other languages
        # see https://github.com/DataDog/dd-trace-dotnet/pull/7244 for more details
        if context.library >= "dotnet@3.22.0":
            data_streams_enabled = ("true", True)
        else:
            data_streams_enabled = ("false", False)

        for apm_telemetry_name, value in [
            ("trace_sample_rate", (1.0, None, "1.0")),
            ("logs_injection_enabled", ("false", False, "true", True, "structured")),
            ("trace_header_tags", ""),
            ("trace_tags", ""),
            ("trace_enabled", ("true", True)),
            ("profiling_enabled", ("false", False, None)),
            ("appsec_enabled", ("false", False, "inactive", None)),
            ("data_streams_enabled", data_streams_enabled),
        ]:
            # The Go tracer does not support logs injection.
            if context.library == "golang" and apm_telemetry_name in ("logs_injection_enabled",):
                continue
            if context.library == "cpp" and apm_telemetry_name in (
                "logs_injection_enabled",
                "trace_header_tags",
                "profiling_enabled",
                "appsec_enabled",
                "data_streams_enabled",
                "trace_sample_rate",
            ):
                continue
            if context.library == "python" and apm_telemetry_name in ("trace_sample_rate",):
                # DD_TRACE_SAMPLE_RATE is not supported in ddtrace>=3.x
                continue
            mapped_apm_telemetry_name = _mapped_telemetry_name(context, apm_telemetry_name)

            cfg_item = configuration_by_name.get(mapped_apm_telemetry_name)
            assert cfg_item is not None, f"Missing telemetry config item for '{mapped_apm_telemetry_name}'"
            if isinstance(value, tuple):
                assert (
                    cfg_item.get("value") in value
                ), f"Unexpected value for '{mapped_apm_telemetry_name}' ('{context.library}')"
            else:
                assert cfg_item.get("value") == value, f"Unexpected value for '{mapped_apm_telemetry_name}'"
            assert cfg_item.get("origin") == "default", f"Unexpected origin for '{mapped_apm_telemetry_name}'"


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o")
# To pass this test, ensure the lang you are testing has the necessary mapping in its config_rules.json file: https://github.com/DataDog/dd-go/tree/prod/trace/apps/tracer-telemetry-intake/telemetry-payload/static
# And replace the `missing_feature` marker under the lang's manifest file, for Test_Consistent_Configs
@features.telemetry_configurations_collected
class Test_Consistent_Configs:
    """Clients should report modifications to features."""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",  # Decrease the heartbeat/poll intervals to speed up the tests
                "DD_ENV": "dev",
                "DD_SERVICE": "service_test",
                "DD_VERSION": "5.2.0",
                "DD_TRACE_RATE_LIMIT": 10,
                "DD_TRACE_HEADER_TAGS": "User-Agent:my-user-agent,Content-Type.",
                "DD_TRACE_ENABLED": "true",
                "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": r"\d{3}-\d{2}-\d{4}",
                "DD_TRACE_LOG_DIRECTORY": "/some/temporary/directory",
                "DD_TRACE_CLIENT_IP_HEADER": "random-header-name",
                "DD_TRACE_HTTP_CLIENT_ERROR_STATUSES": "200-250",
                "DD_TRACE_HTTP_SERVER_ERROR_STATUSES": "250-200",
                "DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING": "false",
                # "DD_TRACE_AGENT_URL": "http://localhost:8126", # Don't want to configure this, since we need tracer <> agent connection to run these tests!
                # "DD_TRACE_<INTEGRATION>_ENABLED": "N/A", # Skipping because it is blocked by the telemetry intake & this information is already collected through other (non-config) telemetry.
            }
        ],
    )
    @missing_feature(context.library <= "python@2.16.0", reason="Reports configurations with unexpected names")
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass

        configuration_by_name = test_agent.wait_for_telemetry_configurations()
        # # Check that the tags name match the expected value
        assert configuration_by_name.get("DD_ENV", {}).get("value") == "dev"
        assert configuration_by_name.get("DD_SERVICE", {}).get("value") == "service_test"
        assert configuration_by_name.get("DD_VERSION", {}).get("value") == "5.2.0"
        assert configuration_by_name.get("DD_TRACE_RATE_LIMIT", {}).get("value") == "10"
        assert (
            configuration_by_name.get("DD_TRACE_HEADER_TAGS", {}).get("value")
            == "User-Agent:my-user-agent,Content-Type."
        )
        assert configuration_by_name.get("DD_TRACE_ENABLED", {}).get("value") is True
        assert (
            configuration_by_name.get("DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP", {}).get("value")
            == r"\d{3}-\d{2}-\d{4}"
        )
        assert configuration_by_name.get("DD_TRACE_CLIENT_IP_HEADER", {}).get("value") == "random-header-name"

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",  # Decrease the heartbeat/poll intervals to speed up the tests
                "DD_TRACE_LOG_DIRECTORY": "/some/temporary/directory",
                "DD_TRACE_HTTP_CLIENT_ERROR_STATUSES": "200-250",
                "DD_TRACE_HTTP_SERVER_ERROR_STATUSES": "250-200",
                "DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING": "false",
            }
        ],
    )
    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "python@2.16.0", reason="Reports configurations with unexpected names")
    def test_library_settings_2(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass

        configuration_by_name = test_agent.wait_for_telemetry_configurations()
        assert configuration_by_name.get("DD_TRACE_LOG_DIRECTORY", {}).get("value") == "/some/temporary/directory"
        assert configuration_by_name.get("DD_TRACE_HTTP_CLIENT_ERROR_STATUSES", {}).get("value") == "200-250"
        assert configuration_by_name.get("DD_TRACE_HTTP_SERVER_ERROR_STATUSES", {}).get("value") == "250-200"
        assert (
            configuration_by_name.get("DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING", {}).get("value") is False
        )  # No telemetry received, tested with Python and Java(also tried: DD_HTTP_CLIENT_TAG_QUERY_STRING)


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1In4TfVBbKEztLzYg4g0si5H56uzAbYB3OfqzRGP2xhg/edit")
@features.telemetry_app_started_event
class Test_Environment:
    """Clients should use and report the same environment values for features."""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                # Decrease the heartbeat/poll intervals to speed up the tests
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",
                "DD_TRACE_SAMPLE_RATE": "0.3",
                "DD_LOGS_INJECTION": "true",
                "DD_TRACE_HEADER_TAGS": "X-Header-Tag-1:header_tag_1,X-Header-Tag-2:header_tag_2",
                "DD_TAGS": "team:apm,component:web",
                "DD_TRACE_ENABLED": "true",
                # node.js DD_TRACING_ENABLED is equivalent to DD_TRACE_ENABLED in other libraries
                "DD_TRACING_ENABLED": "true",
                "DD_PROFILING_ENABLED": "false",
                "DD_APPSEC_ENABLED": "false",
                "DD_DATA_STREAMS_ENABLED": "false",
            }
        ],
    )
    @missing_feature(context.library <= "python@2.16.0", reason="Reports configurations with unexpected names")
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass

        configuration_by_name = test_agent.wait_for_telemetry_configurations()
        for apm_telemetry_name, environment_value in [
            ("trace_sample_rate", ("0.3", 0.3)),
            ("logs_injection_enabled", ("true", True)),
            (
                "trace_header_tags",
                (
                    "X-Header-Tag-1:header_tag_1,X-Header-Tag-2:header_tag_2",
                    "x-header-tag-1:header_tag_1,x-header-tag-2:header_tag_2",
                ),
            ),
            ("trace_tags", ("team:apm,component:web", "component:web,team:apm")),
            ("trace_enabled", ("true", True)),
            ("profiling_enabled", ("false", False)),
            ("appsec_enabled", ("false", False)),
            ("data_streams_enabled", ("false", False)),
        ]:
            # The Go tracer does not support logs injection.
            if context.library == "golang" and apm_telemetry_name in ("logs_injection_enabled",):
                continue
            if context.library == "cpp" and apm_telemetry_name in (
                "logs_injection_enabled",
                "trace_header_tags",
                "profiling_enabled",
                "appsec_enabled",
                "data_streams_enabled",
            ):
                continue
            if context.library == "python" and apm_telemetry_name in ("trace_sample_rate",):
                # DD_TRACE_SAMPLE_RATE is not supported in ddtrace>=3.x
                continue

            mapped_apm_telemetry_name = _mapped_telemetry_name(context, apm_telemetry_name)
            cfg_item = configuration_by_name.get(mapped_apm_telemetry_name)
            assert cfg_item is not None, f"Missing telemetry config item for '{mapped_apm_telemetry_name}'"
            if isinstance(environment_value, tuple):
                assert cfg_item.get("value") in environment_value, f"Unexpected value for '{mapped_apm_telemetry_name}'"
            else:
                assert cfg_item.get("value") == environment_value, f"Unexpected value for '{mapped_apm_telemetry_name}'"
            assert cfg_item.get("origin") == "env_var", f"Unexpected origin for '{mapped_apm_telemetry_name}'"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library == "python", reason="OTEL Sampling config is mapped to a different datadog config")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_AGENT_PORT": "agent.port",
                "DD_TRACE_OTEL_ENABLED": 1,
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": 1,
                "TIMEOUT": 1500,
                "DD_SERVICE": "service",
                "OTEL_SERVICE_NAME": "otel_service",
                "DD_TRACE_LOG_LEVEL": "error",
                "DD_LOG_LEVEL": "error",
                "OTEL_LOG_LEVEL": "debug",
                # python tracer supports DD_TRACE_SAMPLING_RULES not DD_TRACE_SAMPLE_RATE
                "DD_TRACE_SAMPLING_RULES": '[{"sample_rate":0.5}]',
                "DD_TRACE_SAMPLE_RATE": "0.5",
                "OTEL_TRACES_SAMPLER": "traceidratio",
                "OTEL_TRACES_SAMPLER_ARG": "0.1",
                "DD_TRACE_ENABLED": "true",
                "OTEL_TRACES_EXPORTER": "none",
                "DD_RUNTIME_METRICS_ENABLED": "true",
                "OTEL_METRICS_EXPORTER": "none",
                "DD_TAGS": "foo:bar,baz:qux",
                "OTEL_RESOURCE_ATTRIBUTES": "foo=bar1,baz=qux1",
                "DD_TRACE_PROPAGATION_STYLE": "datadog",
                "OTEL_PROPAGATORS": "datadog,tracecontext",
                "OTEL_LOGS_EXPORTER": "none",
                "OTEL_SDK_DISABLED": "false",
            }
        ],
    )
    def test_telemetry_otel_env_hiding(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("generate-metrics", wait_loops=400)
        payload = event["payload"]
        assert event["request_type"] == "generate-metrics"

        metrics = payload["series"]
        assert payload["namespace"] == "tracers"
        otel_hiding = [s for s in metrics if s["metric"] == "otel.env.hiding"]
        assert not [s for s in metrics if s["metric"] == "otel.env.invalid"]

        if context.library == "nodejs":
            ddlog_config = "dd_trace_log_level"
        elif context.library == "python":
            ddlog_config = "dd_trace_debug"
        else:
            ddlog_config = "dd_log_level"

        if context.library == "python":
            otelsampler_config = "otel_traces_sampler"
        else:
            otelsampler_config = "otel_traces_sampler_arg"

        if context.library == "python":
            ddsampling_config = "dd_trace_sampling_rules"
        else:
            ddsampling_config = "dd_trace_sample_rate"

        dd_to_otel_mapping: list[list[str | None]] = [
            ["dd_trace_propagation_style", "otel_propagators"],
            ["dd_service", "otel_service_name"],
            [ddsampling_config, "otel_traces_sampler"],
            ["dd_trace_enabled", "otel_traces_exporter"],
            ["dd_runtime_metrics_enabled", "otel_metrics_exporter"],
            ["dd_tags", "otel_resource_attributes"],
            ["dd_trace_otel_enabled", "otel_sdk_disabled"],
            [ddlog_config, "otel_log_level"],
            [ddsampling_config, otelsampler_config],
        ]

        for dd_config, otel_config in dd_to_otel_mapping:
            for metric in otel_hiding:
                if (
                    f"config_datadog:{dd_config}" in metric["tags"]
                    and f"config_opentelemetry:{otel_config}" in metric["tags"]
                ):
                    assert metric["points"][0][1] == 1
                    break
            else:
                pytest.fail(
                    f"Could not find a metric with {dd_config} and {otel_config} in otelHiding metrics: {otel_hiding}"
                )

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "ruby", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library == "python", reason="OTEL Sampling config is mapped to a different datadog config")
    @missing_feature(
        context.library == "nodejs", reason="does not collect otel_env.invalid metrics for otel_resource_attributes"
    )
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_TRACE_AGENT_PORT": "agent.port",
                "DD_TELEMETRY_HEARTBEAT_INTERVAL": 1,
                "TIMEOUT": 1500,
                "OTEL_SERVICE_NAME": "otel_service",
                "OTEL_LOG_LEVEL": "foo",
                "OTEL_TRACES_SAMPLER": "foo",
                "OTEL_TRACES_SAMPLER_ARG": "foo",
                "OTEL_TRACES_EXPORTER": "foo",
                "OTEL_METRICS_EXPORTER": "foo",
                "OTEL_RESOURCE_ATTRIBUTES": "foo",
                "OTEL_PROPAGATORS": "foo",
                "OTEL_LOGS_EXPORTER": "foo",
                "DD_TRACE_OTEL_ENABLED": None,
                "DD_TRACE_DEBUG": None,
                "OTEL_SDK_DISABLED": "foo",
            }
        ],
    )
    def test_telemetry_otel_env_invalid(self, library_env, test_agent, test_library):
        with test_library.dd_start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("generate-metrics", wait_loops=400)
        payload = event["payload"]
        assert event["request_type"] == "generate-metrics"

        metrics = payload["series"]

        assert payload["namespace"] == "tracers"

        otel_invalid = [s for s in metrics if s["metric"] == "otel.env.invalid"]

        if context.library == "nodejs":
            ddlog_config = "dd_trace_log_level"
        elif context.library == "python":
            ddlog_config = "dd_trace_debug"
        else:
            ddlog_config = "dd_log_level"

        if context.library == "python":
            otelsampler_config = "otel_traces_sampler"
        else:
            otelsampler_config = "otel_traces_sampler_arg"

        if context.library == "python":
            ddsampling_config = "dd_trace_sampling_rules"
        else:
            ddsampling_config = "dd_trace_sample_rate"

        dd_to_otel_mapping: list[list[str | None]] = [
            ["dd_trace_propagation_style", "otel_propagators"],
            [ddsampling_config, "otel_traces_sampler"],
            ["dd_trace_enabled", "otel_traces_exporter"],
            ["dd_runtime_metrics_enabled", "otel_metrics_exporter"],
            ["dd_tags", "otel_resource_attributes"],
            ["dd_trace_otel_enabled", "otel_sdk_disabled"],
            [ddlog_config, "otel_log_level"],
            [ddsampling_config, otelsampler_config],
            [None, "otel_logs_exporter"],
        ]

        for dd_config, otel_config in dd_to_otel_mapping:
            for metric in otel_invalid:
                if (
                    dd_config is None or f"config_datadog:{dd_config}" in metric["tags"]
                ) and f"config_opentelemetry:{otel_config}" in metric["tags"]:
                    assert metric["points"][0][1] == 1
                    break
            else:
                pytest.fail(
                    f"Could not find a metric with {dd_config} and {otel_config} in otel_invalid metrics: {otel_invalid}"
                )


@scenarios.parametric
@features.stable_configuration_support
@rfc("https://docs.google.com/document/d/1MNI5d3g6R8uU3FEWf2e08aAsFcJDVhweCPMjQatEb0o")
class Test_Stable_Configuration_Origin(StableConfigWriter):
    """Clients should report origin of configurations set by stable configuration faithfully"""

    @pytest.mark.parametrize(
        ("local_cfg", "library_env", "fleet_cfg", "expected_origin"),
        [
            (
                {
                    "DD_LOGS_INJECTION": True,
                    "DD_RUNTIME_METRICS_ENABLED": True,
                    "DD_DYNAMIC_INSTRUMENTATION_ENABLED": True,
                },
                {
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",  # Decrease the heartbeat/poll intervals to speed up the tests
                    "DD_RUNTIME_METRICS_ENABLED": True,
                },
                {"DD_LOGS_INJECTION": True},
                {
                    "logs_injection_enabled": "fleet_stable_config",
                    # Reporting for other origins than stable config is not completely implemented
                    # "runtime_metrics_enabled": "env_var",
                    "dynamic_instrumentation_enabled": "local_stable_config",
                },
            )
        ],
    )
    def test_stable_configuration_origin(
        self, local_cfg, library_env, fleet_cfg, test_agent, test_library, expected_origin
    ):
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
            # Sleep to ensure the telemetry events are sent with different timestamps
            time.sleep(1)
            test_library.container_restart()
            test_library.dd_start_span("test")

        configuration = test_agent.wait_for_telemetry_configurations()
        for cfg_name, origin in expected_origin.items():
            # The Go tracer does not support logs injection.
            if context.library == "golang" and cfg_name == "logs_injection_enabled":
                continue
            apm_telemetry_name = _mapped_telemetry_name(context, cfg_name)
            telemetry_item = configuration[apm_telemetry_name]
            assert telemetry_item["origin"] == origin, f"wrong origin for {telemetry_item}"
            assert telemetry_item["value"]

    @missing_feature(context.library == "nodejs", reason="Not implemented")
    @missing_feature(context.library <= "java@v1.53.0-SNAPSHOT", reason="Not implemented")
    @pytest.mark.parametrize(
        ("local_cfg", "library_env", "fleet_cfg", "fleet_config_id"),
        [
            (
                {"DD_DYNAMIC_INSTRUMENTATION_ENABLED": True},
                {
                    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1",  # Decrease the heartbeat/poll intervals to speed up the tests
                },
                {
                    "DD_TRACE_DEBUG": True,
                },
                "1231231231231",
            )
        ],
    )
    def test_stable_configuration_config_id(
        self, local_cfg, library_env, fleet_cfg, test_agent, test_library, fleet_config_id
    ):
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
                    "config_id": fleet_config_id,
                },
                "/etc/datadog-agent/managed/datadog-agent/stable/application_monitoring.yaml",
                test_library,
            )
            # Sleep to ensure the telemetry events are sent with different timestamps
            time.sleep(1)
            test_library.container_restart()
            test_library.dd_start_span("test")

        configurations = test_agent.wait_for_telemetry_configurations()
        print("TEST - CONFIGURATIONS    ", configurations)
        apm_telemetry_name = _mapped_telemetry_name(context, "trace_debug_enabled")
        telemetry_item = configurations[apm_telemetry_name]
        assert telemetry_item["origin"] == "fleet_stable_config"
        assert telemetry_item["config_id"] == fleet_config_id

        # Configuration set via local config should not have the config_id set
        apm_telemetry_name = _mapped_telemetry_name(context, "dynamic_instrumentation_enabled")
        telemetry_item = configurations[apm_telemetry_name]
        assert telemetry_item["origin"] == "local_stable_config"
        assert "config_id" not in telemetry_item or telemetry_item["config_id"] is None


DEFAULT_ENVVARS = {
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
}


@rfc("https://docs.google.com/document/d/14vsrCbnAKnXmJAkacX9I6jKPGKmxsq0PKUb3dfiZpWE/edit")
@scenarios.parametric
@features.telemetry_app_started_event
class Test_TelemetryInstallSignature:
    """This telemetry provides insights into how a library was installed."""

    @pytest.mark.parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_INSTRUMENTATION_INSTALL_TIME": str(int(time.time())),
                "DD_INSTRUMENTATION_INSTALL_TYPE": "k8s_single_step",
                "DD_INSTRUMENTATION_INSTALL_ID": str(uuid.uuid4()),
            },
        ],
    )
    def test_telemetry_event_propagated(self, library_env, test_agent, test_library):
        """Ensure the installation ID is included in the app-started telemetry event.

        The installation ID is generated as soon as possible in the APM installation process. It is propagated
        to the APM library via an environment variable. It is used to correlate telemetry events to help determine
        where installation issues are occurring.
        """

        # Some libraries require a first span for telemetry to be emitted.
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started", wait_loops=400)
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if body["request_type"] != "app-started":
                continue
            assert (
                "install_signature" in body["payload"]
            ), f"The install signature should be included in the telemetry event, got {body}"
            assert (
                "install_id" in body["payload"]["install_signature"]
            ), "The install id should be included in the telemetry event, got {}".format(
                body["payload"]["install_signature"]
            )
            assert body["payload"]["install_signature"]["install_id"] == library_env["DD_INSTRUMENTATION_INSTALL_ID"]
            assert (
                body["payload"]["install_signature"]["install_type"] == library_env["DD_INSTRUMENTATION_INSTALL_TYPE"]
            )
            assert (
                "install_type" in body["payload"]["install_signature"]
            ), "The install type should be included in the telemetry event, got {}".format(
                body["payload"]["install_signature"]
            )
            assert (
                body["payload"]["install_signature"]["install_time"] == library_env["DD_INSTRUMENTATION_INSTALL_TIME"]
            )
            assert (
                "install_time" in body["payload"]["install_signature"]
            ), "The install time should be included in the telemetry event, got {}".format(
                body["payload"]["install_signature"]
            )

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_telemetry_event_not_propagated(self, library_env, test_agent, test_library):
        """When instrumentation data is not propagated to the library
        The telemetry event should not contain telemetry as the Agent will add it when not present.
        """

        # Some libraries require a first span for telemetry to be emitted.
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started")
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if "payload" in body:
                assert (
                    "install_signature" not in body["payload"]
                ), f"The install signature should not be included in the telemetry event, got {body}"


@scenarios.parametric
@features.ssi_service_tracking
class Test_TelemetrySSIConfigs:
    """This telemetry provides insights into how a library was installed."""

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECTION_ENABLED": "tracer",
                },
                "tracer",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECTION_ENABLED": "service_test,profiler,false",
                },
                "service_test,profiler,false",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECTION_ENABLED": None,
                },
                None,
            ),
        ],
    )
    def test_injection_enabled(self, library_env, expected_value, test_agent, test_library):
        """Ensure SSI DD_INJECTION_ENABLED configuration is captured by a telemetry event."""

        # Some libraries require a first span for telemetry to be emitted.
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_configurations()

        configuration_by_name = test_agent.wait_for_telemetry_configurations(service="service_test")
        ssi_enabled_telemetry_name = _mapped_telemetry_name(context, "ssi_injection_enabled")
        inject_enabled = configuration_by_name.get(ssi_enabled_telemetry_name)
        assert inject_enabled, ",\n".join(configuration_by_name.keys())
        assert inject_enabled.get("value") == expected_value
        if expected_value is not None:
            assert inject_enabled.get("origin") == "env_var"

    @pytest.mark.parametrize(
        ("library_env", "expected_value"),
        [
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECT_FORCE": "true",
                },
                "true",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECT_FORCE": "false",
                },
                "false",
            ),
            (
                {
                    **DEFAULT_ENVVARS,
                    "DD_SERVICE": "service_test",
                    "DD_INJECT_FORCE": None,
                },
                "none",
            ),
        ],
    )
    def test_inject_force(self, library_env, expected_value, test_agent, test_library):
        """Ensure SSI DD_INJECT_FORCE configuration is captured by a telemetry event."""

        # Some libraries require a first span for telemetry to be emitted.
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_configurations()
        configuration_by_name = test_agent.wait_for_telemetry_configurations(service="service_test")
        # # Check that the tags name match the expected value
        inject_force_telemetry_name = _mapped_telemetry_name(context, "ssi_forced_injection_enabled")
        inject_force = configuration_by_name.get(inject_force_telemetry_name)
        assert inject_force, ",\n".join(configuration_by_name.keys())
        assert str(inject_force.get("value")).lower() == expected_value
        if expected_value != "none":
            assert inject_force.get("origin") == "env_var"

    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS, "DD_SERVICE": "service_test"}])
    def test_instrumentation_source_non_ssi(self, library_env, test_agent, test_library):
        # Some libraries require a first span for telemetry to be emitted.
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_configurations()
        configuration_by_name = test_agent.wait_for_telemetry_configurations(service="service_test")
        # Check that the tags name match the expected value
        instrumentation_source_telemetry_name = _mapped_telemetry_name(context, "instrumentation_source")
        instrumentation_source = configuration_by_name.get(instrumentation_source_telemetry_name)
        assert instrumentation_source, ",\n".join(configuration_by_name.keys())
        assert instrumentation_source.get("value").lower() != "ssi"


@rfc("https://docs.google.com/document/d/1xTLC3UEGNooZS0YOYp3swMlAhtvVn1aa639TGxHHYvg/edit")
@scenarios.parametric
@features.telemetry_app_started_event
class Test_TelemetrySCAEnvVar:
    """This telemetry entry has the value of DD_APPSEC_SCA_ENABLED in the library."""

    @staticmethod
    def flatten_message_batch(requests) -> Generator[dict, None, None]:
        for request in requests:
            body = json.loads(base64.b64decode(request["body"]))
            if body["request_type"] == "message-batch":
                for batch_payload in body["payload"]:
                    # create a fresh copy of the request for each payload in the
                    # message batch, as though they were all sent independently
                    copied = copy.deepcopy(body)
                    copied["request_type"] = batch_payload.get("request_type")
                    copied["payload"] = batch_payload.get("payload")
                    yield copied
            else:
                yield body

    @staticmethod
    def get_app_started_configuration_by_name(test_agent, test_library) -> dict | None:
        with test_library.dd_start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started", wait_loops=400)

        requests = test_agent.raw_telemetry(clear=True)
        bodies = list(Test_TelemetrySCAEnvVar.flatten_message_batch(requests))

        assert len(bodies) > 0, "There should be at least one telemetry event (app-started)"
        for body in bodies:
            if body["request_type"] != "app-started":
                continue

            assert (
                "configuration" in body["payload"]
            ), f"The configuration should be included in the telemetry event, got {body}"

            configuration = body["payload"]["configuration"]

            return {item["name"]: item for item in configuration}

        return None

    @pytest.mark.parametrize(
        ("library_env", "specific_libraries_support", "outcome_value"),
        [
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "true"}, False, True),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "True"}, ("python", "golang"), True),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "1"}, ("python", "golang"), True),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "false"}, False, False),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "False"}, ("python", "golang"), False),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "0"}, ("python", "golang"), False),
        ],
    )
    @missing_feature(context.library <= "python@2.16.0", reason="Converts boolean values to strings")
    def test_telemetry_sca_enabled_propagated(
        self, library_env, specific_libraries_support, outcome_value, test_agent, test_library
    ):
        if specific_libraries_support and context.library not in specific_libraries_support:
            pytest.xfail(f"{outcome_value} unsupported value for {context.library}")

        configuration_by_name = self.get_app_started_configuration_by_name(test_agent, test_library)
        assert configuration_by_name is not None, "Missing telemetry configuration"

        dd_appsec_sca_enabled = TelemetryUtils.get_dd_appsec_sca_enabled_str(context.library)

        cfg_appsec_enabled = configuration_by_name.get(dd_appsec_sca_enabled)
        assert cfg_appsec_enabled is not None, f"Missing telemetry config item for '{dd_appsec_sca_enabled}'"

        if context.library == "java":
            outcome_value = str(outcome_value).lower()
        assert cfg_appsec_enabled.get("value") == outcome_value

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    @missing_feature(
        context.library <= "python@2.16.0",
        reason="Does not report DD_APPSEC_SCA_ENABLED configuration if the default value is used",
    )
    def test_telemetry_sca_enabled_not_propagated(self, library_env, test_agent, test_library):
        configuration_by_name = self.get_app_started_configuration_by_name(test_agent, test_library)
        assert configuration_by_name is not None, "Missing telemetry configuration"

        dd_appsec_sca_enabled = TelemetryUtils.get_dd_appsec_sca_enabled_str(context.library)

        if context.library in ("java", "nodejs", "python"):
            cfg_appsec_enabled = configuration_by_name.get(dd_appsec_sca_enabled)
            assert cfg_appsec_enabled is not None, f"Missing telemetry config item for '{dd_appsec_sca_enabled}'"
            assert cfg_appsec_enabled.get("value") is None
        else:
            assert dd_appsec_sca_enabled not in configuration_by_name

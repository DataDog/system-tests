import pytest

from utils import context, rfc, scenarios


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1In4TfVBbKEztLzYg4g0si5H56uzAbYB3OfqzRGP2xhg/edit")
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
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("app-started")
        configuration = event["payload"]["configuration"]

        configuration_by_name = {item["name"]: item for item in configuration}
        for (apm_telemetry_name, value) in [
            ("trace_sample_rate", "1.0"),
            ("logs_injection_enabled", "false"),
            ("trace_header_tags", ""),
            ("trace_tags", ""),
            ("profiling_enabled", "false"),
            ("appsec_enabled", "false"),
            ("data_streams_enabled", "false"),
        ]:
            # The Go tracer does not support logs injection.
            if context.library == "golang" and apm_telemetry_name in ("logs_injection_enabled",):
                continue
            cfg_item = configuration_by_name.get(apm_telemetry_name)
            assert cfg_item is not None, "Missing telemetry config item for '{}'".format(apm_telemetry_name)
            assert cfg_item.get("value") == value, "Unexpected value for '{}'".format(apm_telemetry_name)
            assert cfg_item.get("origin") == "default", "Unexpected origin for '{}'".format(apm_telemetry_name)


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1In4TfVBbKEztLzYg4g0si5H56uzAbYB3OfqzRGP2xhg/edit")
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
                "DD_PROFILING_ENABLED": "false",
                "DD_APPSEC_ENABLED": "false",
                "DD_DATA_STREAMS_ENABLED": "false",
            }
        ],
    )
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("app-started")
        configuration = event["payload"]["configuration"]

        configuration_by_name = {item["name"]: item for item in configuration}
        for (apm_telemetry_name, environment_value) in [
            ("trace_sample_rate", "0.3"),
            ("logs_injection_enabled", "true"),
            ("trace_header_tags", "X-Header-Tag-1:header_tag_1,X-Header-Tag-2:header_tag_2"),
            ("trace_tags", "team:apm,component:web"),
            ("profiling_enabled", "false"),
            ("appsec_enabled", "false"),
            ("data_streams_enabled", "false"),
        ]:
            # The Go tracer does not support logs injection.
            if context.library == "golang" and apm_telemetry_name in ("logs_injection_enabled",):
                continue
            cfg_item = configuration_by_name.get(apm_telemetry_name)
            assert cfg_item is not None, "Missing telemetry config item for '{}'".format(apm_telemetry_name)
            assert cfg_item.get("value") == environment_value, "Unexpected value for '{}'".format(apm_telemetry_name)
            assert cfg_item.get("origin") == "env_var", "Unexpected origin for '{}'".format(apm_telemetry_name)

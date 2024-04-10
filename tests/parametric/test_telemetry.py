"""
Test the telemetry that should be emitted from the library.
"""
import base64
import json
import time
import uuid

import pytest

from utils import context, scenarios, rfc, features


telemetry_name_mapping = {
    "trace_sample_rate": {"dotnet": "DD_TRACE_SAMPLE_RATE", "nodejs": "DD_TRACE_SAMPLE_RATE"},
    "logs_injection_enabled": {"dotnet": "DD_LOGS_INJECTION", "nodejs": "DD_LOG_INJECTION"},
    "trace_header_tags": {"dotnet": "DD_TRACE_HEADER_TAGS", "nodejs": "DD_TRACE_HEADER_TAGS"},
    "trace_tags": {"dotnet": "DD_TAGS", "nodejs": "DD_TAGS"},
    "trace_enabled": {"dotnet": "DD_TRACE_ENABLED", "nodejs": "tracing"},
    "profiling_enabled": {"dotnet": "DD_PROFILING_ENABLED", "nodejs": "profiling.enabled"},
    "appsec_enabled": {"dotnet": "DD_APPSEC_ENABLED", "nodejs": "appsec.enabled"},
    "data_streams_enabled": {"dotnet": "DD_DATA_STREAMS_ENABLED", "nodejs": "dsmEnabled"},
}


def _mapped_telemetry_name(context, apm_telemetry_name):
    if apm_telemetry_name in telemetry_name_mapping:
        mapped_name = telemetry_name_mapping[apm_telemetry_name].get(context.library.library)
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
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("app-started")
        configuration = event["payload"]["configuration"]

        configuration_by_name = {item["name"]: item for item in configuration}
        for apm_telemetry_name, value in [
            ("trace_sample_rate", (1.0, None, "1.0")),
            ("logs_injection_enabled", ("false", False, "true", True)),
            ("trace_header_tags", ""),
            ("trace_tags", ""),
            ("trace_enabled", ("true", True)),
            ("profiling_enabled", ("false", False)),
            ("appsec_enabled", ("false", False, "inactive", None)),
            ("data_streams_enabled", ("false", False)),
        ]:
            # The Go tracer does not support logs injection.
            if context.library == "golang" and apm_telemetry_name in ("logs_injection_enabled",):
                continue
            if context.library == "cpp":
                unsupported_fields = (
                    "logs_injection_enabled",
                    "trace_header_tags",
                    "profiling_enabled",
                    "appsec_enabled",
                    "data_streams_enabled",
                    "trace_sample_rate",
                )
                if apm_telemetry_name in unsupported_fields:
                    continue
            apm_telemetry_name = _mapped_telemetry_name(context, apm_telemetry_name)

            cfg_item = configuration_by_name.get(apm_telemetry_name)
            assert cfg_item is not None, "Missing telemetry config item for '{}'".format(apm_telemetry_name)
            if isinstance(value, tuple):
                assert cfg_item.get("value") in value, "Unexpected value for '{}'".format(apm_telemetry_name)
            else:
                assert cfg_item.get("value") == value, "Unexpected value for '{}'".format(apm_telemetry_name)
            assert cfg_item.get("origin") == "default", "Unexpected origin for '{}'".format(apm_telemetry_name)


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
    def test_library_settings(self, library_env, test_agent, test_library):
        with test_library.start_span("test"):
            pass
        event = test_agent.wait_for_telemetry_event("app-started")
        configuration = event["payload"]["configuration"]

        configuration_by_name = {item["name"]: item for item in configuration}
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
            if context.library == "cpp":
                unsupported_fields = (
                    "logs_injection_enabled",
                    "trace_header_tags",
                    "profiling_enabled",
                    "appsec_enabled",
                    "data_streams_enabled",
                )
                if apm_telemetry_name in unsupported_fields:
                    continue

            apm_telemetry_name = _mapped_telemetry_name(context, apm_telemetry_name)
            cfg_item = configuration_by_name.get(apm_telemetry_name)
            assert cfg_item is not None, "Missing telemetry config item for '{}'".format(apm_telemetry_name)
            if isinstance(environment_value, tuple):
                assert cfg_item.get("value") in environment_value, "Unexpected value for '{}'".format(
                    apm_telemetry_name
                )
            else:
                assert cfg_item.get("value") == environment_value, "Unexpected value for '{}'".format(
                    apm_telemetry_name
                )
            assert cfg_item.get("origin") == "env_var", "Unexpected origin for '{}'".format(apm_telemetry_name)


DEFAULT_ENVVARS = {
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
}


@rfc("https://docs.google.com/document/d/14vsrCbnAKnXmJAkacX9I6jKPGKmxsq0PKUb3dfiZpWE/edit")
@scenarios.parametric
@features.telemetry_app_started_event
class Test_TelemetryInstallSignature:
    """
    This telemetry provides insights into how a library was installed.
    """

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
        with test_library.start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started")
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if body["request_type"] != "app-started":
                continue
            assert (
                "install_signature" in body["payload"]
            ), "The install signature should be included in the telemetry event, got {}".format(body)
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
        """
        When instrumentation data is not propagated to the library
            The telemetry event should not contain telemetry as the Agent will add it when not present.
        """

        # Some libraries require a first span for telemetry to be emitted.
        with test_library.start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started")
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if "payload" in body:
                assert (
                    "install_signature" not in body["payload"]
                ), "The install signature should not be included in the telemetry event, got {}".format(body)


@rfc("https://docs.google.com/document/d/1xTLC3UEGNooZS0YOYp3swMlAhtvVn1aa639TGxHHYvg/edit")
@scenarios.parametric
@features.telemetry_app_started_event
class Test_TelemetrySCAEnvVar:
    """
    This telemetry entry has the value of DD_APPSEC_SCA_ENABLED in the library.
    """

    @pytest.mark.parametrize(
        "library_env, outcome_value",
        [
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "true",}, "true"),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "True",}, "true"),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "1",}, "true"),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "false",}, "false"),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "False",}, "false"),
            ({**DEFAULT_ENVVARS, "DD_APPSEC_SCA_ENABLED": "0",}, "false"),
        ],
    )
    def test_telemetry_sca_enabled_propagated(self, library_env, outcome_value, test_agent, test_library):
        with test_library.start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started")
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if body["request_type"] != "app-started":
                continue
            assert (
                "configuration" in body["payload"]
            ), "The configuration should be included in the telemetry event, got {}".format(body)

            configuration = body["payload"]["configuration"]

            configuration_by_name = {item["name"]: item for item in configuration}

            DD_APPSEC_SCA_ENABLED = "DD_APPSEC_SCA_ENABLED"
            if context.library in ("dotnet", "jvm", "nodejs"):
                DD_APPSEC_SCA_ENABLED = "appsec.sca.enabled"
            elif context.library == "php":
                DD_APPSEC_SCA_ENABLED = "appsec.sca_enabled"

            cfg_appsec_enabled = configuration_by_name.get(DD_APPSEC_SCA_ENABLED)
            assert cfg_appsec_enabled is not None, "Missing telemetry config item for '{}'".format(apm_telemetry_name)
            assert cfg_appsec_enabled.get("value") == outcome_value

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_telemetry_sca_enabled_not_propagated(self, library_env, test_agent, test_library):
        with test_library.start_span("first_span"):
            pass

        test_agent.wait_for_telemetry_event("app-started")
        requests = test_agent.raw_telemetry(clear=True)
        assert len(requests) > 0, "There should be at least one telemetry event (app-started)"
        for req in requests:
            body = json.loads(base64.b64decode(req["body"]))
            if body["request_type"] != "app-started":
                continue
            assert (
                "configuration" in body["payload"]
            ), "The configuration should be included in the telemetry event, got {}".format(body)

            configuration = body["payload"]["configuration"]

            configuration_by_name = {item["name"]: item for item in configuration}

            DD_APPSEC_SCA_ENABLED = "DD_APPSEC_SCA_ENABLED"
            if context.library in ("dotnet", "jvm", "nodejs"):
                DD_APPSEC_SCA_ENABLED = "appsec.sca.enabled"
            elif context.library == "php":
                DD_APPSEC_SCA_ENABLED = "appsec.sca_enabled"

            assert DD_APPSEC_SCA_ENABLED not in configuration_by_name.keys()

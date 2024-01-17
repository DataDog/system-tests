"""
Test the telemetry that should be emitted from the library.
"""
import base64
import json
import time
import uuid

import pytest

from utils import context, scenarios, rfc, features


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

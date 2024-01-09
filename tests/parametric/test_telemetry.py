"""
Test the telemetry that should be emitted from the library.
"""
import base64
import json
import time
import uuid

import pytest

from utils import scenarios, rfc


DEFAULT_ENVVARS = {
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
}


@rfc("https://docs.google.com/document/d/14vsrCbnAKnXmJAkacX9I6jKPGKmxsq0PKUb3dfiZpWE/edit")
@scenarios.parametric
class Test_First_Trace_Telemetry:
    """
    Test the time-to-first-trace telemetry that should be emitted from the library.

    The time-to-first trace telemetry provides insight into how long it takes for the library to emit its first trace
    from the time of Agent installation.
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
            assert "install_signature" in body["payload"], "The install signature should be included in the telemetry event, got {}".format(body)
            assert "install_id" in body["payload"]["install_signature"], "The install id should be included in the telemetry event, got {}".format(body["payload"]["install_signature"])
            assert body["payload"]["install_signature"]["install_id"] == library_env["DD_INSTRUMENTATION_INSTALL_ID"]
            assert body["payload"]["install_signature"]["install_type"] == library_env["DD_INSTRUMENTATION_INSTALL_TYPE"]
            assert "install_type" in body["payload"]["install_signature"], "The install type should be included in the telemetry event, got {}".format(body["payload"]["install_signature"])
            assert body["payload"]["install_signature"]["install_time"] == library_env["DD_INSTRUMENTATION_INSTALL_TIME"]
            assert "install_time" in body["payload"]["install_signature"], "The install time should be included in the telemetry event, got {}".format(body["payload"]["install_signature"])


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
            assert (
                "DD-Agent-Install-Id" not in req["headers"]
            ), "The install id should not be included when not propagated, got headers {}".format(req["headers"])
            assert (
                "DD-Agent-Install-Type" not in req["headers"]
            ), "The install type should not be included when not propagated, got headers {}".format(req["headers"])
            assert (
                "DD-Agent-Install-Time" not in req["headers"]
            ), "The install time should not be included when not propagated, got headers {}".format(req["headers"])

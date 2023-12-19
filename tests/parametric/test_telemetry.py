"""
Test the telemetry that should be emitted from the library.
"""
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
    def test_first_trace_telemetry_propagated(self, library_env, test_agent, test_library):
        """
        When instrumentation data is propagated to the library
            The first trace should contain telemetry for calculating how long it took to emit the first trace.
        """
        with test_library.start_span("first_span"):
            with test_library.start_span("second_span"):
                pass
        with test_library.start_span("third_span"):
            pass

        traces = test_agent.wait_for_num_traces(num=2)

        assert (
            "_dd.install.time" in traces[0][0]["meta"]
        ), "The installation time should be included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]
        )
        install_time = traces[0][0]["meta"]["_dd.install.time"]
        assert isinstance(install_time, str), "Install time should be string"
        assert (
            install_time == library_env["DD_INSTRUMENTATION_INSTALL_TIME"]
        ), "Install time should be the propagated value, got {}".format(install_time)

        assert (
            "_dd.install.type" in traces[0][0]["meta"]
        ), "The installation type should included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]
        )
        install_type = traces[0][0]["meta"]["_dd.install.type"]
        assert install_type == "k8s_single_step", "Install type should be the propagated value"

        assert (
            "_dd.install.id" in traces[0][0]["meta"]
        ), "The installation id should included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]
        )
        install_id = traces[0][0]["meta"]["_dd.install.id"]
        assert (
            install_id == library_env["DD_INSTRUMENTATION_INSTALL_ID"]
        ), "Install id should be the propagated value, got {}".format(install_id)

        # Ensure other spans do not have the telemetry
        for span in (traces[0][1], traces[1][0]):
            assert "_dd.install.time" not in span["meta"]
            assert "_dd.install.type" not in span["meta"]
            assert "_dd.install.id" not in span["meta"]

    @pytest.mark.parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_first_trace_telemetry_not_propagated(self, library_env, test_agent, test_library):
        """
        When instrumentation data is not propagated to the library
            The first trace should not contain telemetry as the Agent will add it when not present.
        """
        with test_library.start_span("first_span"):
            pass

        traces = test_agent.wait_for_num_traces(num=1)

        assert (
            "_dd.install.time" not in traces[0][0]["meta"]
        ), "The installation time should not be included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]["_dd.install.time"]
        )
        assert (
            "_dd.install.type" not in traces[0][0]["meta"]
        ), "The installation type should not be included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]["_dd.install.type"]
        )
        assert (
            "_dd.install.id" not in traces[0][0]["meta"]
        ), "The installation id should not be included in the first span of the first trace, got {}".format(
            traces[0][0]["meta"]
        )

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
            assert (
                "DD-Agent-Install-Id" in req["headers"]
            ), "The install id should be included in all telemetry events, got headers {}".format(req["headers"])
            assert (
                req["headers"]["DD-Agent-Install-Id"] == library_env["DD_INSTRUMENTATION_INSTALL_ID"]
            ), "The install id should match the environment setting, got {}".format(
                req["headers"]["DD-Agent-Install-Id"]
            )
            assert (
                "DD-Agent-Install-Type" in req["headers"]
            ), "The install type should be included in all telemetry events, got headers {}".format(req["headers"])
            assert (
                req["headers"]["DD-Agent-Install-Type"] == library_env["DD_INSTRUMENTATION_INSTALL_TYPE"]
            ), "The install type should match the environment setting, got {}".format(
                req["headers"]["DD-Agent-Install-Type"]
            )
            assert (
                "DD-Agent-Install-Time" in req["headers"]
            ), "The install time should be included in all telemetry events, got headers {}".format(req["headers"])
            assert (
                req["headers"]["DD-Agent-Install-Time"] == library_env["DD_INSTRUMENTATION_INSTALL_TIME"]
            ), "The install time should be included in all telemetry events, got {}".format(
                req["headers"]["DD-Agent-Install-Time"]
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
            assert (
                "DD-Agent-Install-Id" not in req["headers"]
            ), "The install id should not be included when not propagated, got headers {}".format(req["headers"])
            assert (
                "DD-Agent-Install-Type" not in req["headers"]
            ), "The install type should not be included when not propagated, got headers {}".format(req["headers"])
            assert (
                "DD-Agent-Install-Time" not in req["headers"]
            ), "The install time should not be included when not propagated, got headers {}".format(req["headers"])

"""This module provides simple unit tests for each parametric endpoint.
The results of these unit tests are reported to the feature parity dashboard.
Parametric endpoints that are not tested in this file are not yet supported.
Avoid using those endpoints in the parametric tests.
When in doubt refer to the python implementation as the source of truth via
the OpenAPI schema: https://github.com/DataDog/system-tests/blob/44281005e9d2ddec680f31b2813eb90af831c0fc/docs/scenarios/parametric.md#shared-interface
"""

import pytest
import time

from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_span_in_traces
from utils.parametric.spec.trace import retrieve_span_links
from utils.parametric.spec.trace import retrieve_span_events
from utils.parametric.spec.trace import find_only_span
from utils import irrelevant, bug, incomplete_test_app, scenarios, features, context, missing_feature
from opentelemetry.trace import SpanKind
from opentelemetry.trace import StatusCode
from utils.parametric._library_client import APMLibrary, Link, LogLevel
from utils.docker_fixtures import TestAgentAPI

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in the tracers to enable OTel
#   DD_TRACE_PROPAGATION_HTTP_BAGGAGE_ENABLED=true is required in the tracers to enable baggage propagation, which is used for one test class in this file
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "DD_TRACE_PROPAGATION_HTTP_BAGGAGE_ENABLED": "true"}]
)

@missing_feature(
    context.library == "nodejs",
    reason="Temporarily disabled while adjusting FFE implementation and system tests",
    force_skip=True,
)
@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Start:
    def test_start_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/start creates a new span.

        Supported Parameters:
        - name: str
        - service: Optional[str]
        - resource: Optional[str]
        - parent_id: Optional[Union[str,int]]
        - type: Optional[str]
        - tags: Optional[List[Tuple[str, str]]]

        Supported Return Values:
        - span_id: Union[int, str]
        - trace_id: Union[int, str]
        """
        with test_library:
            with test_library.dd_start_span("parent") as s1:
                pass

            # To test proper parenting behavior
            with test_library.dd_start_span(
                "child", "myservice", "myresource", s1.span_id, "web", tags=[("hello", "monkeys"), ("num", "1")]
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(1)
        trace = find_trace(traces, s1.trace_id)
        assert len(trace) == 2

        parent_span = find_span(trace, s1.span_id)
        assert parent_span["name"] == "parent"

        child_span = find_span(trace, s2.span_id)
        assert child_span["name"] == "child"
        assert child_span["service"] == "myservice"
        assert child_span["resource"] == "myresource"
        # nodejs and dotnet libraries returns span and trace_ids as strings
        assert child_span["parent_id"] == int(s1.span_id)
        assert child_span["type"] == "web"
        assert child_span["meta"]["hello"] == "monkeys"
        assert child_span["meta"]["num"] == "1"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Finish:
    def test_span_finish(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/finish finishes a span and sends it to the agent.

        Supported Parameters:
        - span_id: Union[int, str]
        Supported Return Values:
        """
        with test_library:
            # Avoids calling test_library.dd_start_span.__exit__() since this method calls span.finish()
            s1 = test_library.dd_start_span("span").__enter__()
            with pytest.raises(ValueError) as e:
                test_agent.wait_for_num_traces(num=1)
            assert e.match(".*traces not available from test agent, got 0.*")
            s1.finish()

        traces = test_agent.wait_for_num_traces(1)
        assert find_span_in_traces(traces, s1.trace_id, s1.span_id)


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_Inject_Headers:
    def test_inject_headers(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/inject_headers generates distributed tracing headers from span data.

        Supported Parameters:
        - span_id: Union[int, str]
        Supported Return Values:
        - List[Tuple[str, str]]
        """
        with test_library.dd_start_span("local_root_span") as s1:
            headers = test_library.dd_inject_headers(s1.span_id)
            assert headers
            assert "x-datadog-parent-id" in [h[0] for h in headers]
            assert str(s1.span_id) in [h[1] for h in headers]


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Extract_Headers:
    def test_extract_headers(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/extract_headers extracts span data from distributed tracing headers.

        Supported Parameters:
        - List[Tuple[str, str]]
        Supported Return Values:
        - span_id: Union[int, str]
        """
        with test_library:
            parent_id = test_library.dd_extract_headers([("x-datadog-trace-id", "1"), ("x-datadog-parent-id", "2")])
            # nodejs library returns span and trace_ids as strings
            assert int(parent_id) == 2

            with test_library.dd_start_span("local_root_span", parent_id=parent_id) as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["name"] == "local_root_span"
        assert span["trace_id"] == 1
        assert span["parent_id"] == 2


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Set_Meta:
    def test_set_meta(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/set_meta sets a key value pair on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        - value: str
        Supported Return Values:
        """

        with test_library, test_library.dd_start_span("span") as s1:
            s1.set_meta("key", "value")

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["meta"]["key"] == "value"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Set_Metric:
    def test_set_metric(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/set_metric sets a metric on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        - value: Union[int, float]
        Supported Return Values:
        """

        with test_library, test_library.dd_start_span("span_meta") as s1:
            s1.set_metric("key", 1)

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["metrics"]["key"] == 1


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Set_Error:
    def test_set_error(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/error sets an error on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - type: str
        - message: str
        - stack: str
        Supported Return Values:
        """

        with test_library, test_library.dd_start_span("span_set_error") as s1:
            s1.set_error("MyException", "Parametric tests rock", "fake_stacktrace")

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["error"] == 1
        assert span["meta"]["error.type"] == "MyException"
        assert span["meta"].get("error.message", span["meta"].get("error.msg")) == "Parametric tests rock"
        assert span["meta"]["error.stack"] == "fake_stacktrace"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Set_Resource:
    def test_set_resource(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/set_resource sets a resource name on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - resource: str
        Supported Return Values:
        """
        with test_library, test_library.dd_start_span("span_set_resource", "old_resource") as s1:
            s1.set_resource("new_resource")

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)
        assert span["resource"] == "new_resource"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDSpan_Add_Link:
    def test_add_link(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/add_link adds a spanlink to a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - parent_id: Union[int, str]
        - attributes: Dict[str, str]
        Supported Return Values:
        """

        with test_library:
            with test_library.dd_start_span("span_add_link") as s1:
                pass

            with test_library.dd_start_span("span_add_link2") as s2:
                s2.add_link(s1.span_id, {"link.key": "value"})

        traces = test_agent.wait_for_num_traces(2)
        span = find_span_in_traces(traces, s2.trace_id, s2.span_id)
        links = retrieve_span_links(span)
        assert len(links) == 1
        assert links[0]["span_id"] == int(s1.span_id)
        assert links[0]["attributes"]["link.key"] == "value"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Config:
    def test_config(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/config returns a list of tracer configurations. This list is expected to
        grow over time.

        Supported Parameters:
        Supported Return Values:
        - config: Dict[str, str]
        """
        with test_library as t:
            configs = t.config()
            assert configs
            assert list(configs.keys()) == [
                "dd_service",
                "dd_log_level",
                "dd_trace_sample_rate",
                "dd_trace_enabled",
                "dd_runtime_metrics_enabled",
                "dd_tags",
                "dd_trace_propagation_style",
                "dd_trace_debug",
                "dd_trace_otel_enabled",
                "dd_trace_sample_ignore_parent",
                "dd_env",
                "dd_version",
                "dd_trace_agent_url",
                "dd_trace_rate_limit",
                "dd_dogstatsd_host",
                "dd_dogstatsd_port",
                "dd_logs_injection",
                "dd_profiling_enabled",
                "dd_data_streams_enabled",
            ]


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Crash:
    def test_crash(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/crash crashes the current process.

        Supported Parameters:
        Supported Return Values:
        """
        assert test_library.is_alive()
        test_library.crash()
        assert not test_library.is_alive()


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Current_Span:
    def test_current_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/current returns the active Datadog span.

        Supported Parameters:
        Supported Return Values:
        - span_id: Union[int, str]
        """
        with test_library:
            dd_current_span = test_library.dd_current_span()
            assert dd_current_span is not None
            assert int(dd_current_span.span_id) == 0
            assert int(dd_current_span.trace_id) == 0

            with test_library.dd_start_span("span_test_current_span") as s1:
                dd_current_span = test_library.dd_current_span()
                assert dd_current_span is not None
                assert dd_current_span.span_id == s1.span_id

                with test_library.dd_start_span("span_test_current_spans_s2", parent_id=s1.span_id) as s2:
                    dd_current_span = test_library.dd_current_span()
                    assert dd_current_span is not None
                    assert dd_current_span.span_id == s2.span_id

                dd_current_span = test_library.dd_current_span()
                assert dd_current_span is not None
                assert dd_current_span.span_id == s1.span_id

            dd_current_span = test_library.dd_current_span()
            assert dd_current_span is not None
            assert int(dd_current_span.span_id) == 0
            assert int(dd_current_span.trace_id) == 0

    def test_current_span_from_otel(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/current can return the Datadog span that was created by the OTEL API.

        Supported Parameters:
        Supported Return Values:
        - span_id: Union[int, str]
        """
        with test_library:
            with test_library.otel_start_span("span_test_current_span_from_otel") as s1:
                dd_current_span = test_library.dd_current_span()
                assert dd_current_span is not None
                assert dd_current_span.span_id == s1.span_id
            dd_current_span = test_library.dd_current_span()
            assert dd_current_span is not None
            assert int(dd_current_span.span_id) == 0
            assert int(dd_current_span.trace_id) == 0


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Flush:
    def test_flush(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/flush and /trace/stats/flush endpoints are implemented and return successful status codes.
        If these endpoint are not implemented, spans and/or stats will not be flushed when the test_library contextmanager exits.
        Trace data may or may not be received by the agent in time for validation. This can introduce flakiness in tests.

        Supported Parameters:
        Supported Return Values:
        - success: bool
        """
        with test_library.dd_start_span("test_flush"):
            pass
        assert test_library.dd_flush()


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_DDTrace_Baggage:
    def test_set_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/set_baggage sets a baggage item.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        - value: str
        Supported Return Values:
        """
        with test_library:
            with test_library.dd_start_span("test_set_baggage") as s1:
                s1.set_baggage("key", "value")

            headers = test_library.dd_inject_headers(s1.span_id)
            assert any("baggage" in header for header in headers)

    def test_get_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/get_baggage gets a baggage item.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        Supported Return Values:
        - value: str
        """
        with test_library, test_library.dd_start_span("test_get_baggage") as s1:
            s1.set_baggage("key", "value")

            baggage = s1.get_baggage("key")
            assert baggage == "value"

    def test_get_all_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/get_all_baggage gets all baggage items.

        Supported Parameters:
        - span_id: Union[int, str]
        Supported Return Values:
        - baggage: Dict[str, str]
        """
        with test_library, test_library.dd_start_span("test_get_all_baggage") as s1:
            s1.set_baggage("key1", "value")
            s1.set_baggage("key2", "value")

            baggage = s1.get_all_baggage()
            assert baggage["key1"] == "value"
            assert baggage["key2"] == "value"

    def test_remove_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/remove_baggage removes a baggage item.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        Supported Return Values:
        """
        with test_library:
            with test_library.dd_start_span("test_remove_baggage") as s1:
                # Set baggage
                s1.set_baggage("key", "value")
                headers = test_library.dd_inject_headers(s1.span_id)
                assert any("baggage" in header for header in headers)
                # Remove baggage
                s1.remove_baggage("key")

            headers = test_library.dd_inject_headers(s1.span_id)
            assert not any("baggage" in header for header in headers)

    def test_remove_all_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/span/remove_all_baggage removes all baggage items from a span.

        Supported Parameters:
        - span_id: Union[int, str]
        Supported Return Values:
        """
        with test_library:
            with test_library.dd_start_span("test_remove_baggage") as s1:
                # Set baggage
                s1.set_baggage("key1", "value")
                s1.set_baggage("key2", "value")
                # Remove all baggage
                headers = test_library.dd_inject_headers(s1.span_id)
                assert any("baggage" in header for header in headers)
                s1.remove_all_baggage()

            headers = test_library.dd_inject_headers(s1.span_id)
            assert not any("baggage" in header for header in headers)


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Start:
    def test_span_start(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that the /trace/otel/start_span creates a new span.

        Supported Parameters:
        - name: str
        - timestamp (μs): Optional[int]
        - span_kind: Optional[SpanKind]
        - parent_id: Optional[Union[int, str]]
        - attributes: Optional[Dict[str, str]]
        - links: Optional[List[Link]]
        Supported Return Values:
        - span_id: Union[int, str]
        - trace_id: Union[int, str]
        """
        with test_library:
            with test_library.otel_start_span("otel_start_span_parent") as s1:
                pass

            with test_library.otel_start_span("otel_start_span_linked") as s2:
                pass

            with test_library.otel_start_span(
                name="otel_start_span_child",
                timestamp=1730393556000000,
                span_kind=SpanKind.SERVER,
                parent_id=s1.span_id,
                links=[Link(parent_id=s2.span_id, attributes={"link.key": "value"})],
                attributes={"attr_key": "value"},
            ) as s3:
                pass

        traces = test_agent.wait_for_num_traces(2)
        first_trace = find_trace(traces, s1.trace_id)
        assert len(first_trace) == 2
        parent = find_span(first_trace, s1.span_id)
        assert parent["resource"] == "otel_start_span_parent"
        child = find_span(first_trace, s3.span_id)
        assert child["resource"] == "otel_start_span_child"
        assert child["meta"]["span.kind"] == "server"
        assert child["meta"]["attr_key"] == "value"
        assert child["start"] == 1730393556000000000
        links = retrieve_span_links(child)
        assert len(links) == 1
        assert links[0]["span_id"] == int(s2.span_id)
        assert links[0]["attributes"]["link.key"] == "value"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_End:
    def test_span_end(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that the /trace/otel/end_span finishes a span and sends it to the agent

        Supported Parameters:
        - timestamp (μs): Optional[int]
        Supported Return Values:
        """
        sleep = 0.2
        t1 = time.time()
        with test_library, test_library.otel_start_span("otel_end_span", end_on_exit=True):
            time.sleep(sleep)
        total_time = time.time() - t1

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        assert sleep <= span["duration"] / 1e9 <= total_time, span["start"]

    def test_span_end_with_timestamp(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that the /trace/otel/end_span finishes a span and sends it to the agent with the expected duration

        Supported Parameters:
        - timestamp (μs): Optional[int]
        Supported Return Values:
        """
        start = 5_000_000  # microseconds
        end = 10_000_000  # microseconds
        with test_library:
            with test_library.otel_start_span("otel_end_span_with_timestamp", timestamp=start, end_on_exit=False) as s1:
                pass
            s1.end_span(end)

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        assert span["start"] == start * 1000
        assert span["duration"] == (end - start) * 1000


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Set_Attribute:
    def test_otel_set_attribute(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/set_attributes sets a key value pair on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        Supported Return Values:
        """
        with test_library, test_library.otel_start_span("otel_set_attribute") as s1:
            s1.set_attribute("key", "value")

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        assert span["meta"]["key"] == "value"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Set_Status:
    def test_otel_set_status(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/set_status sets a status on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - code: Literal[StatusCode]
        - description: str
        Supported Return Values:
        """
        with test_library, test_library.otel_start_span("otel_set_status") as s1:
            s1.set_status(StatusCode.ERROR, "error message")

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        assert span["error"] == 1


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Set_Name:
    def test_otelspan_set_name(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/set_name sets the resource name on a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - name: str
        Supported Return Values:
        """
        with test_library, test_library.otel_start_span("otel_set_name") as s1:
            s1.set_name("new_name")

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        assert span["resource"] == "new_name"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Events:
    def test_add_event(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/add_event adds an event to a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - name: str
        - timestamp (μs): Optional[int]
        - attributes: Optional[Dict[str, str]]
        Supported Return Values:
        """
        with test_library, test_library.otel_start_span("otel_add_event") as s1:
            s1.add_event("some_event", 1730393556000000, {"key": "value"})

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        events = retrieve_span_events(span)
        assert events is not None
        assert len(events) == 1, f"events: {events}"
        assert events[0]["name"] == "some_event"
        assert events[0]["time_unix_nano"] == 1730393556000000000
        assert events[0]["attributes"]["key"] == "value"

    @irrelevant(context.library == "golang", reason="OTEL does not expose an API for recording exceptions")
    @bug(library="nodejs", reason="APMAPI-778")  # doees not set attributes on the exception event
    def test_record_exception(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/record_exception adds an exception event to a span.

        Supported Parameters:
        - span_id: Union[int, str]
        - message: str
        - attributes: str
        Supported Return Values:
        """
        with test_library, test_library.otel_start_span("otel_record_exception") as s1:
            s1.record_exception("MyException Parametric tests rock", {"error.key": "value"})

        traces = test_agent.wait_for_num_traces(1)
        span = find_only_span(traces)
        events = retrieve_span_events(span)
        assert events is not None
        assert len(events) == 1, f"events: {events}"
        assert events[0]["name"].lower() in ["exception", "error"]
        assert events[0]["attributes"]["error.key"] == "value"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_OtelSpan_Is_Recording:
    def test_is_recording(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/is_recording returns whether a span is recording.

        Supported Parameters:
        - span_id: Union[int, str]
        Supported Return Values:
        - is_recording: bool
        """
        with test_library.otel_start_span("otel_is_recording") as s1:
            assert s1.is_recording()


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_Otel_Baggage:
    def test_set_baggage(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/otel_set_baggage sets a baggage item.

        Supported Parameters:
        - span_id: Union[int, str]
        - key: str
        - value: str
        Supported Return Values:
        """
        with test_library.otel_start_span("otel_set_baggage") as s1:
            value = test_library.otel_set_baggage(s1.span_id, "foo", "bar")
            assert value == "bar"


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_Otel_Current_Span:
    def test_otel_current_span(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/current_span returns the current span.

        Supported Parameters:
        Supported Return Values:
        - span_id: Union[int, str]
        """
        with test_library:
            dd_current_span = test_library.otel_current_span()
            assert dd_current_span is not None
            assert int(dd_current_span.span_id) == 0
            assert int(dd_current_span.trace_id) == 0

            with test_library.otel_start_span("span_test_current_span") as s1:
                dd_current_span = test_library.otel_current_span()
                assert dd_current_span is not None
                assert dd_current_span.span_id == s1.span_id

                with test_library.otel_start_span("span_test_current_spans_s2", parent_id=s1.span_id) as s2:
                    dd_current_span = test_library.otel_current_span()
                    assert dd_current_span is not None
                    assert dd_current_span.span_id == s2.span_id

                dd_current_span = test_library.otel_current_span()
                assert dd_current_span is not None
                assert dd_current_span.span_id == s1.span_id

            dd_current_span = test_library.otel_current_span()
            assert dd_current_span is not None
            assert int(dd_current_span.span_id) == 0
            assert int(dd_current_span.trace_id) == 0


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_Otel_Trace_Flush:
    def test_flush(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /trace/otel/flush flushes all finished spans.

        Supported Parameters:
        - timeout_sec: int
        Supported Return Values:
        - success: boolean
        """
        with test_library.otel_start_span("test_otel_flush"):
            pass

        assert test_library.otel_flush(timeout_sec=5)


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_Write_Log:
    @incomplete_test_app(context.library != "python", reason="Logs endpoint is only implemented in python app")
    def test_write_log(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /log/write creates a log message with the specified parameters.

        Supported Parameters:
        - message: str
        - level: LogLevel enum (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - logger_name: str
        - span_id: Union[int, str]  (optional)

        Supported Return Values:
        - success: bool
        """
        # Test with different log levels
        result = test_library.write_log("Warning message", LogLevel.WARNING, "warning_logger")
        assert result is True

        result = test_library.write_log("Error message", LogLevel.ERROR, "error_logger")
        assert result is True

        # Test with custom logger name
        result = test_library.write_log("Custom logger message", LogLevel.INFO, "custom_app_logger")
        assert result is True

    def test_write_log_with_span_id(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /log/write creates a log message with the specified parameters.

        Supported Parameters:
        - message: str
        - level: LogLevel enum (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - logger_name: str
        - span_id: Union[int, str]  (optional)
        """
        with test_library.otel_start_span("otel_span") as s1:
            pass

        with test_library.dd_start_span("dd_span") as s2:
            pass

        result = test_library.write_log("Warning message", LogLevel.WARNING, "warning_logger", span_id=s1.span_id)
        assert result is True

        result = test_library.write_log("Error message", LogLevel.ERROR, "error_logger", span_id=s2.span_id)
        assert result is True


@scenarios.parametric
@features.parametric_endpoint_parity
class Test_Parametric_FFE_Start:
    def test_ffe_start(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Validates that /ffe/start initializes the feature flag evaluation provider and returns a successful status code.

        Supported Parameters:
        Supported Return Values:
        - success: bool
        """
        result = test_library.ffe_start()
        assert result is True

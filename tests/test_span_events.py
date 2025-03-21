# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, irrelevant, weblog, scenarios, features, rfc, logger, missing_feature
from utils.parametric.spec.trace import find_span, find_trace
import json


@rfc("https://docs.google.com/document/d/1cVod_VI7Yruq8U9dfMRFJd7npDu-uBpste2IB04GyaQ")
@features.span_events
@scenarios.agent_supporting_span_events
class Test_SpanEvents_WithAgentSupport:
    """Test that tracers send natively serialized span events if the agent support and serialization format support it.
    Tracers only need to test for their default serialization format (v0.4, v0.5, v0.7).

    Request the Weblog endpoint `/add_event`,
    which creates a span with resource `add_event` and
    adds a span event (with any name and attributes values)
    """

    def setup_v04_v07_default_format(self):
        self.r = weblog.get("/add_event")

    @missing_feature(library = "java", reason="Native span events are not yet supported")
    def test_v04_v07_default_format(self):
        """For traces that default to the v0.4 or v0.7 format, send events as a top-level `span_events` field"""
        interfaces.library.assert_trace_exists(self.r)
        traces = [t for _, t in interfaces.library.get_traces(request=self.r)]
        
        span = None
        for trace in traces:
            span = next((s for s in trace if s["resource"] == "add_event"), None)
            if span is not None:
                break
                
        meta = span.get("meta", {})
        assert "span_events" in span
        assert "events" not in meta

    def setup_v05_default_format(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="v0.5 is not the default format")
    @irrelevant(context.library in ["nodejs"], reason="v0.5 is not the default format")
    def test_v05_default_format(self):
        """For traces that default to the v0.5 format, send events as the span tag `events`
        given this format does not support native serialization.
        """
        interfaces.library.assert_trace_exists(self.r)
        traces = [t for _, t in interfaces.library.get_traces(request=self.r)]
        
        span = None
        for trace in traces:
            span = next((s for s in trace if s["resource"] == "add_event"), None)
            if span is not None:
                break
                

        meta = span.get("meta", {})
        assert "span_events" not in span
        assert "events" in meta


@features.span_events
@scenarios.agent_not_supporting_span_events
class Test_SpanEvents_WithoutAgentSupport:
    """Test that tracers do not attempt to send natively serialized span events if the agent does not support it.

    Request the Weblog endpoint `/add_event`,
    which creates a span with resource `add_event` and
    adds a span event (with any name and attributes values)
    """

    def setup_send_as_a_tag(self):
        self.r = weblog.get("/add_event")

    def test_send_as_a_tag(self):
        """Send span events as the tag `events` when the agent does not support native serialization"""
        interfaces.library.assert_trace_exists(self.r)
        traces = [t for _, t in interfaces.library.get_traces(request=self.r)]
        
        span = None
        for trace in traces:
            span = next((s for s in trace if s["resource"] == "add_event"), None)
            if span is not None:
                break
                
        meta = span.get("meta", {})
        assert "span_events" not in span
        assert "events" in meta

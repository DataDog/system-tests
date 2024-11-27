# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, irrelevant, weblog, scenarios, features, rfc


@rfc("https://docs.google.com/document/d/1cVod_VI7Yruq8U9dfMRFJd7npDu-uBpste2IB04GyaQ")
@features.span_events
@scenarios.agent_supporting_span_events
class Test_SpanEvents_WithAgentSupport:
    """
    Test that tracers send natively serialized span events if the agent support it.

    Request the Weblog endpoint `/add_event`, which adds a span event (with any name and attributes values)
    to the request root span.
    """

    def setup_v07(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="Does not support v0.7")
    def test_v07(self):
        """The v0.7 format send events as a top-levle `span_events` when the agent supports native serialization"""
        interfaces.library.assert_trace_exists(self.r)

        span = self._get_span(self.r)

        assert "span_events" in span

    def setup_v04(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="Native serialization not supported")
    def test_v04(self):
        """The v0.4 format send events as a top-levle `span_events` when the agent supports native serialization"""
        interfaces.library.assert_trace_exists(self.r)

        span = self._get_span(self.r)

        assert "span_events" in span

    def setup_v05(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="Does not support v0.5")
    def test_v05(self):
        """The v0.5 format continues to send events as tags"""
        interfaces.library.assert_trace_exists(self.r)

        meta = self._get_root_span_meta(self.r)

        assert "span_events" in meta
        assert "events" not in meta

    def _get_root_span_meta(self, request):
        return self._get_span(request).get("meta", {})

    def _get_span(self, request):
        root_spans = [s for _, s in interfaces.library.get_root_spans(request=request)]
        assert len(root_spans) == 1
        return root_spans


@features.span_events
@scenarios.agent_not_supporting_span_events
class Test_SpanEvents_WithoutAgentSupport:
    """
    Test that tracers do not attempt to send natively serialized span events if the agent does not support it.
    
    Request the Weblog endpoint `/add_event`, which adds a span event (with any name and attributes values)
    to the request root span.
    """

    def setup_v07(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="Does not support v0.7")
    def test_v07(self):
        """The v0.7 format send events as tags when the agent does not support native serialization"""
        interfaces.library.assert_trace_exists(self.r)

        meta = self._get_root_span_meta(self.r)

        assert "span_events" not in meta
        assert "events" in meta

    def setup_v04(self):
        self.r = weblog.get("/add_event")

    def test_v04(self):
        """The v0.4 format send events as tags when the agent does not support native serialization"""
        interfaces.library.assert_trace_exists(self.r)

        meta = self._get_root_span_meta(self.r)

        assert "span_events" not in meta
        assert "events" in meta

    def setup_v05(self):
        self.r = weblog.get("/add_event")

    @irrelevant(context.library in ["ruby"], reason="Does not support v0.5")
    def test_v05(self):
        """The v0.5 format continues to send events as tags"""
        interfaces.library.assert_trace_exists(self.r)

        meta = self._get_root_span_meta(self.r)

        assert "span_events" not in meta
        assert "events" in meta

    def _get_root_span_meta(self, request):
        root_spans = [s for _, s in interfaces.library.get_root_spans(request=request)]
        assert len(root_spans) == 1
        span = root_spans[0]
        return span.get("meta", {})

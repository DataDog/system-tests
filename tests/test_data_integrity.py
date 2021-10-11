# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
from utils import BaseTestCase, interfaces, skipif, context


class Test_TraceUniqueness(BaseTestCase):
    """Test uniques values"""

    def test_trace_ids(self):
        """Test uniqeness of trace_ids"""
        interfaces.library.assert_trace_id_uniqueness()


@skipif(context.weblog_variant == "echo-poc", reason="not relevant: echo isn't instrumented")
class Test_TraceHeaders(BaseTestCase):
    @skipif(context.library == "cpp", reason="known bug?")
    @skipif(context.library == "golang", reason="known bug?")
    @skipif(context.library == "php", reason="known bug: Php tracer submits empty traces to endpoint")
    def test_traces_header_present(self):
        """Verify that headers described in
        https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md
        are present in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_present()

    @skipif(context.library != "php", reason="Not relevant: Special case of the header tests for php tracer")
    def test_traces_header_present_php(self):
        """Verify that headers described in
        https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md
        are present in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_present_php()

    def test_trace_header_count_match(self):
        """Verify that the X-Datadog-Trace-Count header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_count_match()

    @skipif(context.library != "cpp", reason="Not relevant: Special case of Datadog-Container-ID test for C++ tracer")
    def test_trace_header_container_tags_cpp(self):
        """Verify that the Datadog-Container-ID header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_container_tags_cpp()

    @skipif(
        context.library == "cpp",
        reason="known bug: C++ tracer doesn't send Datadog-Container-ID "
        "https://github.com/DataDog/dd-opentracing-cpp/issues/194",
    )
    def test_trace_header_container_tags(self):
        """Verify that the Datadog-Container-ID header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_container_tags()

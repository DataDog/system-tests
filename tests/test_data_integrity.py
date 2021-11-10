# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
from utils import BaseTestCase, interfaces, context, bug, irrelevant, rfc, released


class Test_TraceUniqueness(BaseTestCase):
    """All trace ids are uniques"""

    def test_trace_ids(self):
        interfaces.library.assert_trace_id_uniqueness()


@rfc("https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md")
@irrelevant(weblog_variant="echo-poc", reason="echo isn't instrumented")
class Test_TraceHeaders(BaseTestCase):
    """All required headers are present in all traces submitted to the agent"""

    @bug(library="cpp")
    @bug(library="golang")
    @bug(library="php", reason="Php tracer submits empty traces to endpoint")
    def test_traces_header_present(self):
        interfaces.library.assert_trace_headers_present()

    @irrelevant(context.library != "php", reason="Special case of the header tests for php tracer")
    def test_traces_header_present_php(self):
        interfaces.library.assert_trace_headers_present_php()

    def test_trace_header_count_match(self):
        """X-Datadog-Trace-Count header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_count_match()

    @irrelevant(context.library != "cpp", reason="Special case of Datadog-Container-ID test for C++ tracer")
    def test_trace_header_container_tags_cpp(self):
        """Datadog-Container-ID header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_container_tags_cpp()

    @bug(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/194")
    def test_trace_header_container_tags(self):
        """Datadog-Container-ID header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_container_tags()

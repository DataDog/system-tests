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
class Test_TraceHeaders(BaseTestCase):
    """All required headers are present in all traces submitted to the agent"""

    @bug(context.library <= "golang@1.37.0")
    @bug(library="cpp")
    def test_traces_header_present(self):
        """Verify that headers described in RFC are present in traces submitted to the agent"""

        request_headers = [
            "datadog-meta-tracer-version",
            "datadog-meta-lang",
            "datadog-meta-lang-interpreter",
            "datadog-meta-lang-version",
            "x-datadog-trace-count",
        ]

        def check_condition(data):
            # if there is not trace, don't check anything
            return len(data["request"]["content"]) != 0

        interfaces.library.assert_headers_presence(
            r"/v[0-9]+\.[0-9]+/traces", request_headers=request_headers, check_condition=check_condition
        )

    def test_trace_header_diagnostic_check(self):
        """ x-datadog-diagnostic-check header is present iif content is empty """

        def validator(data):
            request_headers = {h[0].lower() for h in data["request"]["headers"]}
            if "x-datadog-diagnostic-check" in request_headers and len(data["request"]["content"]) != 0:
                raise Exception("Tracer sent a dignostic request with traces in it")

        interfaces.library.add_traces_validation(validator=validator, is_success_on_expiry=True)

    def test_trace_header_count_match(self):
        """X-Datadog-Trace-Count header value is right in all traces submitted to the agent"""

        def validator(data):
            for header, value in data["request"]["headers"]:
                if header.lower() == "x-datadog-trace-count":
                    try:
                        trace_count = int(value)
                    except ValueError:
                        raise Exception(
                            f"{self.count_header} request header in {data['log_filename']} wasn't an integer: {value}"
                        )

                    if trace_count != len(data["request"]["content"]):
                        raise Exception(
                            f"x-datadog-trace-count request header in {data['log_filename']} didn't match the number of traces"
                        )

        interfaces.library.add_traces_validation(validator=validator, is_success_on_expiry=True)

    @bug(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/194")
    def test_trace_header_container_tags(self):
        """Datadog-Container-ID header value is right in all traces submitted to the agent"""
        interfaces.library.assert_trace_headers_container_tags()

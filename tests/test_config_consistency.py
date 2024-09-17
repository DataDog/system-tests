# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_HttpServerErrorStatuses_Default:
    """ Verify behavior of http clients and distributed traces """

    def setup_status_code_400(self):
        self.r = weblog.get("/status?code=400")

    def test_status_code_400(self):

        assert self.r.status_code == 400

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "400"
        assert "error" not in spans[0] or spans[0]["error"] == 0

    def setup_status_code_500(self):
        self.r = weblog.get("/status?code=500")

    def test_status_code_500(self):
        assert self.r.status_code == 500

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["meta"]["http.status_code"] == "500"
        assert spans[0]["error"] == 1


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_HttpServerErrorStatuses_FeatureFlagCustom:
    """ Verify behavior of http clients and distributed traces """

    def setup_status_code_200(self):
        self.r = weblog.get("/status?code=200")

    def test_status_code_200(self):
        assert self.r.status_code == 200

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "200"
        assert spans[0]["error"] == 1

    def setup_status_code_202(self):
        self.r = weblog.get("/status?code=202")

    def test_status_code_202(self):
        assert self.r.status_code == 202

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "202"
        assert spans[0]["error"] == 1


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_ClientTagQueryString_Empty:
    """Verify behavior when DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING set to empty string"""

    def setup_query_string_redaction_unset(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?hi=monkey"})

    def test_query_string_redaction_unset(self):
        trace = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        expected_tags = {"http.url": "http://weblog:7777/?hi=monkey"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault_3
@features.tracing_configuration_consistency
class Test_Config_ClientTagQueryString_Configured:
    """Verify behavior when DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING set to false"""

    def setup_query_string_redaction(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?hi=monkey"})

    def test_query_string_redaction(self):
        trace = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        expected_tags = {"http.url": "http://weblog:7777/"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_ClientIPHeader_Configured:
    """Verify headers containing ips are tagged when DD_TRACE_CLIENT_IP_ENABLED=true
    and DD_TRACE_CLIENT_IP_HEADER=custom-ip-header"""

    IP_HEADERS = {
        "custom-ip-header": "0.0.0.1",
        "x-forwarded-for": "98.73.45.0",
        "x-real-ip": "98.73.145.1",
        "true-client-ip": "98.73.45.2",
        "x-client-ip": "98.73.45.3",
        "x-forwarded": "98.73.45.4",
        "forwarded-for": "98.73.45.5",
        "x-cluster-client-ip": "98.73.45.6",
        "fastly-client-ip": "98.73.45.7",
        "cf-connecting-ip": "98.73.45.8",
        "cf-connecting-ipv6": "98.73.45.9",
    }

    def setup_ip_headers_sent_in_seperate_client_requests(self):
        for header, ip in self.IP_HEADERS.items():
            self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers={header: ip})

    def test_ip_headers_sent_in_seperate_client_requests(self):
        # Ensures client libraries support each of the headers in Test_Config_ClientIPHeader_Configured.IP_HEADERS
        spans = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        ip_headers_found = {span["meta"]["http.client_ip"] for span in spans if "http.client_ip" in span["meta"]}
        ip_headers = {ip for _, ip in self.IP_HEADERS}
        assert ip_headers.issubset(
            ip_headers_found
        ), f"Expected {ip_headers} but found {ip_headers_found} in spans {spans}"

    def setup_ip_headers_sent_in_one_client_requests(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=self.IP_HEADERS)

    def test_ip_headers_sent_in_seperate_client_requests(self):
        # Ensures the header set in DD_TRACE_CLIENT_IP_HEADER takes precedence over all supported ip headers
        trace = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        expected_tags = {"http.client_ip": "0.0.0.1"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


def _get_span_by_tags(trace, tags):
    for span in trace:
        # Avoids retrieving the client span by the operation/resource name, this value varies between languages
        # Use the expected tags to identify the span
        for k, v in tags.items():
            if span["meta"].get(k) != v:
                break
        else:
            return span

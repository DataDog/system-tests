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
        "custom-ip-header": "5.6.7.8",
        "x-forwarded-for": "98.73.45.0",
        "x-real-ip": "98.73.145.1",
        "true-client-ip": "98.73.45.2",
        "x-client-ip": "98.73.45.3",
        "x-forwarded": "98.73.45.4",
        "forwarded-for": "98.73.45.5",
        "x-cluster-client-ip": "98.73.45.6",
        "fastly-client-ip": "98.73.45.7",
        "cf-connecting-ip": "98.73.45.8",
        "cf-connecting-ipv6": "2001:db8:3333:4444:5555:6666:7777:8888",
    }

    def setup_ip_headers_sent_in_one_client_requests(self):
        self.req2 = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=self.IP_HEADERS)

    def test_ip_headers_sent_in_one_client_requests(self):
        # Ensures the header set in DD_TRACE_CLIENT_IP_HEADER takes precedence over all supported ip headers
        trace = [span for _, _, span in interfaces.library.get_spans(self.req2, full_trace=True)]
        expected_tags = {"http.client_ip": "5.6.7.8"}
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


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging_CustomService:
    """ Verify behavior of http clients and distributed traces """

    def setup_specified_service_name(self):
        self.r = weblog.get("/")

    def test_specified_service_name(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"
        assert spans[0]["service"] == "service_test"


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging_Default:
    """ Verify behavior of http clients and distributed traces """

    def setup_default_service_name(self):
        self.r = weblog.get("/")

    def test_default_service_name(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"
        assert (
            spans[0]["service"] != "service_test"
        )  # in default scenario, DD_SERVICE is set to "weblog" in the dockerfile; this is a temp fix to test that it is not the value we manually set in the specific scenario

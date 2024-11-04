# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features, rfc, irrelevant, context, bug


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


# Tests for verifying default query string obfuscation behavior can be found in the Test_StandardTagsUrl test class
@scenarios.tracing_config_nondefault_2
@features.tracing_configuration_consistency
class Test_Config_ObfuscationQueryStringRegexp_Empty:
    """ Verify behavior when set to empty string """

    def setup_query_string_obfuscation_empty_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?key=monkey"})

    @bug(context.library == "java", reason="APMAPI-770")
    def test_query_string_obfuscation_empty_client(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        client_span = _get_span_by_tags(spans, tags={"http.url": "http://weblog:7777/?key=monkey"})
        assert client_span, "\n".join([str(s) for s in spans])

    def setup_query_string_obfuscation_empty_server(self):
        self.r = weblog.get("/?application_key=value")

    @bug(context.library == "python", reason="APMAPI-772")
    def test_query_string_obfuscation_empty_server(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        client_span = _get_span_by_tags(spans, tags={"http.url": "http://localhost:7777/?application_key=value"})
        assert client_span, "\n".join([str(s) for s in spans])


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_ObfuscationQueryStringRegexp_Configured:
    def setup_query_string_obfuscation_configured(self):
        self.r = weblog.get("/?ssn=123-45-6789")

    def test_query_string_obfuscation_configured(self):
        interfaces.library.add_span_tag_validation(
            self.r, tags={"http.url": r"^.*/\?<redacted>$"}, value_as_regular_expression=True,
        )


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_HttpClientErrorStatuses_Default:
    """ Verify behavior of http clients """

    def setup_status_code_400(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=400"})

    def test_status_code_400(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 400

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span_by_tags(spans, tags={"span.kind": "client", "http.status_code": "400"})
        assert client_span, spans
        assert client_span.get("error") == 1

    def setup_status_code_500(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=500"})

    def test_status_code_500(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 500

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span_by_tags(spans, tags={"span.kind": "client", "http.status_code": "500"})
        assert client_span, spans
        assert client_span.get("error") == None or client_span.get("error") == 0


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_HttpClientErrorStatuses_FeatureFlagCustom:
    """ Verify behavior of http clients """

    def setup_status_code_200(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=200"})

    def test_status_code_200(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 200

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span_by_tags(spans, tags={"span.kind": "client", "http.status_code": "200"})
        assert client_span, spans
        assert client_span.get("error") == 1

    def setup_status_code_202(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=202"})

    def test_status_code_202(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 202

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span_by_tags(spans, tags={"span.kind": "client", "http.status_code": "202"})
        assert client_span, spans
        assert client_span.get("error") == 1


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


@scenarios.tracing_config_nondefault_2
@features.tracing_configuration_consistency
class Test_Config_ClientIPHeader_Configured:
    """Verify headers containing ips are tagged when DD_TRACE_CLIENT_IP_ENABLED=true
    and DD_TRACE_CLIENT_IP_HEADER=custom-ip-header"""

    def setup_ip_headers_sent_in_one_request(self):
        self.req = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777"}, headers={"custom-ip-header": "5.6.7.9"}
        )

    def test_ip_headers_sent_in_one_request(self):
        # Ensures the header set in DD_TRACE_CLIENT_IP_HEADER takes precedence over all supported ip headers
        trace = [span for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)]
        expected_tags = {"http.client_ip": "5.6.7.9"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_ClientIPHeader_Precedence:
    """Verify headers containing ips are tagged when DD_TRACE_CLIENT_IP_ENABLED=true 
    and headers are used to set http.client_ip in order of precedence"""

    # Supported ip headers in order of precedence
    IP_HEADERS = (
        ("x-forwarded-for", "5.6.7.0"),
        ("x-real-ip", "8.7.6.5"),
        ("true-client-ip", "5.6.7.2"),
        ("x-client-ip", "5.6.7.3"),
        # ("x-forwarded", "5.6.7.4"),
        ("forwarded-for", "5.6.7.5"),
        ("x-cluster-client-ip", "5.6.7.6"),
        ("fastly-client-ip", "5.6.7.7"),
        ("cf-connecting-ip", "5.6.7.8"),
        ("cf-connecting-ipv6", "0:2:3:4:5:6:7:8"),
    )

    def setup_ip_headers_precedence(self):
        # Sends requests with supported ip headers, in each iteration the header with next higest precedence is not sent.
        # In the last request, only the header with the lowest precedence is sent.
        self.requests = []
        for i in range(len(self.IP_HEADERS)):
            headers = {k: v for k, v in self.IP_HEADERS[i:]}
            self.requests.append(
                weblog.get("/make_distant_call", params={"url": "http://weblog:7777"}, headers=headers)
            )

    def test_ip_headers_precedence(self):
        # Ensures that at least one span stores each ip header in the http.client_ip tag
        # Note - system tests may obfuscate the actual ip address, we may need to update the test to take this into account
        assert len(self.requests) == len(self.IP_HEADERS), "Number of requests and ip headers do not match, check setup"
        for i in range(len(self.IP_HEADERS)):
            req = self.requests[i]
            ip = self.IP_HEADERS[i][1]
            trace = [span for _, _, span in interfaces.library.get_spans(req, full_trace=True)]
            print(88, i)
            expected_tags = {"http.client_ip": ip}
            assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


def _get_span_by_tags(spans, tags):
    for span in spans:
        # Avoids retrieving the client span by the operation/resource name, this value varies between languages
        # Use the expected tags to identify the span
        for k, v in tags.items():
            if span["meta"].get(k) != v:
                break
        else:
            return span
    return {}


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_UnifiedServiceTagging_CustomService:
    """ Verify behavior of http clients and distributed traces """

    def setup_specified_service_name(self):
        self.r = weblog.get("/")

    @irrelevant(
        library="golang",
        weblog_variant="gin",
        reason="A custom service name is specified on the gin integration, causing a conflict",
    )
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


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_IntegrationEnabled_False:
    """ Verify behavior of integrations automatic spans """

    def setup_integration_enabled_false(self):
        # PHP does not have a kafka integration
        if context.library == "php":
            self.r = weblog.get("/dbm", params={"integration": "pdo-pgsql"})
            return
        self.r = weblog.get("/kafka/produce", params={"topic": "Something"})

    def test_integration_enabled_false(self):
        assert self.r.status_code == 200
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True)]
        assert spans, "No spans found in trace"
        # Ruby kafka integration generates a span with the name "kafka.producer.*",
        # unlike python/dotnet/etc. which generates a "kafka.produce" span
        assert (
            list(filter(lambda span: "kafka.produce" in span.get("name"), spans)) == []
        ), f"kafka.produce span was found in trace: {spans}"

        nonKafkaOrPdoSpans = []
        kafkaOrPdoSpans = []
        
        for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True):
            if span.get("name") != "kafka.produce":
                nonKafkaOrPdoSpans.append(span)
            elif context.library == "php" and span.get("service") != "pdo":
                nonKafkaOrPdoSpans.append(span)
            else:
                kafkaOrPdoSpans.append(span)
        assert len(nonKafkaOrPdoSpans) > 0
        assert len(kafkaOrPdoSpans) == 0


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_2
@features.tracing_configuration_consistency
class Test_Config_IntegrationEnabled_True:
    """ Verify behavior of integrations automatic spans """
    def setup_integration_enabled_true(self):
        # PHP does not have a kafka integration
        if context.library == "php":
            self.r = weblog.get("/dbm", params={"integration": "pdo-pgsql"})
            return
        self.r = weblog.get("/kafka/produce", params={"topic": "Something"})

    def test_integration_enabled_true(self):
        assert self.r.status_code == 200
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True)]
        assert spans, "No spans found in trace"
        # Ruby kafka integration generates a span with the name "kafka.producer.*",
        # unlike python/dotnet/etc. which generates a "kafka.produce" span
        assert list(
            filter(lambda span: "kafka.produce" in span.get("name"), spans)
        ), f"No kafka.produce span found in trace: {spans}"

        nonKafkaOrPdoSpans = []
        kafkaOrPdoSpans = []
        for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True):
            if span.get("name") != "kafka.produce" and span.get("service") != "pdo":
                nonKafkaOrPdoSpans.append(span)
            else:
                kafkaOrPdoSpans.append(span)
        assert len(nonKafkaOrPdoSpans) > 0
        assert len(kafkaOrPdoSpans) > 0

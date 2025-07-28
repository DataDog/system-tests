# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import re
import json
import time
from utils import (
    weblog,
    interfaces,
    scenarios,
    features,
    rfc,
    irrelevant,
    context,
    bug,
    missing_feature,
    logger,
    incomplete_test_app,
)

# get the default log output
stdout = interfaces.library_stdout
runtime_metrics = {"nodejs": "runtime.node.mem.heap_total"}
runtime_metrics_lang_map = {
    "dotnet": ("lang", ".NET"),
    "golang": ("lang", "go"),
    "java": (None, None),
    "nodejs": (None, None),
    "python": ("lang", "python"),
    "ruby": ("language", "ruby"),
}


@scenarios.default
@features.trace_http_server_error_statuses
class Test_Config_HttpServerErrorStatuses_Default:
    """Verify behavior of http clients and distributed traces"""

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
@features.trace_http_server_error_statuses
class Test_Config_HttpServerErrorStatuses_FeatureFlagCustom:
    """Verify behavior of http clients and distributed traces"""

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
@features.trace_query_string_obfuscation
class Test_Config_ObfuscationQueryStringRegexp_Empty:
    """Verify behavior when set to empty string"""

    def setup_query_string_obfuscation_empty_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?key=monkey"})

    @bug(
        context.library == "java" and context.weblog_variant in ("vertx3", "vertx4"),
        reason="APMAPI-770",
    )
    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(context.library < "golang@2.1.0-dev", reason="Obfuscation only occurs on server side")
    def test_query_string_obfuscation_empty_client(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        client_span = _get_span_by_tags(
            spans, tags={"span.kind": "client", "http.url": "http://weblog:7777/?key=monkey"}
        )
        assert client_span, "\n".join([str(s) for s in spans])

    def setup_query_string_obfuscation_empty_server(self):
        self.r = weblog.get("/?application_key=value")

    @bug(context.library == "python", reason="APMAPI-772")
    def test_query_string_obfuscation_empty_server(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        server_span = _get_span_by_tags(spans, tags={"http.url": "http://localhost:7777/?application_key=value"})
        assert server_span, "\n".join([str(s) for s in spans])


@scenarios.tracing_config_nondefault
@features.trace_query_string_obfuscation
class Test_Config_ObfuscationQueryStringRegexp_Configured:
    def setup_query_string_obfuscation_configured_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?ssn=123-45-6789"})

    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(
        context.library < "golang@2.1.0-dev",
        reason="Client query string collection disabled by default; obfuscation only occurs on server side",
    )
    @missing_feature(
        context.library == "java" and context.weblog_variant in ("vertx3", "vertx4"),
        reason="Missing endpoint",
    )
    @bug(context.library >= "golang@1.72.0", reason="APMAPI-1196")
    def test_query_string_obfuscation_configured_client(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        client_span = _get_span_by_tags(
            spans, tags={"span.kind": "client", "http.url": "http://weblog:7777/?<redacted>"}
        )
        assert client_span, "\n".join([str(s) for s in spans])

    def setup_query_string_obfuscation_configured_server(self):
        self.r = weblog.get("/?ssn=123-45-6789")

    def test_query_string_obfuscation_configured_server(self):
        interfaces.library.add_span_tag_validation(
            self.r, tags={"http.url": r"^.*/\?<redacted>$"}, value_as_regular_expression=True
        )


@features.trace_query_string_obfuscation
class Test_Config_ObfuscationQueryStringRegexp_Default:
    def setup_query_string_obfuscation_configured_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?token=value"})

    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(
        context.library < "golang@2.1.0-dev",
        reason="Client query string collection disabled by default; obfuscation only occurs on server side",
    )
    @missing_feature(
        context.library == "java" and context.weblog_variant in ("vertx3", "vertx4"),
        reason="Missing endpoint",
    )
    @bug(context.library >= "golang@1.72.0", reason="APMAPI-1196")
    def test_query_string_obfuscation_configured_client(self):
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]
        client_span = _get_span_by_tags(
            spans, tags={"span.kind": "client", "http.url": "http://weblog:7777/?<redacted>"}
        )
        assert client_span, "\n".join([str(s) for s in spans])

    def setup_query_string_obfuscation_configured_server(self):
        self.r = weblog.get("/?token=value")

    def test_query_string_obfuscation_configured_server(self):
        interfaces.library.add_span_tag_validation(
            self.r, tags={"http.url": r"^.*/\?<redacted>$"}, value_as_regular_expression=True
        )


@scenarios.default
@features.trace_http_client_error_statuses
class Test_Config_HttpClientErrorStatuses_Default:
    """Verify behavior of http clients"""

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
        assert client_span.get("error") is None or client_span.get("error") == 0


@scenarios.tracing_config_nondefault
@features.trace_http_client_error_statuses
class Test_Config_HttpClientErrorStatuses_FeatureFlagCustom:
    """Verify behavior of http clients"""

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
@features.trace_http_client_tag_query_string
class Test_Config_ClientTagQueryString_Empty:
    """Verify behavior when DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING set to empty string"""

    def setup_query_string_redaction_unset(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?hi=monkey"})

    def test_query_string_redaction_unset(self):
        trace = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        expected_tags = {"http.url": "http://weblog:7777/?hi=monkey"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault_3
@features.trace_http_client_tag_query_string
class Test_Config_ClientTagQueryString_Configured:
    """Verify behavior when DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING set to false"""

    def setup_query_string_redaction(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?hi=monkey"})

    def test_query_string_redaction(self):
        trace = [span for _, _, span in interfaces.library.get_spans(self.r, full_trace=True)]
        expected_tags = {"http.url": "http://weblog:7777/"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault_2
@features.trace_client_ip_header
class Test_Config_ClientIPHeader_Configured:
    """Verify headers containing ips are tagged when DD_TRACE_CLIENT_IP_ENABLED=true
    and DD_TRACE_CLIENT_IP_HEADER=custom-ip-header
    """

    def setup_ip_headers_sent_in_one_request(self):
        self.req = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777"}, headers={"custom-ip-header": "5.6.7.9"}
        )

    def test_ip_headers_sent_in_one_request(self):
        # Ensures the header set in DD_TRACE_CLIENT_IP_HEADER takes precedence over all supported ip headers
        trace = [span for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)]
        expected_tags = {"http.client_ip": "5.6.7.9"}
        assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


@scenarios.tracing_config_nondefault_3
@features.trace_client_ip_header
class Test_Config_ClientIPHeaderEnabled_False:
    """Verify headers containing ips are not tagged when by default, even with DD_TRACE_CLIENT_IP_HEADER=custom-ip-header"""

    def setup_ip_headers_sent_in_one_request(self):
        self.req = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777"}, headers={"custom-ip-header": "5.6.7.9"}
        )

    def test_ip_headers_sent_in_one_request(self):
        spans = [span for _, _, span in interfaces.library.get_spans(self.req, full_trace=True)]
        logger.info(spans)
        expected_tags = {"http.client_ip": "5.6.7.9"}
        assert _get_span_by_tags(spans, expected_tags) == {}


@scenarios.tracing_config_nondefault
@features.trace_client_ip_header
class Test_Config_ClientIPHeader_Precedence:
    """Verify headers containing ips are tagged when DD_TRACE_CLIENT_IP_ENABLED=true
    and headers are used to set http.client_ip in order of precedence
    """

    # Supported ip headers in order of precedence
    IP_HEADERS = (
        ("x-forwarded-for", "5.6.7.0"),
        ("x-real-ip", "8.7.6.5"),
        ("true-client-ip", "5.6.7.2"),
        ("x-client-ip", "5.6.7.3"),
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
        # Note - system tests may obfuscate the actual ip address, we may need to update
        # the test to take this into account.
        assert len(self.requests) == len(self.IP_HEADERS), "Number of requests and ip headers do not match, check setup"
        for i, header in enumerate(self.IP_HEADERS):
            req = self.requests[i]
            header_name, ip = header

            assert req.status_code == 200, f"Request with {header} is not succesful"

            logger.info(f"Checking request with header {header_name}={ip}")

            if ip.startswith("for="):
                ip = ip[4:]

            trace = [span for _, _, span in interfaces.library.get_spans(req, full_trace=True)]
            expected_tags = {"http.client_ip": ip}
            assert _get_span_by_tags(trace, expected_tags), f"Span with tags {expected_tags} not found in {trace}"


def _get_span_by_tags(spans, tags):
    logger.info(f"Try to find span with metag tags {tags}")

    for span in spans:
        meta = span["meta"]
        logger.debug(f"Checking span {span['span_id']} meta:\n{'\n'.join(map(str,meta.items()))}")
        # Avoids retrieving the client span by the operation/resource name, this value varies between languages
        # Use the expected tags to identify the span
        for k, v in tags.items():
            if k not in meta:
                logger.debug(f"Span {span['span_id']} does not have tag {k}")
                break
            elif meta[k] != v:
                logger.debug(f"Span {span['span_id']} has tag {k}={meta[k]} instead of {v}")
                break
        else:
            logger.info(f"Span found: {span['span_id']}")
            return span

    logger.warning("No span with those tags has been found")
    return {}


@features.envoy_external_processing
@features.unified_service_tagging
@scenarios.tracing_config_nondefault
@scenarios.external_processing
class Test_Config_UnifiedServiceTagging_CustomService:
    """Verify behavior of http clients and distributed traces"""

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
@features.unified_service_tagging
class Test_Config_UnifiedServiceTagging_Default:
    """Verify behavior of http clients and distributed traces"""

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
@features.integration_enablement
class Test_Config_IntegrationEnabled_False:
    """Verify behavior of integrations automatic spans"""

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
        if context.library == "php":
            assert (
                list(filter(lambda span: "pdo" in span.get("service"), spans)) == []
            ), f"PDO span was found in trace: {spans}"
        else:
            assert (
                list(filter(lambda span: "kafka.produce" in span.get("name"), spans)) == []
            ), f"kafka.produce span was found in trace: {spans}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_2
@features.integration_enablement
class Test_Config_IntegrationEnabled_True:
    """Verify behavior of integrations automatic spans"""

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
        # PHP uses the pdo integration
        if context.library == "php":
            assert list(
                filter(lambda span: "pdo" in span.get("service"), spans)
            ), f"No PDO span found in trace: {spans}"
        else:
            # Ruby kafka integration generates a span with the name "kafka.producer.*",
            # unlike python/dotnet/etc. which generates a "kafka.produce" span
            assert list(
                filter(lambda span: "kafka.produce" in span.get("name"), spans)
            ), f"No kafka.produce span found in trace: {spans}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_empty
@features.log_injection
@features.structured_log_injection
class Test_Config_LogInjection_Enabled:
    """Verify log injection behavior when enabled"""

    def setup_log_injection_enabled(self):
        self.message = "Test_Config_LogInjection_Enabled.test_log_injection_enabled"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_log_injection_enabled(self):
        assert self.r.status_code == 200
        msg = parse_log_injection_message(self.message)

        tid = parse_log_trace_id(msg)
        assert tid is not None, "Expected a trace ID, but got None"
        sid = parse_log_span_id(msg)
        assert sid is not None, "Expected a span ID, but got None"

        required_fields = ["service", "version", "env"]
        if context.library.name in ("java", "python", "ruby", "php"):
            required_fields = ["dd.service", "dd.version", "dd.env"]
        elif context.library.name == "dotnet":
            required_fields = ["dd_service", "dd_version", "dd_env"]

        for field in required_fields:
            assert field in msg, f"Missing field: {field}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_2
@features.log_injection
@features.structured_log_injection
class Test_Config_LogInjection_Default_Structured:
    """Verify log injection is enabled by default for structured logs"""

    def setup_test_log_injection_default(self):
        self.message = "Test_Config_LogInjection_Default_Structured.test_log_injection_default"
        self.r = weblog.get("/log/library", params={"msg": self.message, "structured": True})

    def test_test_log_injection_default(self):
        assert self.r.status_code == 200
        log_records = get_trace_details_structured(self.message)
        assert len(log_records) == 1, f"Expected one structured log record {log_records}"

        tid = parse_log_trace_id(log_records[0])
        assert tid is not None, f"Expected a trace ID, but got None {log_records[0]}"
        sid = parse_log_span_id(log_records[0])
        assert sid is not None, f"Expected a span ID, but got None {log_records[0]}"


# Using TRACING_CONFIG_NONDEFAULT_2 for dd-trace-java since the default value is under the DD_TRACE_EXPERIMENTAL_FEATURES_ENABLED
# TODO: Change scenarios back to DEFAULT once all libraries change it to true
@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_2
@features.log_injection
@features.unstructured_log_injection
class Test_Config_LogInjection_Default_Unstructured:
    """Verify log injection is disabled by default for unstructured logs"""

    def setup_test_log_injection_default(self):
        self.message = "Test_Config_LogInjection_Default_Unstructured.test_log_injection_default"
        self.r = weblog.get("/log/library", params={"msg": self.message, "structured": False})

    def test_test_log_injection_default(self):
        assert self.r.status_code == 200
        trace_details = get_trace_details_unstructured(self.message)
        assert not trace_details, f"Expected no trace details in unstructured log message, but got: {trace_details}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_empty
@features.log_injection
@features.log_injection_128bit_traceid
@bug(context.library == "golang@2.1.0", reason="LANGPLAT-670")
class Test_Config_LogInjection_128Bit_TraceId_Enabled:
    """Verify trace IDs are logged in 128bit format by default when log injection is enabled"""

    def setup_new_traceid(self):
        self.message = "Test_Config_LogInjection_128Bit_TraceId_Enabled.test_new_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_new_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^[0-9a-f]{32}$", trace_id), f"Invalid 128-bit trace_id: {trace_id}"

    def setup_incoming_64bit_traceid(self):
        incoming_headers = {
            "x-datadog-trace-id": "1",
            "x-datadog-parent-id": "1",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.dm=-4",
        }

        self.message = "Test_Config_LogInjection_128Bit_TraceId_Enabled.test_incoming_64bit_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message}, headers=incoming_headers)

    @incomplete_test_app(
        context.library == "ruby", reason="rails70 app does not use the incoming headers in log correlation"
    )
    def test_incoming_64bit_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^\d{1,20}$", str(trace_id)), f"Invalid 64-bit trace_id: {trace_id}"

    def setup_incoming_128bit_traceid(self):
        incoming_headers = {
            "x-datadog-trace-id": "2",
            "x-datadog-parent-id": "2",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
        }

        self.message = "Test_Config_LogInjection_128Bit_TraceId_Enabled.test_incoming_128bit_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message}, headers=incoming_headers)

    def test_incoming_128bit_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^[0-9a-f]{32}$", trace_id), f"Invalid 128-bit trace_id: {trace_id}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_4
@features.log_injection
@features.log_injection_128bit_traceid
@bug(context.library == "golang@2.1.0", reason="LANGPLAT-670")
@irrelevant(
    context.library == "python", reason="The Python tracer does not support disabling logging 128-bit trace IDs"
)
class Test_Config_LogInjection_128Bit_TraceId_Disabled:
    """Verify 128 bit traceid are disabled in log injection when DD_TRACE_128_BIT_TRACEID_LOGGING_ENABLED=false"""

    def setup_new_traceid(self):
        self.message = "Test_Config_LogInjection_128Bit_TraceId_Disabled.test_new_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_new_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^\d{1,20}$", str(trace_id)), f"Invalid 64-bit trace_id: {trace_id}"

    def setup_incoming_64bit_traceid(self):
        incoming_headers = {
            "x-datadog-trace-id": "1",
            "x-datadog-parent-id": "1",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.dm=-4",
        }

        self.message = "Test_Config_LogInjection_128Bit_TraceId_Disabled.test_incoming_64bit_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message}, headers=incoming_headers)

    def test_incoming_64bit_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^\d{1,20}$", str(trace_id)), f"Invalid 64-bit trace_id: {trace_id}"

    def setup_incoming_128bit_traceid(self):
        incoming_headers = {
            "x-datadog-trace-id": "2",
            "x-datadog-parent-id": "2",
            "x-datadog-sampling-priority": "2",
            "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
        }

        self.message = "Test_Config_LogInjection_128Bit_TraceId_Disabled.test_incoming_128bit_traceid"
        self.r = weblog.get("/log/library", params={"msg": self.message}, headers=incoming_headers)

    def test_incoming_128bit_traceid(self):
        assert self.r.status_code == 200
        log_msg = parse_log_injection_message(self.message)

        trace_id = parse_log_trace_id(log_msg)
        assert re.match(r"^\d{1,20}$", str(trace_id)), f"Invalid 64-bit trace_id: {trace_id}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.runtime_metrics_enabled
@features.runtime_metrics
class Test_Config_RuntimeMetrics_Enabled:
    """Verify runtime metrics are enabled when DD_RUNTIME_METRICS_ENABLED=true and that they have the proper tags"""

    def setup_main(self):
        self.req = weblog.get("/")

        # Wait for 10s to allow the tracer to send runtime metrics on the default 10s interval
        time.sleep(10)

    def test_main(self):
        assert self.req.status_code == 200

        runtime_metrics_gauges, runtime_metrics_sketches = get_runtime_metrics(interfaces.agent)

        assert len(runtime_metrics_gauges) > 0 or len(runtime_metrics_sketches) > 0

        runtime_metrics = runtime_metrics_gauges if len(runtime_metrics_gauges) > 0 else runtime_metrics_sketches

        for metric in runtime_metrics:
            tags = {tag.split(":")[0]: tag.split(":")[1] for tag in metric["tags"]}
            language_tag_key, language_tag_value = runtime_metrics_lang_map[context.library.name]
            if language_tag_key is not None:
                assert tags.get(language_tag_key) == language_tag_value

            # Test that Unified Service Tags are added to the runtime metrics
            assert tags["service"] == "weblog"
            assert tags["env"] == "system-tests"
            assert tags["version"] == "1.0.0"

            # Test that DD_TAGS are added to the runtime metrics
            # DD_TAGS=key1:val1,key2:val2 in default weblog containers
            assert tags["key1"] == "val1"
            assert tags["key2"] == "val2"


@scenarios.runtime_metrics_enabled
@features.runtime_metrics
class Test_Config_RuntimeMetrics_Enabled_WithRuntimeId:
    """Verify runtime metrics are enabled when DD_RUNTIME_METRICS_ENABLED=true and that they have the runtime-id tag"""

    def setup_main(self):
        self.req = weblog.get("/")

        # Wait for 10s to allow the tracer to send runtime metrics on the default 10s interval
        time.sleep(10)

    def test_main(self):
        assert self.req.status_code == 200

        runtime_metrics_gauges, runtime_metrics_sketches = get_runtime_metrics(interfaces.agent)

        assert len(runtime_metrics_gauges) > 0 or len(runtime_metrics_sketches) > 0

        runtime_metrics = runtime_metrics_gauges if len(runtime_metrics_gauges) > 0 else runtime_metrics_sketches

        for metric in runtime_metrics:
            tags = {tag.split(":")[0]: tag.split(":")[1] for tag in metric["tags"]}
            assert "runtime-id" in tags


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.default
@features.runtime_metrics
class Test_Config_RuntimeMetrics_Default:
    """Verify runtime metrics are disabled by default"""

    # test that by default runtime metrics are disabled
    def setup_main(self):
        self.req = weblog.get("/")

        # Wait for 10s to allow the tracer to send runtime metrics on the default 10s interval
        time.sleep(10)

    def test_main(self):
        assert self.req.status_code == 200

        runtime_metrics_gauges, runtime_metrics_sketches = get_runtime_metrics(interfaces.agent)

        assert len(runtime_metrics_gauges) == 0
        assert len(runtime_metrics_sketches) == 0


def get_runtime_metrics(agent):
    runtime_metrics_gauges = [
        metric
        for _, metric in agent.get_metrics()
        if metric["metric"].startswith("runtime.") or metric["metric"].startswith("jvm.")
    ]

    runtime_metrics_sketches = [
        metric
        for _, metric in agent.get_sketches()
        if metric["metric"].startswith("runtime.") or metric["metric"].startswith("jvm.")
    ]

    return runtime_metrics_gauges, runtime_metrics_sketches


def parse_log_injection_message(log_message: str) -> dict:
    if context.library == "ruby":
        # TODO: Update ruby weblog app to support structured logs
        trace_details = get_trace_details_unstructured(log_message)
    else:
        trace_details = get_trace_details_structured(log_message)

    if not trace_details:
        raise ValueError(f"Did not find any log with {log_message}. Trace details: {trace_details}")
    elif len(trace_details) > 1:
        raise ValueError(f"Found more than one log with {log_message}. Trace details: {trace_details}")
    return trace_details[0]


def get_trace_details_unstructured(log_message: str) -> list[dict]:
    """Extract Datadog trace details from unstructured logs that contain
    Datadog key-value attributes prefixed with `dd.`.
    """
    if len(log_message.split()) != 1:
        raise ValueError(f"Log message must be a single word, got: {log_message}")

    results = []
    processed_logs: set[str] = set()

    # Matches logs like: dd.trace_id=... dd.span_id=... actual_log_message
    log_pattern = re.compile(r"((?:dd\.\w+=\S+\s*)+)")

    for data in stdout.get_data():
        raw_log: str = data.get("raw")
        if raw_log in processed_logs:
            continue
        processed_logs.add(raw_log)
        # Split the raw logs into lines to process each record separately
        for log_line in raw_log.splitlines():
            match = log_pattern.search(log_line)
            if not match:
                # Skip lines that do not match the expected pattern
                logger.debug(f"Log line does not contain `dd.` attributes: {log_line}")
                continue
            # Check if the log message matches the expected log message
            extracted_message = get_log_message_from_record(log_line)
            logger.debug(f"Log line: {log_line}, Extracted log message: {extracted_message}, Expected: {log_message}")
            if log_message != extracted_message:
                continue
            # Extract all dd.*=value pairs
            dd_pairs = match.group(1).strip().split()
            trace_details = {pair.split("=")[0]: pair.split("=")[1] for pair in dd_pairs}
            logger.debug(f"Found unstructured log with trace details: {trace_details}")
            results.append(trace_details)
    return results


def get_trace_details_structured(log_message: str) -> list[dict]:
    """Extract Datadog trace details from structured logs (JSON format),
    where trace attributes are stored under common keys like 'dd', 'mdc', or 'record'.
    """
    results = []
    processed_logs: set[str] = set()

    # Match the first JSON object in the log line
    json_pattern = re.compile(r"({.*})")

    for data in stdout.get_data():
        raw_log: str = data.get("raw")
        if raw_log in processed_logs:
            continue
        processed_logs.add(raw_log)

        for log_line in raw_log.splitlines():
            logger.debug(f"Processing structured log line: {log_line}")
            try:
                json_string = json_pattern.search(log_line).group(1)  # type: ignore[union-attr]
                log_record = json.loads(json_string)
            except Exception:  # noqa: S112
                continue
            # Locate log with the custom message, which should have the trace ID and span ID
            if get_log_message_from_record(log_record) != log_message:
                continue

            logger.debug(f"Found structured log matching message: {data}")

            # Extract trace details from known keys
            if "dd" in log_record:
                results.append(log_record["dd"])
            elif "mdc" in log_record:
                results.append(log_record["mdc"])  # Java tracer key
            elif "record" in log_record:
                results.append(log_record["record"].get("extra"))  # Python Loguru key
            else:
                results.append(log_record)  # Fallback to entire record if no known key found

    return results


def get_log_message_from_record(record: dict | str) -> str | None:
    """Extract the log message from a structured or unstructured log record."""
    if isinstance(record, str):
        # If log is unstructured, extract the log message from the end of the line.
        return record.strip().split()[-1] if record.strip() else ""
    elif context.library.name == "dotnet":
        return record.get("@mt")
    elif context.library.name == "python":
        return record.get("record", {}).get("message")
    elif context.library.name == "golang":
        return record.get("msg")
    return record.get("message")


def parse_log_trace_id(record: dict) -> str:
    # APMAPI-1199: update nodejs to use dd.trace_id instead of trace_id
    # APMAPI-1234: update dotnet to use dd.trace_id instead of dd_trace_id
    return record.get("dd.trace_id", record.get("trace_id", record.get("dd_trace_id")))


def parse_log_span_id(record: dict) -> str:
    # APMAPI-1199: update nodejs to use dd.span_id instead of span_id
    # APMAPI-1234: update dotnet to use dd.span_id instead of dd_span_id
    return record.get("dd.span_id", record.get("span_id", record.get("dd_span_id")))

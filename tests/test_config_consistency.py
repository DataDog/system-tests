# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import re
import json
import time
from utils import weblog, interfaces, scenarios, features, rfc, irrelevant, context, bug, missing_feature
from utils.tools import logger

# get the default log output
stdout = interfaces.library_stdout if context.library != "dotnet" else interfaces.library_dotnet_managed
runtime_metrics = {"nodejs": "runtime.node.mem.heap_total"}
runtime_metrics_langs = [".NET", "go", "nodejs", "python", "ruby"]
log_injection_fields = {"nodejs": {"message": "msg"}}


@scenarios.default
@features.tracing_configuration_consistency
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
@features.tracing_configuration_consistency
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
@features.tracing_configuration_consistency
class Test_Config_ObfuscationQueryStringRegexp_Empty:
    """Verify behavior when set to empty string"""

    def setup_query_string_obfuscation_empty_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?key=monkey"})

    @bug(context.library == "java", reason="APMAPI-770")
    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(context.library < "golang@1.72.0-dev", reason="Obfuscation only occurs on server side")
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
@features.tracing_configuration_consistency
class Test_Config_ObfuscationQueryStringRegexp_Configured:
    def setup_query_string_obfuscation_configured_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?ssn=123-45-6789"})

    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(
        context.library < "golang@1.72.0-dev",
        reason="Client query string collection disabled by default; obfuscation only occurs on server side",
    )
    @missing_feature(
        context.library == "java" and context.weblog_variant in ("vertx3", "vertx4"),
        reason="Missing endpoint",
    )
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


@features.tracing_configuration_consistency
class Test_Config_ObfuscationQueryStringRegexp_Default:
    def setup_query_string_obfuscation_configured_client(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/?token=value"})

    @missing_feature(context.library == "nodejs", reason="Node only obfuscates queries on the server side")
    @missing_feature(
        context.library < "golang@1.72.0-dev",
        reason="Client query string collection disabled by default; obfuscation only occurs on server side",
    )
    @missing_feature(
        context.library == "java" and context.weblog_variant in ("vertx3", "vertx4"),
        reason="Missing endpoint",
    )
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
@features.tracing_configuration_consistency
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
        assert client_span.get("error") == None or client_span.get("error") == 0


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
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


@scenarios.tracing_config_nondefault_3
@features.tracing_configuration_consistency
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
        # Avoids retrieving the client span by the operation/resource name, this value varies between languages
        # Use the expected tags to identify the span
        for k, v in tags.items():
            meta = span["meta"]

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
@features.tracing_configuration_consistency
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
@features.tracing_configuration_consistency
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
@features.tracing_configuration_consistency
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
@features.tracing_configuration_consistency
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
@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_LogInjection_Enabled:
    """Verify log injection behavior when enabled"""

    def setup_log_injection_enabled(self):
        self.message = "msg"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_log_injection_enabled(self):
        assert self.r.status_code == 200
        pattern = r'"dd":\{[^}]*\}'
        stdout.assert_presence(pattern)
        dd = parse_log_injection_message(self.message)
        required_fields = ["trace_id", "span_id", "service", "version", "env"]
        for field in required_fields:
            assert field in dd, f"Missing field: {field}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_LogInjection_Default:
    """Verify log injection is disabled by default"""

    def setup_log_injection_default(self):
        self.message = "msg"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_log_injection_default(self):
        assert self.r.status_code == 200
        pattern = r'"dd":\{[^}]*\}'
        stdout.assert_absence(pattern)


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_LogInjection_128Bit_TradeId_Default:
    """Verify trace IDs are logged in 128bit format when log injection is enabled"""

    def setup_log_injection_128bit_traceid_default(self):
        self.message = "msg"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_log_injection_128bit_traceid_default(self):
        assert self.r.status_code == 200
        pattern = r'"dd":\{[^}]*\}'
        stdout.assert_presence(pattern)
        dd = parse_log_injection_message(self.message)
        trace_id = dd.get("trace_id")
        assert re.match(r"^[0-9a-f]{32}$", trace_id), f"Invalid 128-bit trace_id: {trace_id}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.tracing_config_nondefault_3
@features.tracing_configuration_consistency
class Test_Config_LogInjection_128Bit_TradeId_Disabled:
    """Verify 128 bit traceid are disabled in log injection when DD_TRACE_128_BIT_TRACEID_LOGGING_ENABLED=false"""

    def setup_log_injection_128bit_traceid_disabled(self):
        self.message = "msg"
        self.r = weblog.get("/log/library", params={"msg": self.message})

    def test_log_injection_128bit_traceid_disabled(self):
        assert self.r.status_code == 200
        pattern = r'"dd":\{[^}]*\}'
        stdout.assert_presence(pattern)
        dd = parse_log_injection_message(self.message)
        trace_id = dd.get("trace_id")
        assert re.match(r"^\d{1,20}$", trace_id), f"Invalid 64-bit trace_id: {trace_id}"


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.runtime_metrics_enabled
@features.tracing_configuration_consistency
class Test_Config_RuntimeMetrics_Enabled:
    """Verify runtime metrics are enabled when DD_RUNTIME_METRICS_ENABLED=true and that they have the proper tags"""

    def setup_main(self):
        self.req = weblog.get("/")

        # Wait for 10s to allow the tracer to send runtime metrics on the default 10s interval
        time.sleep(10)

    def test_main(self):
        assert self.req.status_code == 200

        runtime_metrics = [
            metric
            for _, metric in interfaces.agent.get_metrics()
            if metric["metric"].startswith("runtime.") or metric["metric"].startswith("jvm.")
        ]
        assert len(runtime_metrics) > 0

        for metric in runtime_metrics:
            tags = {tag.split(":")[0]: tag.split(":")[1] for tag in metric["tags"]}
            assert tags.get("lang") in runtime_metrics_langs or tags.get("lang") is None

            # Test that Unified Service Tags are added to the runtime metrics
            assert tags["service"] == "weblog"
            assert tags["env"] == "system-tests"
            assert tags["version"] == "1.0.0"

            # Test that DD_TAGS are added to the runtime metrics
            # DD_TAGS=key1:val1,key2:val2 in default weblog containers
            assert tags["key1"] == "val1"
            assert tags["key2"] == "val2"


@scenarios.runtime_metrics_enabled
@features.tracing_configuration_consistency
class Test_Config_RuntimeMetrics_Enabled_WithRuntimeId:
    """Verify runtime metrics are enabled when DD_RUNTIME_METRICS_ENABLED=true and that they have the runtime-id tag"""

    def setup_main(self):
        self.req = weblog.get("/")

        # Wait for 10s to allow the tracer to send runtime metrics on the default 10s interval
        time.sleep(10)

    def test_main(self):
        assert self.req.status_code == 200

        runtime_metrics = [
            metric
            for _, metric in interfaces.agent.get_metrics()
            if metric["metric"].startswith("runtime.") or metric["metric"].startswith("jvm.")
        ]
        assert len(runtime_metrics) > 0

        for metric in runtime_metrics:
            tags = {tag.split(":")[0]: tag.split(":")[1] for tag in metric["tags"]}
            assert "runtime-id" in tags


@rfc("https://docs.google.com/document/d/1kI-gTAKghfcwI7YzKhqRv2ExUstcHqADIWA4-TZ387o/edit#heading=h.8v16cioi7qxp")
@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_RuntimeMetrics_Default:
    """Verify runtime metrics are disabled by default"""

    # test that by default runtime metrics are disabled
    def test_config_runtimemetrics_default(self):
        iterations = 0
        for data in interfaces.library.get_data("/dogstatsd/v2/proxy"):
            iterations += 1
        assert iterations == 0, "Runtime metrics are enabled by default"


# Parse the JSON-formatted log message from stdout and return the 'dd' object
def parse_log_injection_message(log_message):
    for data in stdout.get_data():
        try:
            message = json.loads(data.get("message"))
        except json.JSONDecodeError:
            continue
        if message.get("dd") and message.get(log_injection_fields[context.library.library]["message"]) == log_message:
            dd = message.get("dd")
            return dd

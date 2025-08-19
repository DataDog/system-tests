# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, rfc, context
from utils.dd_constants import Capabilities
from utils._context._scenarios.dynamic import dynamic_scenario
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric,
    validate_metric_v2,
    BaseRulesVersion,
    BaseWAFVersion,
)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_UrlQuery:
    """Server-side request forgery through query parameters"""

    def setup_ssrf_get(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_get(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url", "value": expected_http_value},
                "params": {"address": "server.request.query", "value": "169.254.169.254"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_BodyUrlEncoded:
    """Server-side request forgery through a url-encoded body parameter"""

    def setup_ssrf_post_urlencoded(self):
        self.r = weblog.post("/rasp/ssrf", data={"domain": "169.254.169.254"})

    def test_ssrf_post_urlencoded(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {
                    "address": "server.io.net.url",
                    "value": expected_http_value,
                },
                "params": {
                    "address": "server.request.body",
                    "value": "169.254.169.254",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_BodyXml:
    """Server-side request forgery through an xml body parameter"""

    def setup_ssrf_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><domain>169.254.169.254</domain>"
        self.r = weblog.post("/rasp/ssrf", data=data, headers={"Content-Type": "application/xml"})

    def test_ssrf_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {
                    "address": "server.io.net.url",
                    "value": "http://169.254.169.254",
                },
                "params": {
                    "address": "server.request.body",
                    "value": "169.254.169.254",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_BodyJson:
    """Server-side request forgery through a json body parameter"""

    def setup_ssrf_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/ssrf", json={"domain": "169.254.169.254"})

    def test_ssrf_post_json(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {
                    "address": "server.io.net.url",
                    "value": expected_http_value,
                },
                "params": {
                    "address": "server.request.body",
                    "value": "169.254.169.254",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_ssrf_span_tags(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_ssrf_span_tags(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_span_tags(self):
        validate_span_tags(
            self.r,
            expected_metrics=[
                "_dd.appsec.rasp.duration_ext",
                "_dd.appsec.rasp.rule.eval",
            ],
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.enmf90juqidf")
@features.rasp_stack_trace
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_ssrf_stack_trace(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_ssrf_telemetry(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric("rasp.rule.eval", "ssrf", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        assert any(validate_metric("rasp.rule.match", "ssrf", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@features.rasp_server_side_request_forgery
@dynamic_scenario(
    mandatory={
        "DD_APPSEC_RASP_ENABLED": "true",
        "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json",
        "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true",
    }
)
class Test_Ssrf_Telemetry_V2:
    """Validate Telemetry data on exploit attempts"""

    def setup_ssrf_telemetry(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_v2("rasp.rule.eval", "ssrf", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        block_action = "block:irrelevant" if context.weblog_variant == "nextjs" else "block:success"
        assert any(validate_metric_v2("rasp.rule.match", "ssrf", s, block_action=block_action) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.mshauo3jp6wh")
@features.rasp_server_side_request_forgery
@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "None"})
class Test_Ssrf_Capability:
    """Validate that ASM_RASP_SSRF (23) capability is sent"""

    def test_ssrf_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_RASP_SSRF)


@features.rasp_server_side_request_forgery
class Test_Ssrf_Rules_Version(BaseRulesVersion):
    """Test ssrf min rules version"""

    min_version = "1.13.2"


@features.rasp_server_side_request_forgery
class Test_Ssrf_Waf_Version(BaseWAFVersion):
    """Test ssrf WAF version"""

    min_version = "1.20.1"

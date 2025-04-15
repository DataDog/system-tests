# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, context
from utils.dd_constants import Capabilities
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric,
    validate_metric_v2,
    BaseRulesVersion,
    BaseWAFVersion,
)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_UrlQuery:
    """SQL Injection through query parameters"""

    def setup_sqli_get(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.query", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyUrlEncoded:
    """SQL Injection through a url-encoded body parameter"""

    def setup_sqli_post_urlencoded(self):
        self.r = weblog.post("/rasp/sqli", data={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyXml:
    """SQL Injection through an xml body parameter"""

    def setup_sqli_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><user_id>' OR 1 = 1 --</user_id>"
        self.r = weblog.post("/rasp/sqli", data=data, headers={"Content-Type": "application/xml"})

    def test_sqli_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyJson:
    """SQL Injection through a json body parameter"""

    def setup_sqli_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/sqli", json={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_sqli_span_tags(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_sqli_span_tags(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration_ext", "_dd.appsec.rasp.rule.eval"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.enmf90juqidf")
@features.rasp_stack_trace
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_sqli_stack_trace(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_sqli_telemetry(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric("rasp.rule.eval", "sql_injection", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        assert any(validate_metric("rasp.rule.match", "sql_injection", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_Telemetry_V2:
    """Validate Telemetry data on exploit attempts"""

    def setup_sqli_telemetry(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_v2("rasp.rule.eval", "sql_injection", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        block_action = "block:irrelevant" if context.weblog_variant == "nextjs" else "block:success"
        assert any(
            validate_metric_v2("rasp.rule.match", "sql_injection", s, block_action=block_action) for s in series_match
        ), [s.get("tags") for s in series_match]


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.mshauo3jp6wh")
@features.rasp_sql_injection
@scenarios.remote_config_mocked_backend_asm_dd
class Test_Sqli_Capability:
    """Validate that ASM_RASP_SQLI (21) capability is sent"""

    def test_sqli_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_RASP_SQLI)


@features.rasp_sql_injection
class Test_Sqli_Rules_Version(BaseRulesVersion):
    """Test Sqli min rules version"""

    min_version = "1.13.2"


@features.rasp_sql_injection
class Test_Sqli_Waf_Version(BaseWAFVersion):
    """Test sqli WAF version"""

    min_version = "1.20.1"

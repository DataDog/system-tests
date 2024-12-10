# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc
from utils import remote_config as rc
from utils.dd_constants import Capabilities
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric,
    RC_CONSTANTS,
    Base_Rules_Version,
    Base_WAF_Version,
)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_UrlQuery:
    """Local file inclusion through query parameters"""

    def setup_lfi_get(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyUrlEncoded:
    """Local file inclusion through a url-encoded body parameter"""

    def setup_lfi_post_urlencoded(self):
        self.r = weblog.post("/rasp/lfi", data={"file": "../etc/passwd"})

    def test_lfi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyXml:
    """Local file inclusion through an xml body parameter"""

    def setup_lfi_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><file>../etc/passwd</file>"
        self.r = weblog.post("/rasp/lfi", data=data, headers={"Content-Type": "application/xml"})

    def test_lfi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyJson:
    """Local file inclusion through a json body parameter"""

    def setup_lfi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/lfi", json={"file": "../etc/passwd"})

    def test_lfi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_lfi_span_tags(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_lfi_span_tags(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_span_tags(self):
        validate_span_tags(
            self.r, expected_metrics=["_dd.appsec.rasp.duration_ext", "_dd.appsec.rasp.rule.eval",],
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.enmf90juqidf")
@features.rasp_stack_trace
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_lfi_stack_trace(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_lfi_telemetry(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_telemetry(self):
        series_eval = find_series(True, "appsec", "rasp.rule.eval")
        assert series_eval
        assert any(validate_metric("rasp.rule.eval", "lfi", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series(True, "appsec", "rasp.rule.match")
        assert series_match
        assert any(validate_metric("rasp.rule.match", "lfi", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_runtime_activation
class Test_Lfi_RC_CustomAction:
    """Local file inclusion through query parameters"""

    def setup_lfi_get(self):
        self.config_state_1 = rc.rc_state.reset().set_config(*RC_CONSTANTS.CONFIG_ENABLED).apply()
        self.config_state_1b = rc.rc_state.set_config(*RC_CONSTANTS.RULES).apply()
        self.r1 = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

        self.config_state_2 = rc.rc_state.set_config(*RC_CONSTANTS.BLOCK_505).apply()
        self.r2 = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

        self.config_state_3 = rc.rc_state.set_config(*RC_CONSTANTS.BLOCK_REDIRECT).apply()
        self.r3 = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"}, allow_redirects=False)

        self.config_state_4 = rc.rc_state.del_config(RC_CONSTANTS.BLOCK_REDIRECT[0]).apply()
        self.r4 = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

        self.config_state_5 = rc.rc_state.reset().apply()
        self.r5 = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_get(self):
        assert self.config_state_1[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state_1b[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r1.status_code == 403
        interfaces.library.assert_rasp_attack(
            self.r1,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

        assert self.config_state_2[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r2.status_code == 505
        interfaces.library.assert_rasp_attack(
            self.r2,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

        assert self.config_state_3[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r3.status_code == 302
        assert self.r3.headers["Location"] == "http://google.com"

        interfaces.library.assert_rasp_attack(
            self.r3,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

        assert self.config_state_4[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r4.status_code == 403
        interfaces.library.assert_rasp_attack(
            self.r4,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

        assert self.config_state_5[rc.RC_STATE] == rc.ApplyState.ACKNOWLEDGED
        assert self.r5.status_code == 200

        interfaces.library.assert_no_appsec_event(self.r5)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.mshauo3jp6wh")
@features.rasp_local_file_inclusion
@scenarios.remote_config_mocked_backend_asm_dd
class Test_Lfi_Capability:
    """Validate that ASM_RASP_LFI (22) capability is sent"""

    def test_lfi_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_RASP_LFI)


@features.rasp_local_file_inclusion
class Test_Lfi_Rules_Version(Base_Rules_Version):
    """Test lfi min rules version"""

    min_version = "1.13.3"


@features.rasp_local_file_inclusion
class Test_Lfi_Waf_Version(Base_WAF_Version):
    """Test lfi WAF version"""

    min_version = "1.20.1"

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc
from utils.dd_constants import Capabilities
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric,
    validate_metric_variant,
    Base_Rules_Version,
    Base_WAF_Version,
)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_UrlQuery:
    """Shell Injection through query parameters"""

    def setup_shi_get(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "value": "ls $(cat /etc/passwd 1>&2 ; echo .)",},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd 1>&2 ; echo .)",},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyUrlEncoded:
    """Shell Injection through a url-encoded body parameter"""

    def setup_shi_post_urlencoded(self):
        self.r = weblog.post("/rasp/shi", data={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "value": "ls $(cat /etc/passwd 1>&2 ; echo .)",},
                "params": {"address": "server.request.body", "value": "$(cat /etc/passwd 1>&2 ; echo .)",},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyXml:
    """Shell Injection through an xml body parameter"""

    def setup_shi_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><list_dir>$(cat /etc/passwd 1>&amp;2 ; echo .)</list_dir>"
        self.r = weblog.post("/rasp/shi", data=data, headers={"Content-Type": "application/xml"})

    def test_shi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "value": "ls $(cat /etc/passwd 1>&2 ; echo .)",},
                "params": {"address": "server.request.body", "value": "$(cat /etc/passwd 1>&2 ; echo .)",},
            },
        )


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_BodyJson:
    """Shell Injection through a json body parameter"""

    def setup_shi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/shi", json={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd", "value": "ls $(cat /etc/passwd 1>&2 ; echo .)",},
                "params": {"address": "server.request.body", "value": "$(cat /etc/passwd 1>&2 ; echo .)",},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_shi_span_tags(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_shi_span_tags(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_span_tags(self):
        validate_span_tags(
            self.r, expected_metrics=["_dd.appsec.rasp.duration_ext", "_dd.appsec.rasp.rule.eval",],
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.enmf90juqidf")
@features.rasp_stack_trace
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_shi_stack_trace(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_stack_trace(self):
        assert self.r.status_code == 403
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_shi_telemetry(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_telemetry(self):
        assert self.r.status_code == 403

        series_eval = find_series(True, "appsec", "rasp.rule.eval")
        assert series_eval
        assert any(validate_metric("rasp.rule.eval", "command_injection", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series(True, "appsec", "rasp.rule.match")
        assert series_match
        assert any(validate_metric("rasp.rule.match", "command_injection", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_shell_injection
@scenarios.appsec_rasp
class Test_Shi_Telemetry_Variant_Tag:
    """Validate Telemetry data variant tag on exploit attempts"""

    def setup_shi_telemetry(self):
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd 1>&2 ; echo .)"})

    def test_shi_telemetry(self):
        assert self.r.status_code == 403

        series_eval = find_series(True, "appsec", "rasp.rule.eval")
        assert series_eval
        assert any(validate_metric_variant("rasp.rule.eval", "command_injection", "shell", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series(True, "appsec", "rasp.rule.match")
        assert series_match
        assert any(validate_metric_variant("rasp.rule.match", "command_injection", "shell", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.rasp_shell_injection
@scenarios.remote_config_mocked_backend_asm_dd
class Test_Shi_Capability:
    """Validate that ASM_RASP_SHI (24) capability is sent"""

    def test_shi_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_RASP_SHI)


@features.rasp_local_file_inclusion
class Test_Shi_Rules_Version(Base_Rules_Version):
    """Test shi min rules version"""

    min_version = "1.13.1"


@features.rasp_local_file_inclusion
class Test_Shi_Waf_Version(Base_WAF_Version):
    """Test shi WAF version"""

    min_version = "1.20.1"

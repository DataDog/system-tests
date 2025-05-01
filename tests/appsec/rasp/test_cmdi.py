# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, context
from utils.dd_constants import Capabilities
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric_variant,
    validate_metric_variant_v2,
    BaseRulesVersion,
    BaseWAFVersion,
)


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_UrlQuery:
    """Command Injection through query parameters"""

    def setup_cmdi_get(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {
                    "address": "server.sys.exec.cmd",
                    "value": "/usr/bin/touch /tmp/passwd",
                },
                "params": {
                    "address": "server.request.query",
                    "value": "/usr/bin/touch /tmp/passwd",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyUrlEncoded:
    """Command Injection through a url-encoded body parameter"""

    def setup_cmdi_post_urlencoded(self):
        self.r = weblog.post("/rasp/cmdi", data={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {
                    "address": "server.sys.exec.cmd",
                    "value": "/usr/bin/touch /tmp/passwd",
                },
                "params": {
                    "address": "server.request.body",
                    "value": "/usr/bin/touch /tmp/passwd",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyXml:
    """Command Injection through an xml body parameter"""

    def setup_cmdi_post_xml(self):
        data = (
            "<?xml version='1.0' encoding='utf-8'?><command><cmd>/usr/bin/touch</cmd><cmd>/tmp/passwd</cmd></command>"
        )
        self.r = weblog.post("/rasp/cmdi", data=data, headers={"Content-Type": "application/xml"})

    def test_cmdi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {"address": "server.sys.exec.cmd", "value": '/usr/bin/touch "/tmp/passwd"'},
                "params": {"address": "server.request.body", "value": "/usr/bin/touch"},
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyJson:
    """Command Injection through a json body parameter"""

    def setup_cmdi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/cmdi", json={"command": ["/usr/bin/touch", "/tmp/passwd"]})

    def test_cmdi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {
                    "address": "server.sys.exec.cmd",
                    "value": '/usr/bin/touch "/tmp/passwd"',
                },
                "params": {
                    "address": "server.request.body",
                    "value": "/usr/bin/touch",
                },
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_span_tags
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_cmdi_span_tags(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_span_tags
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_cmdi_span_tags(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration_ext", "_dd.appsec.rasp.rule.eval"])


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_stack_trace
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_cmdi_stack_trace(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_cmdi_telemetry(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_variant("rasp.rule.eval", "command_injection", "exec", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        assert any(validate_metric_variant("rasp.rule.match", "command_injection", "exec", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Telemetry_V2:
    """Validate Telemetry data on exploit attempts"""

    def setup_cmdi_telemetry(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_variant_v2("rasp.rule.eval", "command_injection", "exec", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match

        block_action = "block:irrelevant" if context.weblog_variant == "nextjs" else "block:success"

        assert any(
            validate_metric_variant_v2("rasp.rule.match", "command_injection", "exec", s, block_action=block_action)
            for s in series_match
        ), [s.get("tags") for s in series_match]


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Telemetry_Variant_Tag:
    """Validate Telemetry data variant tag on exploit attempts"""

    def setup_cmdi_telemetry(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/usr/bin/touch /tmp/passwd"})

    def test_cmdi_telemetry(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_variant("rasp.rule.eval", "command_injection", "exec", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match
        assert any(validate_metric_variant("rasp.rule.match", "command_injection", "exec", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.remote_config_mocked_backend_asm_dd
class Test_Cmdi_Capability:
    """Validate that ASM_RASP_CMDI (37) capability is sent"""

    def test_cmdi_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_RASP_CMDI)


@features.rasp_command_injection
class Test_Cmdi_Rules_Version(BaseRulesVersion):
    """Test cmdi min rules version"""

    min_version = "1.13.3"


@features.rasp_command_injection
class Test_Cmdi_Waf_Version(BaseWAFVersion):
    """Test cmdi WAF version"""

    min_version = "1.21.0"

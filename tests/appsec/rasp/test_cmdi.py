# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc
from utils.dd_constants import Capabilities
from tests.appsec.rasp.utils import (
    validate_span_tags,
    validate_stack_traces,
    find_series,
    validate_metric_variant,
    Base_Rules_Version,
    Base_WAF_Version
)


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_UrlQuery:
    """Shell Injection through query parameters"""

    def setup_cmdi_get(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/bin/evilCommand"})

    def test_cmdi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {"address": "server.sys.exec.cmd", "value": "/bin/evilCommand",},
                "params": {"address": "server.request.query", "value": "/bin/evilCommand",},
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyUrlEncoded:
    """Shell Injection through a url-encoded body parameter"""

    def setup_cmdi_post_urlencoded(self):
        self.r = weblog.post("/rasp/cmdi", data={"command": "/bin/evilCommand"})

    def test_cmdi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {"address": "server.sys.exec.cmd", "value": "/bin/evilCommand",},
                "params": {"address": "server.request.body", "value": "/bin/evilCommand",},
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyXml:
    """Shell Injection through an xml body parameter"""

    def setup_cmdi_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><command>/bin/evilCommand</command>"
        self.r = weblog.post("/rasp/cmdi", data=data, headers={"Content-Type": "application/xml"})

    def test_cmdi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {"address": "server.sys.exec.cmd", "value": "/bin/evilCommand",},
                "params": {"address": "server.request.body", "value": "/bin/evilCommand",},
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_BodyJson:
    """Shell Injection through a json body parameter"""

    def setup_cmdi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/cmdi", json={"command": "/bin/evilCommand"})

    def test_cmdi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-932-110",
            {
                "resource": {"address": "server.sys.exec.cmd", "value": "/bin/evilCommand",},
                "params": {"address": "server.request.body", "value": "/bin/evilCommand",},
            },
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_span_tags
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Mandatory_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_cmdi_span_tags(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/bin/evilCommand"})

    def test_cmdi_span_tags(self):
        validate_span_tags(self.r, expected_metrics=["_dd.appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_span_tags
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Optional_SpanTags:
    """Validate span tag generation on exploit attempts"""

    def setup_cmdi_span_tags(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/bin/evilCommand"})

    def test_cmdi_span_tags(self):
        validate_span_tags(
            self.r, expected_metrics=["_dd.appsec.rasp.duration_ext", "_dd.appsec.rasp.rule.eval",],
        )


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_stack_trace
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_cmdi_stack_trace(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/bin/evilCommand"})

    def test_cmdi_stack_trace(self):
        assert self.r.status_code == 403
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1DDWy3frMXDTAbk-BfnZ1FdRwuPx6Pl7AWyR4zjqRFZw")
@features.rasp_command_injection
@scenarios.appsec_rasp
class Test_Cmdi_Telemetry:
    """Validate Telemetry data on exploit attempts"""

    def setup_cmdi_telemetry(self):
        self.r = weblog.get("/rasp/cmdi", params={"command": "/bin/evilCommand"})

    def test_cmdi_telemetry(self):
        assert self.r.status_code == 403

        series_eval = find_series(True, "appsec", "rasp.rule.eval")
        assert series_eval
        assert any(validate_metric_variant("rasp.rule.eval", "command_injection", "exec", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series(True, "appsec", "rasp.rule.match")
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
class Test_Cmdi_Rules_Version(Base_Rules_Version):
    """Test cmdi min rules version"""

    min_version = "1.13.5"


@features.rasp_local_file_inclusion
class Test_Cmdi_WAF_Version(Base_WAF_Version):
    """Test cmdi WAF version"""

    min_version = "1.21.0"
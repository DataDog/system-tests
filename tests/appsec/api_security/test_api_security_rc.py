# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import (
    context,
    interfaces,
    missing_feature,
    rfc,
    scenarios,
    weblog,
    features,
)
from utils.tools import logger


def get_schema(request, address):
    """get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit#heading=h.88xvn2cvs9dt")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_RC_ASM_DD_processors:
    """Test API Security - Remote config ASM_DD - processors"""

    def setup_request_method(self):
        interfaces.library.wait_for_remote_config_request()
        self.request = weblog.get("/tag_value/api_rc_processor/200?key=value")

    def test_request_method(self):
        """can provide custom req.querytest schema"""
        schema = get_schema(self.request, "req.querytest")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        assert "key" in schema[0]
        isinstance(schema[0]["key"], list)


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit#heading=h.88xvn2cvs9dt")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_RC_ASM_DD_scanners:
    """Test API Security - Remote config ASM_DD - scanners"""

    def setup_request_method(self):
        interfaces.library.wait_for_remote_config_request()
        self.request = weblog.post("/tag_value/api_rc_scanner/200", data={"mail": "systemtestmail@datadoghq.com"})

    def test_request_method(self):
        """can provide custom req.querytest schema"""
        schema = get_schema(self.request, "req.bodytest")
        EXPECTED_MAIL_SCHEMA = [8, {"category": "pii", "type": "email"}]

        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        assert "mail" in schema[0]
        isinstance(schema[0]["mail"], list)
        assert len(schema[0]["mail"]) == 2
        # value should be parsed either as a string or as a string array
        if "len" in schema[0]["mail"][1]:
            # as an array of string
            assert isinstance(schema[0]["mail"][0], list)
            element = schema[0]["mail"][0][0]
            assert len(element) == 2
            assert element[0] == 8
            assert element[1] == EXPECTED_MAIL_SCHEMA[1]
        else:
            # as a string
            assert schema[0]["mail"][0] == 8
            assert schema[0]["mail"][1] == EXPECTED_MAIL_SCHEMA[1]


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit#heading=h.88xvn2cvs9dt")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_RC_ASM_processor_overrides_and_custom_scanner:
    """Test API Security - Remote config ASM - processor_overrides"""

    request_number = 0

    def setup_request_method(self):
        interfaces.library.wait_for_remote_config_request()
        self.request = weblog.get("/tag_value/api_rc_processor_overrides/200?testcard=1234567890")

    def test_request_method(self):
        """can provide custom req.querytest schema"""
        schema = get_schema(self.request, "req.querytest")
        EXPECTED_TESTCARD_SCHEMA = [8, {"category": "testcategory", "type": "card"}]

        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        assert "testcard" in schema[0]
        isinstance(schema[0]["testcard"], list)
        assert len(schema[0]["testcard"]) == len(EXPECTED_TESTCARD_SCHEMA)
        assert schema[0]["testcard"][1] == EXPECTED_KEY_SCHEMA[1]

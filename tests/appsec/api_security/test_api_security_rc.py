# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces, rfc, scenarios, weblog, features, logger

from tests.appsec.api_security.utils import BaseAppsecApiSecurityRcTest
from utils._context._scenarios.dynamic import dynamic_scenario



def get_schema(request, address):
    """Get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        key = "_dd.appsec.s." + address
        payload = meta.get(key)
        if payload is not None:
            return payload
        else:
            logger.info(f"Schema not found in span meta for {key}")

    return None


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit#heading=h.88xvn2cvs9dt")
@dynamic_scenario(mandatory={"DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0", "DD_API_SECURITY_SAMPLE_DELAY": "0.0"})
@features.api_security_configuration
class Test_API_Security_RC_ASM_DD_processors(BaseAppsecApiSecurityRcTest):
    """Test API Security - Remote config ASM_DD - processors"""

    def setup_request_method(self):
        self.setup_scenario()
        self.request = weblog.get("/tag_value/api_rc_processor/200?key=value")

    def test_request_method(self):
        """Can provide custom req.querytest schema"""
        schema = get_schema(self.request, "req.querytest")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        assert "key" in schema[0]
        isinstance(schema[0]["key"], list)


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit#heading=h.88xvn2cvs9dt")
@dynamic_scenario(mandatory={"DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0", "DD_API_SECURITY_SAMPLE_DELAY": "0.0"})
@features.api_security_configuration
class Test_API_Security_RC_ASM_DD_scanners(BaseAppsecApiSecurityRcTest):
    """Test API Security - Remote config ASM_DD - scanners"""

    def setup_request_method(self):
        self.setup_scenario()
        self.request = weblog.post("/tag_value/api_rc_scanner/200", data={"mail": "systemtestmail@datadoghq.com"})

    def test_request_method(self):
        """Can provide custom req.querytest schema"""
        schema = get_schema(self.request, "req.bodytest")
        expected_mail_schema = [8, {"category": "pii", "type": "email"}]

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
            assert len(element) == len(expected_mail_schema)
            assert element[0] == expected_mail_schema[0]
            assert element[1] == expected_mail_schema[1]
        else:
            # as a string
            assert schema[0]["mail"][0] == expected_mail_schema[0]
            assert schema[0]["mail"][1] == expected_mail_schema[1]

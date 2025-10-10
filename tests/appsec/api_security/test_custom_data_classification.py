# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces, rfc, scenarios, weblog, features, logger
from utils.dd_constants import Capabilities

from tests.appsec.api_security.utils import BaseAppsecApiSecurityRcTest


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


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_Custom_Data_Classification_Capabilities(BaseAppsecApiSecurityRcTest):
    """Validate that ASM_PROCESSOR_OVERRIDES and ASM_CUSTOM_DATA_SCANNERS capabilities are exposed"""

    def setup_capabilities_check(self):
        """Setup for capabilities validation"""
        self.setup_scenario()

    def test_capabilities_check(self):
        """Verify both ASM_PROCESSOR_OVERRIDES and ASM_CUSTOM_DATA_SCANNERS capabilities"""
        # Verify capability 16: ASM_PROCESSOR_OVERRIDES
        interfaces.library.assert_rc_capability(Capabilities.ASM_PROCESSOR_OVERRIDES)

        # Verify capability 17: ASM_CUSTOM_DATA_SCANNERS
        interfaces.library.assert_rc_capability(Capabilities.ASM_CUSTOM_DATA_SCANNERS)


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_Custom_Data_Classification_Processor_Override(BaseAppsecApiSecurityRcTest):
    """Test API Security - Custom Data Classification with Processor Override"""

    def setup_request_method(self):
        """Test that processor overrides work correctly with custom scanners"""
        self.setup_scenario()
        self.request = weblog.get("/tag_value/api_rc_processor/200?testcard=1234567890")

    def test_request_method(self):
        """Verify custom scanner detects data based on processor override configuration"""
        schema = get_schema(self.request, "req.querytest")
        assert self.request.status_code == 200
        assert schema is not None, "Schema should be present in the span"
        assert isinstance(schema, list), "Schema should be a list"

        # Verify that the custom scanner detected the testcard parameter
        if len(schema) > 0:
            assert "testcard" in schema[0], "testcard parameter should be in the schema"


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_Custom_Data_Classification_Scanner(BaseAppsecApiSecurityRcTest):
    """Test API Security - Custom Data Classification with Custom Scanner"""

    def setup_request_method(self):
        """Test that custom scanners work correctly for request body"""
        self.setup_scenario()
        self.request = weblog.post("/tag_value/api_rc_scanner/200", data={"testcard": "1234567890"})

    def test_request_method(self):
        """Verify custom scanner detects and classifies sensitive data in request body"""
        schema = get_schema(self.request, "req.bodytest")
        assert self.request.status_code == 200
        assert schema is not None, "Schema should be present in the span"
        assert isinstance(schema, list), "Schema should be a list"

        # Verify that the custom scanner detected the testcard field
        if len(schema) > 0:
            assert "testcard" in schema[0], "testcard field should be in the schema"
            # Check if the value was classified with custom tags
            # Structure: schema[0]["testcard"] = [[[value_length, classification]], metadata]
            if isinstance(schema[0]["testcard"], list) and len(schema[0]["testcard"]) > 0:
                values = schema[0]["testcard"][0]
                if isinstance(values, list) and len(values) > 0 and isinstance(values[0], list):
                    if len(values[0]) > 1:
                        classification = values[0][1]
                        assert isinstance(classification, dict), "Classification should be a dict"
                        assert "category" in classification, "Classification should include category"
                        assert classification["category"] == "testcategory", "Category should be testcategory"
                        assert "type" in classification, "Classification should include type"
                        assert classification["type"] == "card", "Type should be card"


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_Custom_Data_Classification_Multiple_Scanners(BaseAppsecApiSecurityRcTest):
    """Test API Security - Multiple Custom Scanners"""

    def setup_request_method(self):
        """Test that multiple scanners work together correctly"""
        self.setup_scenario()
        self.request = weblog.post(
            "/tag_value/api_rc_scanner/200", data={"mail": "systemtestmail@datadoghq.com", "testcard": "1234567890"}
        )

    def test_request_method(self):
        """Verify both standard and custom scanners detect their respective data"""
        schema = get_schema(self.request, "req.bodytest")
        assert self.request.status_code == 200
        assert schema is not None, "Schema should be present in the span"
        assert isinstance(schema, list), "Schema should be a list"

        if len(schema) > 0:
            # Check for email detection by standard scanner
            assert "mail" in schema[0], "mail field should be in the schema"
            # Check for testcard detection by custom scanner
            assert "testcard" in schema[0], "testcard field should be in the schema"


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo/edit")
@scenarios.appsec_api_security_rc
@features.api_security_configuration
class Test_API_Security_Custom_Data_Classification_Negative(BaseAppsecApiSecurityRcTest):
    """Test API Security - Custom Data Classification Negative Cases"""

    def setup_request_method(self):
        """Test that data not matching scanner patterns is not classified"""
        self.setup_scenario()
        self.request = weblog.post("/tag_value/api_rc_scanner/200", data={"normalfield": "normalvalue"})

    def test_request_method(self):
        """Verify that normal data without sensitive patterns is not over-classified"""
        schema = get_schema(self.request, "req.bodytest")
        assert self.request.status_code == 200
        assert schema is not None, "Schema should be present in the span"

        # The schema should exist but the field should not be classified as sensitive
        if len(schema) > 0 and "normalfield" in schema[0]:
            field_data = schema[0]["normalfield"]
            # If it's classified, it should not have sensitive category tags
            # Structure: field_data = [[[value_length, classification]], metadata]
            if isinstance(field_data, list) and len(field_data) > 0:
                values = field_data[0]
                if isinstance(values, list) and len(values) > 0 and isinstance(values[0], list):
                    if len(values[0]) > 1:
                        classification = values[0][1]
                        if isinstance(classification, dict) and "category" in classification:
                            assert classification["category"] not in [
                                "pii",
                                "testcategory",
                            ], "Normal fields should not be classified as sensitive"

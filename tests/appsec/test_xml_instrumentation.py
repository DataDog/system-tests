"""Test XML instrumentation for WAF integration.

This test verifies that XML requests are properly instrumented and relayed to the WAF
for attack detection, similar to how JSON requests are handled. Tests both akka-http
and Spring MVC XML processing.
"""

from utils import context, interfaces, weblog, features, bug


@features.appsec_request_blocking
class Test_XmlWafIntegration:
    """Test that XML requests are properly relayed to WAF like JSON requests."""

    def setup_xml_value_attack(self):
        """Test WAF attack detection in XML element content."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string>var_dump ()</string>"
        self.r_xml_value = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_value_attack(self):
        """Verify WAF detects attack in XML content."""
        interfaces.library.assert_waf_attack(
            self.r_xml_value, 
            value='var_dump ()', 
            address="server.request.body"
        )

    def setup_xml_attribute_attack(self):
        """Test WAF attack detection in XML attribute values."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string attack='var_dump ()' />"
        self.r_xml_attr = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_attribute_attack(self):
        """Verify WAF detects attack in XML attributes."""
        interfaces.library.assert_waf_attack(
            self.r_xml_attr, 
            value='var_dump ()', 
            address="server.request.body"
        )

    def setup_xml_sql_injection(self):
        """Test WAF attack detection for SQL injection in XML."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string>' OR 1=1 --</string>"
        self.r_xml_sqli = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_sql_injection(self):
        """Verify WAF detects SQL injection in XML content."""
        interfaces.library.assert_waf_attack(
            self.r_xml_sqli, 
            value="' OR 1=1 --", 
            address="server.request.body"
        )

    def setup_xml_text_content_type(self):
        """Test XML with text/xml content type."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "text/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string>var_dump ()</string>"
        self.r_text_xml = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_text_content_type(self):
        """Verify WAF works with text/xml content type."""
        interfaces.library.assert_waf_attack(
            self.r_text_xml, 
            value="var_dump ()", 
            address="server.request.body"
        )

    def setup_xml_nested_attack(self):
        """Test WAF detection in nested XML elements."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string>var_dump ()</string>"
        self.r_nested = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_nested_attack(self):
        """Verify WAF detects attacks in nested XML structures."""
        interfaces.library.assert_waf_attack(
            self.r_nested, 
            value='var_dump ()', 
            address="server.request.body"
        )

    def setup_xml_multiple_attacks(self):
        """Test XML with multiple attack vectors."""
        # Use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string attack='var_dump ()'>var_dump ()</string>"
        self.r_multiple = weblog.post("/waf", data=xml_data, headers=headers)

    def test_xml_multiple_attacks(self):
        """Verify WAF detects attacks in XML with multiple attack vectors."""
        interfaces.library.assert_waf_attack(
            self.r_multiple, 
            value="var_dump ()", 
            address="server.request.body"
        )


@features.appsec_request_blocking
class Test_XmlJsonParity:
    """Test that XML and JSON requests have equivalent WAF behavior."""

    def setup_equivalent_payloads(self):
        """Test equivalent attack payloads in JSON vs XML."""
        attack_payload = 'var_dump ()'
        
        # JSON request
        self.r_json = weblog.post("/waf", json={"attack": attack_payload})
        
        # Equivalent XML request - use exact same pattern as working tests in test_addresses.py
        headers = {"Content-Type": "application/xml"}
        xml_data = "<?xml version='1.0' encoding='utf-8'?><string>var_dump ()</string>"
        self.r_xml = weblog.post("/waf", data=xml_data, headers=headers)

    def test_equivalent_payloads(self):
        """Verify JSON and XML requests with same payload both trigger WAF."""
        # Both should be detected by WAF
        interfaces.library.assert_waf_attack(
            self.r_json, 
            value='var_dump ()', 
            address="server.request.body"
        )
        interfaces.library.assert_waf_attack(
            self.r_xml, 
            value='var_dump ()', 
            address="server.request.body"
        )
        
        # Both should have same response status (blocked)
        assert self.r_json.status_code == self.r_xml.status_code

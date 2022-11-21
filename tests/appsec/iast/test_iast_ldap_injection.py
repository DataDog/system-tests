# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?", cpp="?",
)
class TestIastLDAPInjection(BaseTestCase):
    """Verify IAST LDAP Injection"""

    EXPECTATIONS = {"java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.LDAPExamples"}}

    def __expected_location(self, vulnerability):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    def test_insecure(self):
        """Insecure LDAP queries are reported as insecure"""
        r = self.weblog_post("/iast/ldapi/test_insecure", data={"username": "ssam", "password": "sammy"})
        interfaces.library.expect_iast_vulnerabilities(
            r,
            vulnerability_count=1,
            vulnerability_type="LDAP_INJECTION",
            location_path=self.__expected_location("LDAP_INJECTION"),
        )

    def test_secure(self):
        """Secure LDAP queries are not reported as insecure"""
        r = self.weblog_post("/iast/ldapi/test_secure", data={"username": "ssam", "password": "sammy"})
        interfaces.library.expect_no_vulnerabilities(r)

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import weblog, interfaces, context, coverage, released, missing_feature

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(java={"spring-boot": "1.7.0", "*": "?"})
class TestIastLDAPInjection:
    """Verify IAST LDAP Injection"""

    EXPECTATIONS = {"java": {"LOCATION": "com.datadoghq.system_tests.iast.utils.LDAPExamples"}}

    def __expected_location(self, vulnerability):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    def setup_insecure(self):
        self.r_insecure = weblog.post("/iast/ldapi/test_insecure", data={"username": "ssam", "password": "sammy"})

    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_insecure(self):
        """Insecure LDAP queries are reported as insecure"""
        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure,
            vulnerability_count=1,
            vulnerability_type="LDAP_INJECTION",
            location_path=self.__expected_location("LDAP_INJECTION"),
        )

    def setup_secure(self):
        self.r_secure = weblog.post("/iast/ldapi/test_secure", data={"username": "ssam", "password": "sammy"})

    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_secure(self):
        """Secure LDAP queries are not reported as insecure"""
        interfaces.library.expect_no_vulnerabilities(self.r_secure)

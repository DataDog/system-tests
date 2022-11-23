# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released, bug

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?",
    golang="?",
    java={"spring-boot": "0.108.0", "spring-boot-jetty": "0.108.0", "spring-boot-openliberty": "0.108.0", "*": "?"},
    nodejs={"express4": "3.6.0", "*": "?"},
    php_appsec="?",
    python="1.7.0",
    ruby="?",
    cpp="?",
)
class TestIastWeakCipher(BaseTestCase):
    """Verify IAST WEAK CIPHER feature"""

    EXPECTATIONS = {"nodejs": {"WEAK_CIPHER_ALGORITHM": "des-ede-cbc"}, "java": {"WEAK_CIPHER_ALGORITHM": "Blowfish"}}

    def __expected_weak_cipher_algorithm(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("WEAK_CIPHER_ALGORITHM") if expected else None

    @missing_feature(context.library < "nodejs@3.3.1", reason="Need to be implement global vulnerability deduplication")
    def test_insecure_cipher(self):
        """Test weak cipher algorithm is reported as insecure"""
        r = self.weblog_get("/iast/insecure_cipher/test_insecure_algorithm")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_type="WEAK_CIPHER", evidence=self.__expected_weak_cipher_algorithm()
        )

    def test_secure_cipher(self):
        """Test strong cipher algorithm is not reported as insecure"""
        r = self.weblog_get("/iast/insecure_cipher/test_secure_algorithm")

        interfaces.library.expect_no_vulnerabilities(r)

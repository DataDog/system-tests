# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest

from utils import weblog, interfaces, context, missing_feature, coverage, released


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="1.7.0", ruby="?")
@released(nodejs={"express4": "3.6.0", "*": "?"})
@released(
    java={"spring-boot": "0.108.0", "spring-boot-jetty": "0.108.0", "spring-boot-openliberty": "0.108.0", "resteasy-netty3": "1.11.0", "*": "?"},
)
class TestIastWeakCipher:
    """Verify IAST WEAK CIPHER feature"""

    EXPECTATIONS = {"nodejs": {"WEAK_CIPHER_ALGORITHM": "des-ede-cbc"}, "java": {"WEAK_CIPHER_ALGORITHM": "Blowfish"}}

    def __expected_weak_cipher_algorithm(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("WEAK_CIPHER_ALGORITHM") if expected else None

    def setup_insecure_cipher(self):
        self.r_insecure_cipher = weblog.get("/iast/insecure_cipher/test_insecure_algorithm")

    @missing_feature(context.library < "nodejs@3.3.1", reason="Need to be implement global vulnerability deduplication")
    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_insecure_cipher(self):
        """Test weak cipher algorithm is reported as insecure"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_cipher, vulnerability_type="WEAK_CIPHER", evidence=self.__expected_weak_cipher_algorithm()
        )

    def setup_secure_cipher(self):
        self.r_secure_cipher = weblog.get("/iast/insecure_cipher/test_secure_algorithm")

    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_secure_cipher(self):
        """Test strong cipher algorithm is not reported as insecure"""

        interfaces.library.expect_no_vulnerabilities(self.r_secure_cipher)

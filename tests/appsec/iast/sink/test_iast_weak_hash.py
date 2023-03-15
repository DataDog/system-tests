# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from utils import weblog, interfaces, context, missing_feature, coverage, released, bug


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="1.6.0", ruby="?")
@released(nodejs={"express4": "3.11.0", "*": "?"})
@released(
    java={
        "spring-boot": "0.108.0",
        "spring-boot-jetty": "0.108.0",
        "spring-boot-openliberty": "0.108.0",
        "resteasy-netty3": "1.11.0",
        "*": "?",
    }
)
class TestIastWeakHash:
    """Verify IAST WEAK HASH detection feature"""

    @property
    def expected_location(self):
        if context.library.library == "java":
            return "com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples"

        if context.library.library == "nodejs":
            return "iast.js"

        if context.library.library == "python":
            if context.weblog_variant == "uwsgi-poc":
                return "/app/./iast.py"

            return "/app/iast.py"

        return None

    def setup_insecure_hash_remove_duplicates(self):
        self.r_insecure_hash_remove_duplicates = weblog.get("/iast/insecure_hashing/deduplicate")

    @missing_feature(context.weblog_variant == "spring-boot-openliberty")
    @missing_feature(library="python", reason="Need to be implement duplicates vulnerability hashes")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request,
        we will report only one vulnerability"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_hash_remove_duplicates,
            vulnerability_count=1,
            vulnerability_type="WEAK_HASH",
            location_path=self.expected_location,
        )

    def setup_insecure_hash_multiple(self):
        self.r_insecure_hash_multiple = weblog.get("/iast/insecure_hashing/multiple_hash")

    @bug(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_hash_multiple,
            vulnerability_count=2,
            vulnerability_type="WEAK_HASH",
            location_path=self.expected_location,
        )

    def setup_secure_hash(self):
        self.r_secure_hash = weblog.get("/iast/insecure_hashing/test_secure_algorithm")

    def test_secure_hash(self):
        """Strong hash algorithm is not reported as insecure"""
        interfaces.library.expect_no_vulnerabilities(self.r_secure_hash)

    def setup_insecure_md5_hash(self):
        self.r_insecure_md5_hash = weblog.get("/iast/insecure_hashing/test_md5_algorithm")

    @bug(context.weblog_variant == "spring-boot-openliberty")
    def test_insecure_md5_hash(self):
        """Test md5 weak hash algorithm reported as insecure"""

        interfaces.library.expect_iast_vulnerabilities(
            self.r_insecure_md5_hash, vulnerability_type="WEAK_HASH", evidence="md5"
        )

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released

# Weblog are ok for nodejs/express4 and java/spring-boot
# @missing_feature(reason="Need to be implement in iast library")
# @coverage.not_implemented  # TODO : the test logic must be written once we hve the RFC
@missing_feature(library="golang")
@missing_feature(library="cpp")
@missing_feature(library="python")
@missing_feature(library="php")
@missing_feature(library="dotnet")
@missing_feature(library="ruby")
class Test_Iast(BaseTestCase):
    """Verify IAST features"""

    @missing_feature(library="java", reason="Need to be implement deduplicate vulnerability hashes")
    def test_insecure_hash_remove_duplicates(self):
        """If one line is vulnerable and it is executed multiple times (for instance in a loop) in a request, we will report only one vulnerability"""
        r = self.weblog_get("/iast/insecure_hashing/deduplicate")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnarability_count=1, type="WEAK_HASH", location_path=self.__get_insecure_hash_source_path()
        )

    def test_insecure_hash_multiple(self):
        """If a endpoint has multiple vulnerabilities (in diferent lines) we will report all of them"""
        r = self.weblog_get("/iast/insecure_hashing/multiple_hash")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnarability_count=2, type="WEAK_HASH", location_path=self.__get_insecure_hash_source_path()
        )

    def test_secure_hash(self):
        """Strong hash algorithm is not reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_algorithm?name=sha256")

        interfaces.library.expect_iast_vulnerabilities(
            r, vulnarability_count=0, type="WEAK_HASH", location_path=self.__get_insecure_hash_source_path()
        )

    def test_insecure_md5_hash(self):
        """Test md5 weak hash algorithm reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_algorithm?name=md5")

        interfaces.library.expect_iast_vulnerabilities(r, type="WEAK_HASH", evidence="md5")

    @missing_feature(library="java", reason="Need to be implement sha1 hash detection")
    def test_insecure_sha1_hash(self):
        """Test sha1 weak hash algorithm reported as insecure"""
        r = self.weblog_get("/iast/insecure_hashing/test_algorithm?name=sha1")

        interfaces.library.expect_iast_vulnerabilities(
            r, type="WEAK_HASH", evidence="sha1", location_path=self.__get_insecure_hash_source_path()
        )

    def __get_insecure_hash_source_path(self):
        exepcted_location = ""
        if context.library == "nodejs":
            exepcted_location = "/usr/app/app.js"
        elif context.library == "java":
            exepcted_location = "com.datadoghq.system_tests.springboot.iast.utils.CryptoExamples"
        return exepcted_location

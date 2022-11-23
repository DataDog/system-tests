# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?", cpp="?",
)
class TestIastPathTraversal(BaseTestCase):
    """Verify IAST features"""

    EXPECTATIONS = {
        "java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.PathExamples"},
        "nodejs": {"LOCATION": "/usr/app/iast.js"},
    }

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    @missing_feature(reason="Need to implement Path traversal detection")
    def test_insecure_path_traversal(self):
        """Insecure path traversals are reported as insecure"""
        r = self.weblog_post("/iast/path_traversal/test_insecure", data={"path": "/var/log"})
        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_count=1, vulnerability_type="PATH_TRAVERSAL", location_path=self.__expected_location(),
        )

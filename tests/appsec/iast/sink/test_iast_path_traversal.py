# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from utils import weblog, interfaces, context, coverage, released


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "1.1.0",
        "spring-boot-jetty": "1.1.0",
        "spring-boot-openliberty": "1.1.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "*": "?",
    }
)
class TestIastPathTraversal:
    """Verify IAST features"""

    EXPECTATIONS = {
        "java": {"LOCATION": "com.datadoghq.system_tests.iast.utils.PathExamples"},
        "nodejs": {"LOCATION": "iast.js"},
    }

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    def setup_insecure_path_traversal(self):
        self.r = weblog.post("/iast/path_traversal/test_insecure", data={"path": "/var/log"})

    def test_insecure_path_traversal(self):
        """Insecure path traversals are reported as insecure"""
        interfaces.library.expect_iast_vulnerabilities(
            self.r,
            vulnerability_count=1,
            vulnerability_type="PATH_TRAVERSAL",
            location_path=self.__expected_location(),
        )

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, coverage, released

# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(
    dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?", cpp="?",
)
class TestIastCommandInjection(BaseTestCase):
    """Verify IAST features"""

    EXPECTATIONS = {"java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.CmdExamples"}}

    def __expected_location(self):
        expected = self.EXPECTATIONS.get(context.library.library)
        return expected.get("LOCATION") if expected else None

    @missing_feature(reason="Need to implement Command injection detection")
    def test_insecure_command_injection(self):
        """Insecure command executions are reported as insecure"""
        r = self.weblog_post("/iast/cmdi/test_insecure", data={"cmd": "ls"})
        interfaces.library.expect_iast_vulnerabilities(
            r, vulnerability_count=1, vulnerability_type="COMMAND_INJECTION", location_path=self.__expected_location(),
        )

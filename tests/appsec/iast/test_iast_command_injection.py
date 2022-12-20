# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import weblog, interfaces, context, coverage, released, flaky


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


# Weblog are ok for nodejs/express4 and java/spring-boot
@coverage.basic
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@released(java={"spring-boot": "1.1.0", "spring-boot-jetty": "1.1.0", "spring-boot-openliberty": "1.1.0", "*": "?"})
@flaky(library="java", reason="APPSEC-7111")
class TestIastCommandInjection:
    """Verify IAST features"""

    @property
    def expected_location(self):

        EXPECTATIONS = {
            "java": {"LOCATION": "com.datadoghq.system_tests.springboot.iast.utils.CmdExamples"},
            "nodejs": {"LOCATION": "/usr/app/iast.js"},
        }

        expected = EXPECTATIONS.get(context.library.library, {})
        return expected.get("LOCATION", None)

    def setup_insecure_command_injection(self):
        self.r = weblog.post("/iast/cmdi/test_insecure", data={"cmd": "ls"})

    def test_insecure_command_injection(self):
        """Insecure command executions are reported as insecure"""
        interfaces.library.expect_iast_vulnerabilities(
            self.r, vulnerability_count=1, vulnerability_type="COMMAND_INJECTION", location_path=self.expected_location,
        )

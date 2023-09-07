# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, released
from .._test_iast_fixtures import SinkFixture


@coverage.basic
@released(php_appsec="?", python="?")
@released(java={"ratpack": "?", "spring-boot-3-native": "?", "*": "1.18.0"})
class TestXPathInjection:
    """Test xpath injection detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="XPATH_INJECTION",
        http_method="POST",
        insecure_endpoint="/iast/xpathi/test_insecure",
        secure_endpoint="/iast/xpathi/test_secure",
        data={"expression": "expression"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.XPathExamples"},
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    def test_secure(self):
        self.sink_fixture.test_secure()

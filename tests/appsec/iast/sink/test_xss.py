# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, released
from .._test_iast_fixtures import SinkFixture


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?", nodejs="?")
@released(java={"*": "?", "spring-boot": "1.19.0"})
class TestXSSInjection:
    """Test xss detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="XSS",
        http_method="POST",
        insecure_endpoint="/iast/xss/test_insecure",
        secure_endpoint="/iast/xss/test_secure",
        data={"param": "param"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.XSSExamples"},
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    def test_secure(self):
        self.sink_fixture.test_secure()

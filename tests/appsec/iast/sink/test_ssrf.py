# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released, missing_feature
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", java="?", golang="?", php_appsec="?", python="?", ruby="?", nodejs="?")
class TestSSRF:
    """Test command injection detection."""

    sink_fixture = SinkFixture(
        vulnerability_type="SSRF",
        http_method="POST",
        insecure_endpoint="/iast/ssrf/test_insecure",
        secure_endpoint="/iast/ssrf/test_secure",
        data={"url": "https://www.datadoghq.com"},
        location_map={"java": "com.datadoghq.system_tests.iast.utils.SsrfExamples", "nodejs": "iast.js",},
    )

    def setup_insecure(self):
        self.sink_fixture.setup_insecure()

    def test_insecure(self):
        self.sink_fixture.test_insecure()

    def setup_secure(self):
        self.sink_fixture.setup_secure()

    @missing_feature(reason="Endpoint not implemented")
    def test_secure(self):
        self.sink_fixture.test_secure()

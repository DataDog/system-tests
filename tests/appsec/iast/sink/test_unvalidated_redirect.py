# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released
from ..iast_fixtures import SinkFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


def _expected_location():
    if context.library.library == "java":
        if context.weblog_variant.startswith("spring-boot"):
            return "com.datadoghq.system_tests.springboot.AppSecIast"
        if context.weblog_variant == "resteasy-netty3":
            return "com.datadoghq.resteasy.IastSinkResource"
        if context.weblog_variant == "jersey-grizzly2":
            return "com.datadoghq.jersey.IastSinkResource"
    if context.library.library == "nodejs":
        return "iast/index.js"


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", ruby="?", python="?", nodejs="?")
@released(
    java={
        "spring-boot": "?",
        "spring-boot-jetty": "?",
        "spring-boot-openliberty": "?",
        "spring-boot-wildfly": "?",
        "spring-boot-undertow": "?",
        "resteasy-netty3": "?",
        "jersey-grizzly2": "?",
        "*": "?",
    }
)
class TestUnvalidatedRedirect:
    """Verify Unvalidated redirect detection."""

    sink_fixture_header = SinkFixture(
        vulnerability_type="UNVALIDATED_REDIRECT",
        http_method="POST",
        insecure_endpoint="/iast/unvalidated_redirect/test_insecure_header",
        secure_endpoint="/iast/unvalidated_redirect/test_secure_header",
        data={"location": "http://dummy.location.com"},
        location_map=_expected_location,
    )
    sink_fixture_redirect = SinkFixture(
        vulnerability_type="UNVALIDATED_REDIRECT",
        http_method="POST",
        insecure_endpoint="/iast/unvalidated_redirect/test_insecure_redirect",
        secure_endpoint="/iast/unvalidated_redirect/test_secure_redirect",
        data={"location": "http://dummy.location.com"},
        location_map=_expected_location,
    )

    def setup_insecure_header(self):
        self.sink_fixture_header.setup_insecure()

    def test_insecure_header(self):
        self.sink_fixture_header.test_insecure()

    def setup_secure_header(self):
        self.sink_fixture_header.setup_secure()

    def test_secure_header(self):
        self.sink_fixture_header.test_secure()

    def setup_insecure_redirect(self):
        self.sink_fixture_redirect.setup_insecure()

    def test_insecure_redirect(self):
        self.sink_fixture_redirect.test_insecure()

    def setup_secure_redirect(self):
        self.sink_fixture_redirect.setup_secure()

    def test_secure_redirect(self):
        self.sink_fixture_redirect.test_secure()

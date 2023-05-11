# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest
from utils import context, coverage, released, bug
from ..iast_fixtures import SourceFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "1.5.0",
        "spring-boot-jetty": "1.5.0",
        "spring-boot-openliberty": "1.5.0",
        "spring-boot-wildfly": "1.5.0",
        "spring-boot-undertow": "1.5.0",
        "resteasy-netty3": "1.11.0",
        "jersey-grizzly2": "1.11.0",
        "vertx3": "1.12.0",
        "*": "?",
    }
)
@released(nodejs="?")
class TestHeaderValue:
    """Verify that request headers are tainted"""

    source_fixture = SourceFixture(
        http_method="GET",
        endpoint="/iast/source/header/test",
        request_kwargs={"headers": {"random-key": "header-source"}},
        source_type="http.request.header",
        source_name="random-key",
        source_value="header-source",
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_source_reported(self):
        self.source_fixture.test()

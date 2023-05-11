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
class TestParameterValue:
    """Verify that request parameters are tainted"""

    source_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/parameter/test",
        request_kwargs={"data": {"source": "parameter"}},
        source_type="http.request.parameter",
        source_name="source",
        source_value="parameter",
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_source_reported(self):
        self.source_fixture.test()

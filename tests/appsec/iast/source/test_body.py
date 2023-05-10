# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import context, coverage, released
from ..iast_fixtures import SourceFixture

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(
    java={
        "spring-boot": "1.7.0",
        "spring-boot-jetty": "1.7.0",
        "spring-boot-openliberty": "1.7.0",
        "spring-boot-wildfly": "1.7.0",
        "spring-boot-undertow": "1.7.0",
        "vertx3": "1.12.0",
        "*": "?",
    }
)
@released(nodejs="?")
class TestBody:
    """Verify that request json body is tainted"""

    source_fixture = SourceFixture(
        http_method="POST",
        endpoint="/iast/source/body/test",
        request_kwargs={"json": {"name": "nameTest", "value": "valueTest"}},
        source_type="http.request.body",
        source_name=None,
        source_value=None,
    )

    def setup_source_reported(self):
        self.source_fixture.setup()

    def test_source_reported(self):
        self.source_fixture.test()

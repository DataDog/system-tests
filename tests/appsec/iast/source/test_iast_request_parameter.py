# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
import re
from utils import weblog, interfaces, context, coverage, released, missing_feature, bug


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
@released(nodejs={"express4": "3.19.0", "*": "?"})
class TestRequestParameter:
    """Verify that request parameters are tainted"""

    def setup_parameter_post(self):
        self.r = weblog.post("/iast/source/parameter/test", data={"source": "parameter"})

    @bug(context.weblog_variant == "jersey-grizzly2", reason="name field of source not set")
    def test_parameter_post(self):
        expectedOrigin = "http.request.parameter"
        if context.library.library == "nodejs":
            expectedOrigin = "http.request.body"

        interfaces.library.expect_iast_sources(
            self.r, source_count=1, name="source", origin=expectedOrigin, value="parameter"
        )

    def setup_parameter_get(self):
        self.r = weblog.get("/iast/source/parameter/test", params={"source": "parameter"})

    @missing_feature(context.library.library == "java", reason="Pending to add GET test")
    def test_parameter_get(self):
        interfaces.library.expect_iast_sources(
            self.r, source_count=1, name="source", origin="http.request.parameter", value="parameter"
        )

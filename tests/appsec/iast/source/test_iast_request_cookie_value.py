# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
import re
from utils import weblog, interfaces, context, coverage, released, missing_feature


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(java={"spring-boot": "1.5.0", "spring-boot-jetty": "1.5.0", "spring-boot-openliberty": "1.5.0", "*": "?"})
@released(nodejs="?")
class TestRequestCookieValue:
    """Verify that request cookies are tainted"""

    def setup_cookie_value(self):
        self.r = weblog.get("/iast/source/cookievalue/test", cookies={"cookie-source-name": "cookie-source-value"})

    def test_cookie_value(self):
        interfaces.library.expect_iast_sources(
            self.r,
            source_count=1,
            name="cookie-source-name",
            origin="http.request.cookie.value",
            value="cookie-source-value",
        )

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
class TestRequestHeader:
    """Verify that request headers are tainted"""

    def test_header(self):
        weblog.get("/iast/source/header/test", headers={"random-key": "header-source"})
        interfaces.library_stdout.wait()
        test = re.escape(
            'tainted={"value":"header-source","ranges":[{"source":{"origin":"http.request.header","name":"random-key","value":"header-source"},"start":0,"length":13}]}'
        )
        interfaces.library_stdout.assert_presence(test, level="DEBUG")

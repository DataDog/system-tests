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
@released(java={"spring-boot": "1.7.0", "*": "?"})
@released(nodejs="?")
class TestRequestBody:
    """Verify that request json body is tainted"""

    def setup_body(self):
        self.r = weblog.post("/iast/source/body/test", json={"name": "nameTest", "value": "valueTest"})

    def test_body(self):
        interfaces.library.expect_iast_sources(
            self.r, source_count=1, origin="http.request.body",
        )

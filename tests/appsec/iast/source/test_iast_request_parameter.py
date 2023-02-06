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
class TestRequestParameter:
    """Verify that request parameters are tainted"""

    def test_parameter(self):
        weblog.post("/iast/source/parameter/test", data={"source": "parameter", "value": "parameterValue"})
        interfaces.library_stdout.wait()
        testSource = re.escape(
            'tainted={"value":"parameter","ranges":[{"source":{"origin":"http.request.parameter","name":"source","value":"parameter"},"start":0,"length":9}]}'
        )
        interfaces.library_stdout.assert_presence(testSource, level="DEBUG")
        testValue = re.escape(
            'tainted={"value":"parameterValue","ranges":[{"source":{"origin":"http.request.parameter","name":"value","value":"parameterValue"},"start":0,"length":14}]}'
        )
        interfaces.library_stdout.assert_presence(testValue, level="DEBUG")

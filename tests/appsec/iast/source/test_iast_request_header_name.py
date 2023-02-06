# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

# [dd.trace 2023-02-03 08:23:38:472 +0000] [http-nio-7777-exec-2] DEBUG com.datadog.iast.taint.TaintedObjects - taint 198f3241-5ae9-42de-8273-25636ba1a31c: tainted={"value":"parameter","ranges":[{"source":{"origin":"http.request.parameter","name":"username","value":"parameter"},"start":0,"length":9}]}
# [dd.trace 2023-02-03 08:23:38:472 +0000] [http-nio-7777-exec-2] DEBUG com.datadog.iast.taint.TaintedObjects - taint 198f3241-5ae9-42de-8273-25636ba1a31c: tainted={"value":"insecure","ranges":[{"source":{"origin":"http.request.parameter","name":"password","value":"insecure"},"start":0,"length":8}]}


import pytest
import re
from utils import weblog, interfaces, context, coverage, released, missing_feature


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.basic
@released(dotnet="?", golang="?", php_appsec="?", python="?", ruby="?")
@released(java={"spring-boot": "1.5.0", "spring-boot-jetty": "1.5.0", "spring-boot-openliberty": "1.5.0", "*": "?"})
@released(nodejs="?")
class TestRequestHeaderName:
    """Verify that request headers name are tainted"""

    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_headername(self):
        weblog.get("/iast/source/headername/test", headers={"random-key": "header-name"})
        interfaces.library_stdout.wait()
        test = re.escape(
            'tainted={"value":"random-key","ranges":[{"source":{"origin":"http.request.header.name","name":"random-key"},"start":0,"length":10}]}'
        )
        interfaces.library_stdout.assert_presence(test, level="DEBUG")

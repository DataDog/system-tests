# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature


@missing_feature(context.library != "java", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="jersey-grizzly2", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="resteasy-netty3", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="ratpack", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="vertx3", reason="Need to build endpoint on weblog")
@missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class Test_Ognl:
    """Verify the /trace/ognl endpoint is setup"""

    def setup_main(self):
        self.r = weblog.get("/trace/ognl")

    def test_main(self):
        assert self.r.status_code == 200
        interfaces.library.assert_trace_exists(self.r)

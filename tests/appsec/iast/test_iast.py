# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature


@missing_feature(context.library == "python", reason="Need to be implement in iast library")
@missing_feature(context.library == "ruby", reason="Need to be implement in iast library")
@missing_feature(context.library == "golang", reason="Need to be implement in iast library")
@missing_feature(context.library == "php", reason="Need to be implement in iast library")
@missing_feature(context.library == "dotnet", reason="Need to be implement in iast library")
@missing_feature(context.library == "cpp", reason="Need to be implement in iast library")
@missing_feature(weblog_variant="express4-typescript", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="jersey-grizzly2", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="resteasy-netty3", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="ratpack", reason="Need to build endpoint on weblog")
@missing_feature(weblog_variant="vertx3", reason="Need to build endpoint on weblog")
class Test_Iast(BaseTestCase):
    """ Verify the IAST features """

    def test_insecure_hashing_all(self):
        """ Test insecure hashing all algorithms"""
        r = self.weblog_get("/iast/insecure_hashing")
        interfaces.library.assert_trace_exists(r)

    def test_insecure_hashing_sha1(self):
        """ Test insecure hashing sha1 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=sha1")
        interfaces.library.assert_trace_exists(r)

    def test_insecure_hashing_md5(self):
        """ Test insecure hashing md5 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=md5")
        interfaces.library.assert_trace_exists(r)

    def test_insecure_hashing_md4(self):
        """ Test insecure hashing md4 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=md4")
        interfaces.library.assert_trace_exists(r)

    def test_insecure_hashing_md2(self):
        """ Test insecure hashing md2 algorithm"""
        r = self.weblog_get("/iast/insecure_hashing?algorithmName=md2")
        interfaces.library.assert_trace_exists(r)

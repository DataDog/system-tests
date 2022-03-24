# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant


@irrelevant(context.library != "golang", reason="Need to build endpoint on weblog")
@irrelevant(context.library != "nodejs", reason="Need to build endpoint on weblog")
@irrelevant(context.library != "ruby", reason="Need to build endpoint on weblog")
@irrelevant(context.library != "python", reason="Need to build endpoint on weblog")
@irrelevant(context.library != "java", reason="Need to build endpoint on weblog")
class Test_Misc(BaseTestCase):
    """ Check that traces are reported for some services """

    def test_main(self):
        r = self.weblog_get("/trace/httpclient")
        interfaces.library.assert_trace_exists(r, span_type="http")

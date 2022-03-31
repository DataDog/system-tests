# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant


@irrelevant(context.library != "java", reason="Need to build endpoint on weblog")
class Test_Sqli(BaseTestCase):
    """ Verify the /rasp/sqli endpoint is setup """

    def test_main(self):
        r = self.weblog_get("/rasp/sqli")
        interfaces.library.assert_trace_exists(r)

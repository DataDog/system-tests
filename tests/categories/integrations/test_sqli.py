# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context


class Test_Sqli(BaseTestCase):
    """ Check that traces are reported for sqli """

    def test_main(self):
        r = self.weblog_get("/rasp/sqli")
        interfaces.library.assert_trace_exists(r)

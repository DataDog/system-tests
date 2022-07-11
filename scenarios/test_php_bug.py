# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
from utils import BaseTestCase, interfaces


class Test_Basic(BaseTestCase):
    """ Basic testing of profiling """

    def test_basic(self):
        for _ in range(1000):
            r = self.weblog_get("/waf/", params={"value": "merge using("})
            interfaces.library.assert_waf_attack(r, pattern="merge using(")

    def test_schemas(self):
        interfaces.library.assert_schemas()

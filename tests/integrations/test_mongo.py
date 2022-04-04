# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant

# FORCE FAILURE FOR VERIFICATION, TODO REMOVE
# @irrelevant(reason="Endpoint is unimplemented on weblog")
class Test_Mongo(BaseTestCase):
    """ Verify that a mongodb span is created """

    def test_main(self):
        r = self.weblog_get("/trace/mongo")
        interfaces.library.assert_trace_exists(r, span_type="mongodb")

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, bug, missing_feature, scenario


@bug(library="java", reason="Endpoint is probably improperly implemented on weblog")
@missing_feature(condition=context.library != "java", reason="Endpoint is not implemented on weblog")
@scenario("INTEGRATIONS")
class Test_Sql(BaseTestCase):
    """ Verify that a sql span is created """

    def test_main(self):
        r = self.weblog_get("/trace/sql")
        interfaces.library.assert_trace_exists(r, span_type="sql")

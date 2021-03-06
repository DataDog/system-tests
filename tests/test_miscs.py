# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import BaseTestCase, interfaces, missing_feature, released, irrelevant


@released(golang="?", java="0.97.0", nodejs="?", php="0.74.0", python="0.59.1", ruby="?")
@irrelevant(library="cpp")
class Test_Basic(BaseTestCase):
    """ Make sure the spans endpoint is successful """

    def test_spans_generation(self):
        r = self.weblog_get("/spans")
        interfaces.library.assert_trace_exists(r, span_type="web")

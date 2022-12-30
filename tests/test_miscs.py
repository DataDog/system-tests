# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, released, irrelevant, bug


@released(golang="1.43.0", java="0.97.0", nodejs="3.1.0", php="0.74.0", python="0.59.1", ruby="?")
@irrelevant(library="cpp")
class Test_Basic:
    """ Make sure the spans endpoint is successful """

    def setup_spans_generation(self):
        self.r = weblog.get("/spans")

    def test_spans_generation(self):
        interfaces.library.assert_trace_exists(self.r, span_type="web")

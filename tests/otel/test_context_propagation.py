# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import json
from utils import weblog, scenarios, features, incomplete_test_app


@features.otel_propagators_api
@scenarios.apm_tracing_e2e_otel
class Test_Otel_Context_Propagation_Default_Propagator_Api:
    def setup_propagation_extract(self):
        extract_headers = {
            "traceparent": "00-11111111111111110000000000000002-000000000000000a-01",
            "tracestate": "dd=s:2;p:000000000000000a,foo=1",
            "baggage": "foo=1",
        }
        self.r = weblog.get("/otel_drop_in_default_propagator_extract", headers=extract_headers)

    @incomplete_test_app(library="nodejs", reason="Node.js extract endpoint doesn't seem to be working.")
    @incomplete_test_app(library="ruby", reason="Ruby extract seems to fail even though it should be supported")
    def test_propagation_extract(self):
        content = json.loads(self.r.text)

        assert content["trace_id"] == 2
        assert content["span_id"] == 10
        assert content["tracestate"]
        assert not content["tracestate"].isspace()
        # assert content["baggage"] and not content["baggage"].isspace()

    def setup_propagation_inject(self):
        self.r = weblog.get("/otel_drop_in_default_propagator_inject")

    @incomplete_test_app(library="nodejs", reason="Node.js inject endpoint doesn't seem to be working.")
    def test_propagation_inject(self):
        content = json.loads(self.r.text)

        assert content["traceparent"]
        assert not content["traceparent"].isspace()
        # assert content["baggage"] and not content["baggage"].isspace()

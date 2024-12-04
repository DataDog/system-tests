# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import json
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY, ORIGIN
from utils import weblog, interfaces, scenarios, features


@scenarios.trace_propagation_style_w3c
@features.w3c_headers_injection_and_extraction
class Test_DistributedHttp:
    """ Verify behavior of http clients and distributed traces """

    def setup_main(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_main(self):

        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]


@scenarios.default
@features.datadog_headers_propagation
class Test_Synthetics_APM_Datadog:
    def setup_synthetics(self):
        self.r = weblog.get(
            "/",
            headers={
                "x-datadog-trace-id": "1234567890",
                "x-datadog-parent-id": "0",
                "x-datadog-sampling-priority": "1",
                "x-datadog-origin": "synthetics",
            },
        )

    def test_synthetics(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        span = spans[0]
        assert span.get("traceID") == "1234567890"
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None
        assert span.get("meta")[ORIGIN] == "synthetics"
        assert span.get("metrics")[SAMPLING_PRIORITY_KEY] == 1

    def setup_synthetics_browser(self):
        self.r = weblog.get(
            "/",
            headers={
                "x-datadog-trace-id": "1234567891",
                "x-datadog-parent-id": "0",
                "x-datadog-sampling-priority": "1",
                "x-datadog-origin": "synthetics-browser",
            },
        )

    def test_synthetics_browser(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        span = spans[0]
        assert span.get("traceID") == "1234567891"
        assert "parentID" not in span or span.get("parentID") == 0 or span.get("parentID") is None
        assert span.get("meta")[ORIGIN] == "synthetics-browser"
        assert span.get("metrics")[SAMPLING_PRIORITY_KEY] == 1

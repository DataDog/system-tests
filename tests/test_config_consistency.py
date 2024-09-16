# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_HttpServerErrorStatuses_Default:
    """ Verify behavior of http clients and distributed traces """

    def setup_status_code_400(self):
        self.r = weblog.get("/status?code=400")

    def test_status_code_400(self):

        assert self.r.status_code == 400

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "400"
        assert "error" not in spans[0] or spans[0]["error"] == 0

    def setup_status_code_500(self):
        self.r = weblog.get("/status?code=500")

    def test_status_code_500(self):
        assert self.r.status_code == 500

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["meta"]["http.status_code"] == "500"
        assert spans[0]["error"] == 1


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_HttpServerErrorStatuses_FeatureFlagCustom:
    """ Verify behavior of http clients and distributed traces """

    def setup_status_code_200(self):
        self.r = weblog.get("/status?code=200")

    def test_status_code_200(self):
        assert self.r.status_code == 200

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "200"
        assert spans[0]["error"] == 1

    def setup_status_code_202(self):
        self.r = weblog.get("/status?code=202")

    def test_status_code_202(self):
        assert self.r.status_code == 202

        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        assert spans[0]["type"] == "web"
        assert spans[0]["meta"]["http.status_code"] == "202"
        assert spans[0]["error"] == 1


@scenarios.default
@features.tracing_configuration_consistency
class Test_Config_HttpClientErrorStatuses_Default:
    """ Verify behavior of http clients """

    def setup_status_code_400(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=400"})

    def test_status_code_400(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 400

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span(spans, resource_name="GET /status", tags={"span.kind": "client"})

        assert client_span.get("meta").get("http.status_code") == "400"
        assert client_span.get("error") == 1

    def setup_status_code_500(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=500"})

    def test_status_code_500(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 500

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span(spans, resource_name="GET /status", tags={"span.kind": "client"})

        assert client_span.get("meta").get("http.status_code") == "500"
        assert client_span.get("error") == None or client_span.get("error") == 0


@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_HttpClientErrorStatuses_FeatureFlagCustom:
    """ Verify behavior of http clients """

    def setup_status_code_200(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=200"})

    def test_status_code_200(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 200

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span(spans, resource_name="GET /status", tags={"span.kind": "client"})

        assert client_span.get("meta").get("http.status_code") == "200"
        assert client_span.get("error") == 1

    def setup_status_code_202(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777/status?code=202"})

    def test_status_code_202(self):
        assert self.r.status_code == 200
        content = json.loads(self.r.text)
        assert content["status_code"] == 202

        interfaces.library.assert_trace_exists(self.r)
        spans = [s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True)]

        client_span = _get_span(spans, resource_name="GET /status", tags={"span.kind": "client"})

        assert client_span.get("meta").get("http.status_code") == "202"
        assert client_span.get("error") == 1


def _get_span(spans, resource_name, tags):
    for s in spans:
        match = True
        if s["resource"] != resource_name:
            continue

        for tagKey in tags:
            if tagKey in s["meta"]:
                expectValue = tags[tagKey]
                actualValue = s["meta"][tagKey]
                if expectValue != actualValue:
                    continue

        if match:
            return s
    return {}

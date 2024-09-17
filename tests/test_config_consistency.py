# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

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

@scenarios.tracing_config_nondefault_2
@features.tracing_configuration_consistency
class Test_Config_IntegrationEnabled_True:
    """ Verify behavior of integrations automatic spans """
    
    def setup_mongodb_integration_enabled_true(self):
        self.r = weblog.get("/integration_enabled_config")

    def test_mongodb_integration_enabled_true(self):
        assert self.r.status_code == 200

        mongodbSpans = []
        # We do not use get_spans: the span we look for is not directly the span that carry the request information
        for data, trace in interfaces.library.get_traces(request=self.r):
            mongodbSpans += [(data, span) for span in trace if span.get("name") == "mongodb.query"]
            
        assert len(mongodbSpans) >= 1

@scenarios.tracing_config_nondefault
@features.tracing_configuration_consistency
class Test_Config_IntegrationEnabled_False:
    """ Verify behavior of integrations automatic spans """

    def setup_mongodb_integration_enabled_false(self):
        self.r = weblog.get("/integration_enabled_config")

    def test_mongodb_integration_enabled_false(self):
        assert self.r.status_code == 200

        mongodbSpans = []
        # We do not use get_spans: the span we look for is not directly the span that carry the request information
        for data, trace in interfaces.library.get_traces(request=self.r):
            mongodbSpans += [(data, span) for span in trace if span.get("name") == "mongodb.query"]
            
        assert len(mongodbSpans) == 0

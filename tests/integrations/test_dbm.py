# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.


import json

from utils import weblog, interfaces, context, scenarios, features
from utils.tools import logger


@features.database_monitoring_correlation
class Test_Dbm:
    """Verify behavior of DBM propagation"""

    META_TAG = "_dd.dbm_trace_injected"

    # Helper Methods
    def weblog_trace_payload(self):
        self.library_name = context.library
        self.scenario_name = context.scenario.name
        self.requests = []

        if self.library_name == "python":
            self.requests = [
                weblog.get("/dbm", params={"integration": "psycopg", "operation": "execute"}),
                weblog.get("/dbm", params={"integration": "psycopg", "operation": "executemany"}),
            ]
        elif self.library_name == "dotnet":
            self.requests = [
                weblog.get("/dbm", params={"integration": "npgsql"}, timeout=20),
            ]
            if self.scenario_name == "INTEGRATIONS":
                self.requests.extend(
                    [
                        weblog.get("/dbm", params={"integration": "mysql"}),
                        weblog.get("/dbm", params={"integration": "sqlclient"}),
                    ]
                ),
        elif self.library_name == "php":
            self.requests = [
                weblog.get("/dbm", params={"integration": "pdo-pgsql"}),
            ]
            if self.scenario_name == "INTEGRATIONS":
                self.requests.extend(
                    [
                        weblog.get("/dbm", params={"integration": "mysqli"}),
                        weblog.get("/dbm", params={"integration": "pdo-mysql"}),
                    ]
                ),

    def _get_db_span(self, response):
        assert response.status_code == 200, f"Request: {self.scenario} wasn't successful."

        spans = []
        # we do not use get_spans: the span we look for is not directly the span that carry the request information
        for data, trace in interfaces.library.get_traces(request=response):
            spans += [(data, span) for span in trace if span.get("type") == "sql"]

        if len(spans) == 0:
            raise ValueError("No span found with meta.type == 'sql'")

        # look for the span with the good resource
        for data, span in spans:
            if span.get("resource") == "SELECT version()" or span.get("resource") == "SELECT @@version":
                logger.debug(f"A matching span in found in {data['log_filename']}")
                return span

        # log span.resource found to help to debug hen resource does not match
        for _, span in spans:
            logger.debug(
                f"Found spans with meta.type=sql span, but the ressource does not match: {span.get('resource')}"
            )

        raise ValueError("No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found.")

    def _assert_spans_are_untagged(self):
        for request in self.requests:
            self._assert_span_is_untagged(self._get_db_span(request))

    def _assert_span_is_untagged(self, span):
        meta = span.get("meta", {})
        assert self.META_TAG not in meta, f"{self.META_TAG} found in span meta: {json.dumps(span, indent=2)}"

    def _assert_span_is_tagged(self, span):
        meta = span.get("meta", {})
        assert self.META_TAG in meta, f"{self.META_TAG} not found in span meta: {json.dumps(span, indent=2)}"
        tag_value = meta.get(self.META_TAG)
        assert tag_value == "true", f"{self.META_TAG} value is not `true`."

    # Setup Methods
    setup_trace_payload_disabled = weblog_trace_payload

    # Test Methods
    @scenarios.appsec_disabled
    def test_trace_payload_disabled(self):
        self._assert_spans_are_untagged()

    setup_trace_payload_service = weblog_trace_payload

    @scenarios.default
    def test_trace_payload_service(self):
        self._assert_spans_are_untagged()

    setup_trace_payload_full = weblog_trace_payload

    @scenarios.integrations
    def test_trace_payload_full(self):
        for request in self.requests:
            span = self._get_db_span(request)

            if span.get("meta", {}).get("db.type") == "sql-server":
                self._assert_span_is_untagged(span)
            else:
                self._assert_span_is_tagged(span)

# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, released, scenarios


@released(cpp="?", golang="?", java="?", nodejs="?", php="?", ruby="?")
@missing_feature(
    context.library in ["python"] and context.weblog_variant != "flask-poc", reason="Missing on weblog",
)
class Test_Dbm:
    """Verify behavior of DBM propagation"""

    # Helper Methods
    def weblog_trace_payload(self):
        self.library_name = context.library
        self.requests = []

        if self.library_name == "python":
            self.requests = [
                weblog.get("/dbm", params={"integration": "psycopg", "operation": "execute"}),
                weblog.get("/dbm", params={"integration": "psycopg", "operation": "executemany"}),
            ]
        elif self.library_name == "dotnet":
            self.requests = [
                weblog.get("/dbm", params={"integration": "mysql"}),
                weblog.get("/dbm", params={"integration": "npgsql"}, timeout=20),
                weblog.get("/dbm", params={"integration": "sqlclient"}),
            ]

    def find_db_spans(self):
        self.db_span = None
        for r in self.requests:
            assert r.status_code == 200, f"Request: {r.request.url} wasn't successful."
            for _, trace in interfaces.library.get_traces(request=r):
                for span in trace:
                    if span.get("resource") == "SELECT version()" or span.get("resource") == "SELECT @@version":
                        self.db_span = span
                        break

    def assert_span_is_tagged(self):
        assert (
            self.db_span is not None
        ), "No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found."
        meta = self.db_span.get("meta", {})
        assert "_dd.dbm_trace_injected" in meta, "_dd.dbm_trace_injected not found in span meta."
        tag_value = meta.get("_dd.dbm_trace_injected")
        assert tag_value == "true", "_dd.dbm_trace_injected value is not `true`."

    def assert_span_is_untagged(self):
        assert (
            self.db_span is not None
        ), "No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found."
        meta = self.db_span.get("meta", {})
        assert "_dd.dbm_trace_injected" not in meta, "_dd.dbm_trace_injected found in span meta."

    # Setup Methods
    def setup_trace_payload_disabled(self):
        self.weblog_trace_payload()

    def setup_trace_payload_service(self):
        self.weblog_trace_payload()

    def setup_trace_payload_full(self):
        self.weblog_trace_payload()

    # Test Methods
    def test_trace_payload_disabled(self):
        self.find_db_spans()
        self.assert_span_is_untagged()

    @scenarios.integrations_service
    def test_trace_payload_service(self):
        self.find_db_spans()
        self.assert_span_is_untagged()

    @scenarios.integrations
    def test_trace_payload_full(self):
        self.find_db_spans()
        self.assert_span_is_tagged()

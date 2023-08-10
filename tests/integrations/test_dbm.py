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
                weblog.get("/dbm", params={"integration": "npgsql"}, timeout=20),
                weblog.get("/dbm", params={"integration": "mysql"}),
                weblog.get("/dbm", params={"integration": "sqlclient"}),
            ]

    def setup_trace_payload_disabled(self):
        self.weblog_trace_payload()

    @scenarios.integrations_service
    def setup_trace_payload_service(self):
        self.weblog_trace_payload()

    @scenarios.integrations
    def setup_trace_payload_full(self):
        self.weblog_trace_payload()

    def test_trace_payload_disabled(self):
        for r in self.requests:
            assert r.status_code == 200, f"Request: {r.request.url} wasn't successful."
            for _, trace in interfaces.library.get_traces(request=r):
                db_span = None
                for span in trace:
                    if span.get("resource") == "SELECT version()" or span.get("resource") == "SELECT @@version":
                        db_span = span
                        break

                assert db_span is not None, "No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found."
                meta = db_span.get("meta", {}) 
                assert "_dd.dbm_trace_injected" not in meta, "_dd.dbm_trace_injected found in span meta."
                break
    
    @scenarios.integrations_service
    def test_trace_payload_service(self):
        for r in self.requests:
            assert r.status_code == 200, f"Request: {r.request.url} wasn't successful."
            for _, trace in interfaces.library.get_traces(request=r):
                db_span = None
                for span in trace:
                    if span.get("resource") == "SELECT version()" or span.get("resource") == "SELECT @@version":
                        db_span = span
                        break

                assert db_span is not None, "No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found."
                meta = db_span.get("meta", {}) 
                assert "_dd.dbm_trace_injected" not in meta, "_dd.dbm_trace_injected found in span meta."
                break

    @scenarios.integrations
    def test_trace_payload_full(self):
        for r in self.requests:
            assert r.status_code == 200, f"Request: {r.request.url} wasn't successful."
            for _, trace in interfaces.library.get_traces(request=r):
                db_span = None
                for span in trace:
                    if span.get("resource") == "SELECT version()" or span.get("resource") == "SELECT @@version":
                        db_span = span
                        break

                assert db_span is not None, "No DB span with expected resource 'SELECT version()' nor 'SELECT @@version' found."
                meta = db_span.get("meta", {}) 
                assert "_dd.dbm_trace_injected" in meta, "_dd.dbm_trace_injected not found in span meta."
                break
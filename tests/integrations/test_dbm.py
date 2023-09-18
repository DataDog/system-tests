# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, scenarios


@missing_feature(
    context.library in ["python"] and context.weblog_variant != "flask-poc", reason="Missing on weblog",
)
@scenarios.integrations
class Test_Dbm:
    """Verify behavior of DBM propagation"""

    def setup_trace_payload(self):
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

    def test_trace_payload(self):
        for r in self.requests:
            assert r.status_code == 200, f"{r.request.url} is not successful"
            for _, _, span in interfaces.library.get_spans(request=r):
                if span.get("span_type") != "sql":
                    return

                meta = span.get("meta", {})
                assert "_dd.dbm_trace_injected" in meta

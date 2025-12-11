# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.


import json
import re

from utils import weblog, interfaces, context, scenarios, features, irrelevant, flaky, bug, logger
from utils._weblog import HttpResponse


def remove_traceparent(s: str) -> str:
    return re.sub(r",traceparent='[^']*'", "", s)


@features.database_monitoring_correlation
class Test_Dbm:
    """Verify behavior of DBM propagation"""

    META_TAG = "_dd.dbm_trace_injected"

    # Helper Methods
    def weblog_trace_payload(self):
        self.library_name = context.library.name
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
                )
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
                )

    def _get_db_span(self, response: HttpResponse) -> dict:
        assert response.status_code == 200, f"Request: {context.scenario.name} wasn't successful."

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

    def _assert_span_is_untagged(self, span: dict) -> None:
        meta = span.get("meta", {})
        assert self.META_TAG not in meta, f"{self.META_TAG} found in span meta: {json.dumps(span, indent=2)}"

    def _assert_span_is_tagged(self, span: dict) -> None:
        meta = span.get("meta", {})
        assert self.META_TAG in meta, f"{self.META_TAG} not found in span meta: {json.dumps(span, indent=2)}"
        tag_value = meta.get(self.META_TAG)
        assert tag_value == "true", f"{self.META_TAG} value is not `true`."

    # Setup Methods
    setup_trace_payload_disabled = weblog_trace_payload

    # Test Methods
    @scenarios.everything_disabled
    def test_trace_payload_disabled(self):
        assert self.requests, "No requests to validate"
        self._assert_spans_are_untagged()

    setup_trace_payload_service = weblog_trace_payload

    @scenarios.default
    # @flaky(context.library >= "dotnet@2.54.0", reason="APMAPI-930")
    def test_trace_payload_service(self):
        assert self.requests, "No requests to validate"
        self._assert_spans_are_untagged()

    setup_trace_payload_full = weblog_trace_payload

    @scenarios.integrations
    @bug(context.library == "python" and context.weblog_variant in ("flask-poc", "uds-flask"), reason="APMAPI-1058")
    def test_trace_payload_full(self):
        assert self.requests, "No requests to validate"
        for request in self.requests:
            span = self._get_db_span(request)

            # full mode for sql server is supported in dotnet (via the context_info)
            if self.library_name != "dotnet" and span.get("meta", {}).get("db.type") == "sql-server":
                self._assert_span_is_untagged(span)
            else:
                self._assert_span_is_tagged(span)


class _BaseDbmComment:
    """Verify DBM comment for given integration"""

    integration: str | None = None
    operation: str | None = None

    # declared in child classes
    dddb: str | None = None  # db name
    dddbs: str | None = None  # db name
    ddh: str | None = None  # container name

    # comment generic info
    dde = "system-tests"  # DD_ENV
    ddps = "weblog"  # DD_SERVICE
    ddpv = "1.0.0"  # DD_VERSION

    def setup_dbm_comment(self):
        self.r = weblog.get("/stub_dbm", params={"integration": self.integration, "operation": self.operation})

    @bug(context.library == "python" and context.weblog_variant in ("flask-poc", "uds-flask"), reason="APMAPI-1058")
    def test_dbm_comment(self):
        assert self.r.status_code == 200, f"Request: {self.r.request.url} wasn't successful."

        try:
            data = json.loads(self.r.text)
        except json.decoder.JSONDecodeError as e:
            raise ValueError(f"Response from {self.r.request.url} should have been JSON") from e

        expected_dbm_comment = f"/*dddb='{self.dddb}',dddbs='{self.dddbs}',dde='{self.dde}',ddh='{self.ddh}',ddps='{self.ddps}',ddpv='{self.ddpv}'*/ SELECT version()"

        assert "status" in data
        assert data["status"] == "ok"
        assert "traceparent" in data["dbm_comment"]
        assert remove_traceparent(data["dbm_comment"]) == expected_dbm_comment


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Psycopg(_BaseDbmComment):
    integration = "psycopg"
    operation = "execute"

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Batch_Python_Psycopg(_BaseDbmComment):
    integration = "psycopg"
    operation = "executemany"

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name

    @flaky(library="python", reason="APMAPI-724")
    def test_dbm_comment(self):
        return super().test_dbm_comment()


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Asyncpg(_BaseDbmComment):
    integration = "asyncpg"
    operation = "execute"

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name


# no batching dbm comment injection for asyncpg


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Aiomysql(_BaseDbmComment):
    integration = "aiomysql"
    operation = "execute"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Batch_Python_Aiomysql(_BaseDbmComment):
    integration = "aiomysql"
    operation = "executemany"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_MysqlConnector(_BaseDbmComment):
    integration = "mysql-connector"
    operation = "execute"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Batch_Python_MysqlConnector(_BaseDbmComment):
    integration = "mysql-connector"
    operation = "executemany"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Mysqldb(_BaseDbmComment):
    integration = "mysqldb"
    operation = "execute"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name

    @flaky(library="python", reason="APMAPI-724")
    def test_dbm_comment(self):
        return super().test_dbm_comment()


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Batch_Python_Mysqldb(_BaseDbmComment):
    integration = "mysqldb"
    operation = "executemany"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name

    @flaky(library="python", reason="APMAPI-724")
    def test_dbm_comment(self):
        return super().test_dbm_comment()


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Pymysql(_BaseDbmComment):
    integration = "pymysql"
    operation = "execute"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name

    @flaky(library="python", reason="APMAPI-724")
    def test_dbm_comment(self):
        return super().test_dbm_comment()


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Batch_Python_Pymysql(_BaseDbmComment):
    integration = "pymysql"
    operation = "executemany"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name

    @flaky(library="python", reason="APMAPI-724")
    def test_dbm_comment(self):
        return super().test_dbm_comment()


@irrelevant(condition=context.library != "nodejs", reason="These are nodejs only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_NodeJS_mysql2(_BaseDbmComment):
    integration = "mysql2"
    operation = "execute"

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


# no dbm batch comment injection for mysql2


@irrelevant(condition=context.library != "nodejs", reason="These are nodejs only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_NodeJS_pg(_BaseDbmComment):
    integration = "pg"
    operation = "execute"

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name


# no dbm batch comment injection for mysql2

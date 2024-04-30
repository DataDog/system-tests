# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.


import json
import re

from utils import weblog, interfaces, context, scenarios, features, irrelevant
from utils.tools import logger


def remove_traceparent(s):
    return re.sub(r",traceparent='[^']*'", "", s)


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


# @features.datastreams_monitoring_support_for_kafka
# @scenarios.integrations
class _Test_Dbm_Comment:
    """ Verify DBM comment for given integration """

    integration = None
    operation = None
    operation_batch = None
    execute_batch = False

    # comment generic info
    dde = "system-tests"  # DD_ENV
    ddps = "weblog"  # DD_SERVICE
    ddpv = "1.0.0"  # DD_VERSION

    def setup_dbm_comment(self):
        self.r = weblog.get("/stub_dbm", params={"integration": self.integration, "operation": self.operation})
        if self.r.text not in [None, ""]:
            try:
                self.r.text = json.loads(self.r.text)
            except json.decoder.JSONDecodeError:
                pass
            self.expected_dbm_comment = f"/*dddb='{self.dddb}',dddbs='{self.dddbs}',dde='{self.dde}',ddh='{self.ddh}',ddps='{self.ddps}',ddpv='{self.ddpv}'*/ SELECT version()"

    def setup_dbm_comment_batch(self):
        if self.execute_batch:
            self.r_batch = weblog.get(
                "/stub_dbm", params={"integration": self.integration, "operation": self.operation_batch}
            )
            if self.r_batch.text not in [None, ""]:
                try:
                    self.r_batch.text = json.loads(self.r_batch.text)
                except json.decoder.JSONDecodeError:
                    pass
                self.expected_dbm_comment = f"/*dddb='{self.dddb}',dddbs='{self.dddbs}',dde='{self.dde}',ddh='{self.ddh}',ddps='{self.ddps}',ddpv='{self.ddpv}'*/ SELECT version()"

    def test_dbm_comment(self):
        assert self.r.text["status"] == "ok"
        assert "traceparent" in self.r.text["dbm_comment"]

        self.r.text["dbm_comment"] = remove_traceparent(self.r.text["dbm_comment"])

        assert self.r.text["dbm_comment"] == self.expected_dbm_comment

    def test_dbm_comment_batch(self):
        if self.execute_batch:
            assert self.r_batch.text["status"] == "ok"
            assert "traceparent" in self.r_batch.text["dbm_comment"]

            self.r_batch.text["dbm_comment"] = remove_traceparent(self.r_batch.text["dbm_comment"])

            assert self.r_batch.text["dbm_comment"] == self.expected_dbm_comment


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Psycopg(_Test_Dbm_Comment):
    integration = "psycopg"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = True

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Asyncpg(_Test_Dbm_Comment):
    integration = "asyncpg"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = False

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Aiomysql(_Test_Dbm_Comment):
    integration = "aiomysql"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = True

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_MysqlConnector(_Test_Dbm_Comment):
    integration = "mysql-connector"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = True

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Mysqldb(_Test_Dbm_Comment):
    integration = "mysqldb"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = True

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "python", reason="These are python only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_Python_Pymysql(_Test_Dbm_Comment):
    integration = "pymysql"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = True

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "nodejs", reason="These are nodejs only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_NodeJS_mysql2(_Test_Dbm_Comment):
    integration = "mysql2"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = False

    dddb = "mysql_dbname"  # db name
    dddbs = "mysql_dbname"  # db name
    ddh = "mysqldb"  # container name


@irrelevant(condition=context.library != "nodejs", reason="These are nodejs only tests.")
@features.database_monitoring_support
@scenarios.integrations
class Test_Dbm_Comment_NodeJS_pg(_Test_Dbm_Comment):
    integration = "pg"
    operation = "execute"
    operation_batch = "executemany"
    execute_batch = False

    dddb = "system_tests_dbname"  # db name
    dddbs = "system_tests_dbname"  # db name
    ddh = "postgres"  # container name

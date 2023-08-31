# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, released, scenarios
from utils.tools import logger
import pytest
import requests
from utils import context
import json
from utils._context.library_version import LibraryVersion


@pytest.fixture(
    scope="session",
    params=[container.dd_integration_service for container in context.scenario.get_containers_by_type("sql_db")],
    ids=[container.dd_integration_service for container in context.scenario.get_containers_by_type("sql_db")],
)
def db_service(request):
    pytest.db_service = request.param
    yield request.param


sql_integration_request = {}


def add_request(db_service, db_operation, weblog_request):
    global sql_integration_request
    if not db_service in sql_integration_request:
        sql_integration_request[db_service] = {}
    sql_integration_request[db_service][db_operation] = weblog_request


@scenarios.integrations_db_sql
class Test_Db_Integrations_sql:
    """ Verify basic DB operations over different databases.
        Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645 """

    def setup_sql_traces(self, db_service_id):
        """ Make request to weblog for each operation: select, update... """
        for db_operation in "select", "insert", "update", "delete", "procedure", "select_error":
            add_request(
                db_service_id, db_operation, weblog.get(f"/db?service={db_service_id}&operation={db_operation}")
            )

    def test_sql_traces(self, db_service):
        """ After make the requests we check that we are producing sql traces """
        for db_operation in sql_integration_request[db_service]:
            assert self._get_sql_span_for_request(sql_integration_request[db_service][db_operation]) is not None

    def test_db_type(self, db_service):
        """ DEPRECATED!! Now it is db.system. An identifier for the database management system (DBMS) product being used.
            Must be one of the available values: https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.type"] == db_service

    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self, db_service):
        """ DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name."""
        db_container = context.scenario.get_container_by_dd_integration_name(db_service)
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.name"] == db_container.db_instance

    def test_span_kind(self, db_service):
        """ Describes the relationship between the Span, its parents, and its children in a Trace."""
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["span.kind"] == "client"

    @missing_feature(library="java", reason="not implemented yet")
    def test_runtime___id(self, db_service):
        """ Unique identifier for the current process."""
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["runtime-id"].strip()

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_system(self, db_service):
        """ An identifier for the database management system (DBMS) product being used. Formerly db.type
                Must be one of the available values: https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.system"] == db_service

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_connection__string(self, db_service):
        """ The connection string used to connect to the database. """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.connection_string"].strip()

    def test_db_user(self, db_service):
        """ Username for accessing the database. """
        db_container = context.scenario.get_container_by_dd_integration_name(db_service)
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.user"].casefold() == db_container.db_user.casefold()

    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_instance(self, db_service):
        """ The name of the database being connected to. Database instance name. Formerly db.name"""
        db_container = context.scenario.get_container_by_dd_integration_name(db_service)
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.instance"] == db_container.db_instance

    # db.statement https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.statement
    # The database statement being executed. This should only be set by the client when a non-obfuscated query is desired. Otherwise the tracer should only put the SQL query in the resource and the Agent will properly obfuscate and set the necessary field.
    # def test_db_statement(self, db_service):
    #         TODO
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_operation(self, db_service):
        """ The name of the operation being executed """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert db_operation in span["meta"]["db.operation"]

    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_sql_table(self, db_service):
        """ The name of the primary table that the operation is acting upon, including the database name (if applicable). """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.sql.table"].strip()

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_row__count(self, db_service):
        """ The number of rows/results from the query or operation. For caches and other datastores. 
        This tag should only set for operations that retrieve stored data, such as GET operations and queries, excluding SET and other commands not returning data.  """
        span = self._get_sql_span_for_request(sql_integration_request[db_service]["select"])
        assert span["meta"]["db.row_count"] > 0

    def test_db_password(self, db_service):
        """ The database password should not show in the traces """
        db_container = context.scenario.get_container_by_dd_integration_name(db_service)
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            for key in span["meta"]:
                if key not in [
                    "peer.hostname",
                    "db.user",
                    "env",
                    "db.instance",
                    "out.host",
                    "db.name",
                    "peer.service",
                ]:  # These fields hostname, user... are the same as password
                    assert span["meta"][key] != db_container.db_password

    @missing_feature(condition=context.library != "java", reason="Apply only java")
    @missing_feature(library="java", reason="Not implemented yet")
    def test_db_jdbc_drive__classname(self, db_service):
        """ The fully-qualified class name of the Java Database Connectivity (JDBC) driver used to connect. """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.jdbc.driver_classname"].strip()

    @pytest.mark.skipif("pytest.db_service != 'mssql'")
    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_db_mssql_instance__name(self, db_service):
        """ The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance. 
            This value should be set only if it’s specified on the mssql connection string. """
        for db_operation in sql_integration_request[db_service]:
            span = self._get_sql_span_for_request(sql_integration_request[db_service][db_operation])
            assert span["meta"]["db.mssql.instance_name"].strip()

    def test_error_message(self, db_service):
        """ A string representing the error message. """
        span = self._get_sql_span_for_request(sql_integration_request[db_service]["select_error"])
        assert span["meta"]["error.message"].strip()

    def test_error_type(self, db_service):
        """ A string representing the type of the error. """
        span = self._get_sql_span_for_request(sql_integration_request[db_service]["select_error"])
        assert span["meta"]["error.type"].strip()

    def test_error_stack(self, db_service):
        """ A human readable version of the stack trace. """
        span = self._get_sql_span_for_request(sql_integration_request[db_service]["select_error"])
        assert span["meta"]["error.stack"].strip()

    def _get_sql_span_for_request(self, weblog_request):
        for data, trace, span in interfaces.library.get_spans(weblog_request):
            logger.info(f"Span found with trace id: {span['trace_id']} and span id: {span['span_id']}")
            for trace in data["request"]["content"]:
                for span_child in trace:
                    if (
                        "type" in span_child
                        and span_child["type"] == "sql"
                        and span_child["trace_id"] == span["trace_id"]
                        and span_child["resource"]
                        != "SELECT 1;"  # workaround to avoid conflicts on connection check on mssql
                    ):
                        logger.debug("Span type sql found!")
                        logger.info(
                            f"CHILD Span found with trace id: {span_child['trace_id']} and span id: {span_child['span_id']}"
                        )
                        return span_child

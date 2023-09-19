# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, interfaces, context, bug, missing_feature, scenarios
from utils.tools import logger

# @scenarios.integrations
class _BaseIntegrationsSqlTestClass:

    """ Verify basic DB operations over different databases.
        Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645 """

    db_service = None
    requests = {}

    # Set to false
    tracer_interface_validation = True

    @classmethod
    def _setup(cls):
        """ Make request to weblog for each operation: select, update... """

        if cls.db_service in cls.requests:
            return  #  requests has been made ...

        cls.requests[cls.db_service] = {}

        # Initiaze DB
        logger.info("Initializing DB...")
        response_db_creation = weblog.get(
            "/db", params={"service": cls.db_service, "operation": "init"}, timeout=20
        )  # DB initialization can take more time ( mssql )
        logger.info(f"Response from de init endpoint: {response_db_creation.text}")

        # Request for db operations
        logger.info("Perform queries.....")
        for db_operation in ["select", "insert", "update", "delete", "procedure", "select_error"]:
            cls.requests[cls.db_service][db_operation] = weblog.get(
                "/db", params={"service": cls.db_service, "operation": db_operation}
            )

    # Setup methods
    setup_sql_traces = _setup
    setup_resource = _setup
    setup_db_type = _setup
    setup_db_name = _setup
    setup_error_stack = _setup
    setup_error_type = _setup
    setup_error_message = _setup
    setup_db_mssql_instance__name = _setup
    setup_db_jdbc_drive__classname = _setup
    setup_db_password = _setup
    setup_db_row__count = _setup
    setup_db_sql_table = _setup
    setup_db_operation = _setup
    setup_db_instance = _setup
    setup_db_user = _setup
    setup_db_connection__string = _setup
    setup_db_system = _setup
    setup_runtime___id = _setup
    setup_span_kind = _setup

    # Tests methods
    def test_sql_traces(self):
        """ After make the requests we check that we are producing sql traces """
        for db_operation, request in self.requests[self.db_service].items():
            assert self._get_sql_span_for_request(request) is not None, f"Test is failing for {db_operation}"

    def test_resource(self):
        """ Usually the query """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation not in ["procedure", "select_error"]:
                span = self._get_sql_span_for_request(request)
                assert db_operation in span["resource"].lower()

    @missing_feature(library="python", reason="Python is using the correct span: db.system")
    def test_db_type(self):
        """ DEPRECATED!! Now it is db.system. An identifier for the database management system (DBMS) product being used.
            Must be one of the available values: https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.type"] == self.db_service, f"Test is failing for {db_operation}"

    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self):
        """ DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name."""
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.name"] == db_container.db_instance, f"Test is failing for {db_operation}"

    def test_span_kind(self):
        """ Describes the relationship between the Span, its parents, and its children in a Trace."""
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["span.kind"] == "client"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_runtime___id(self):
        """ Unique identifier for the current process."""
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["runtime-id"].strip(), f"Test is failing for {db_operation}"

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_system(self):
        """ An identifier for the database management system (DBMS) product being used. Formerly db.type
                Must be one of the available values: https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.system"] == self.db_service, f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_connection__string(self):
        """ The connection string used to connect to the database. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.connection_string"].strip(), f"Test is failing for {db_operation}"

    def test_db_user(self):
        """ Username for accessing the database. """
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert (
                span["meta"]["db.user"].casefold() == db_container.db_user.casefold()
            ), f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_instance(self):
        """ The name of the database being connected to. Database instance name. Formerly db.name"""
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.instance"] == db_container.db_instance, f"Test is failing for {db_operation}"

    # db.statement https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.statement
    # The database statement being executed. This should only be set by the client when a non-obfuscated query is desired. Otherwise the tracer should only put the SQL query in the resource and the Agent will properly obfuscate and set the necessary field.
    # def test_db_statement(self, db_service):
    #         TODO
    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_operation(self):
        """ The name of the operation being executed """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert db_operation in span["meta"]["db.operation"], f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_sql_table(self):
        """ The name of the primary table that the operation is acting upon, including the database name (if applicable). """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.sql.table"].strip(), f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_row__count(self):
        """ The number of rows/results from the query or operation. For caches and other datastores. 
        This tag should only set for operations that retrieve stored data, such as GET operations and queries, excluding SET and other commands not returning data.  """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select"])
        assert span["meta"]["db.row_count"] > 0, "Test is failing for select"

    def test_db_password(self):
        """ The database password should not show in the traces """
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
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
                    assert span["meta"][key] != db_container.db_password, f"Test is failing for {db_operation}"

    @missing_feature(condition=context.library != "java", reason="Apply only java")
    @missing_feature(library="java", reason="Not implemented yet")
    def test_db_jdbc_drive__classname(self):
        """ The fully-qualified class name of the Java Database Connectivity (JDBC) driver used to connect. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.jdbc.driver_classname"].strip(), f"Test is failing for {db_operation}"

    def test_error_message(self):
        """ A string representing the error message. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.message"].strip()

    def test_error_type(self):
        """ A string representing the type of the error. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.type"].strip()

    def test_error_stack(self):
        """ A human readable version of the stack trace. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.stack"].strip()

    def _get_sql_span_for_request(self, weblog_request):
        """To be implemented by subclasses"""
        return {}


@scenarios.integrations
class _BaseTracerIntegrationsSqlTestClass(_BaseIntegrationsSqlTestClass):
    def test_NOT_obfuscate_query(self):
        """ All queries come out without obfuscation from tracer library """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["resource"].count("?") == 0

    def _get_sql_span_for_request(self, weblog_request):
        for data, trace, span in interfaces.library.get_spans(weblog_request):
            logger.info(f"Span found with trace id: {span['trace_id']} and span id: {span['span_id']} ")
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
                            f"CHILD Span found with trace id: {span_child['trace_id']} and span id: {span_child['span_id']} "
                        )
                        return span_child


@scenarios.integrations
class _BaseAgentIntegrationsSqlTestClass(_BaseIntegrationsSqlTestClass):
    def test_sql_query(self):
        """ Usually the query """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation not in ["procedure", "select_error"]:
                span = self._get_sql_span_for_request(request)
                assert db_operation in span["meta"]["sql.query"].lower()

    def test_obfuscate_query(self):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            # We launch all queries with two parameters (from weblog)
            # Insert and procedure:These operations also receive two parameters, but are obfuscated as only one.
            if db_operation in ["insert", "procedure"]:
                assert span["meta"]["sql.query"].count("?") == 1
            else:
                assert span["meta"]["sql.query"].count("?") == 2

    def _get_sql_span_for_request(self, weblog_request):
        for data, span in interfaces.agent.get_spans(weblog_request):
            logger.info(
                f"Agent: Span found with trace id: {span['traceID']} and span id: {span['spanID']} in file {data['log_filename']}"
            )
            content = data["request"]["content"]["tracerPayloads"]
            for payload in content:
                for chunk in payload["chunks"]:
                    for span_child in chunk["spans"]:
                        if (
                            "type" in span_child
                            and span_child["type"] == "sql"
                            and span_child["traceID"] == span["traceID"]
                            and span_child["resource"]
                            != "SELECT ?"  # workaround to avoid conflicts on connection check on mssql
                        ):
                            logger.debug("Agent: Span type sql found!")
                            logger.info(
                                f"Agent: Span SQL found with trace id: {span_child['traceID']} and span id: {span_child['spanID']}"
                            )
                            logger.debug(f"Agent: Span: {span_child}")
                            return span_child


############################################################
# Postgres: Tracer and Agent validations
############################################################
class Test_Tracer_Postgres_db_integration(_BaseTracerIntegrationsSqlTestClass):
    db_service = "postgresql"

    @missing_feature(library="python", reason="Python is using the correct span: db.system")
    @bug(library="nodejs", reason="the value of this span should be 'postgresql' instead of  'postgres' ")
    def test_db_type(self):
        super().test_db_type()


class Test_Agent_Postgres_db_integration(_BaseAgentIntegrationsSqlTestClass):
    db_service = "postgresql"

    @missing_feature(library="python", reason="Python is using the correct span: db.system")
    @bug(library="nodejs", reason="the value of this span should be 'postgresql' instead of  'postgres' ")
    def test_db_type(self):
        super().test_db_type()


############################################################
# Mysql: Tracer and Agent validations
############################################################
class Test_Tracer_Mysql_db_integration(_BaseTracerIntegrationsSqlTestClass):
    db_service = "mysql"

    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    @bug(library="python", reason="the value of this span should be 'world' instead of  'b'world'' ")
    def test_db_name(self):
        super().test_db_name()

    @bug(library="python", reason="the value of this span should be 'mysqldb' instead of  'b'mysqldb'' ")
    def test_db_user(self):
        super().test_db_user()


class Test_Agent_Mysql_db_integration(_BaseAgentIntegrationsSqlTestClass):
    db_service = "mysql"

    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    @bug(library="python", reason="the value of this span should be 'world' instead of  'b'world'' ")
    def test_db_name(self):
        super().test_db_name()

    @bug(library="python", reason="the value of this span should be 'mysqldb' instead of  'b'mysqldb'' ")
    def test_db_user(self):
        super().test_db_user()


############################################################
# Mssql: Tracer and Agent validations
############################################################
class Test_Tracer_Mssql_db_integration(_BaseTracerIntegrationsSqlTestClass):
    db_service = "mssql"

    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_db_mssql_instance__name(self):
        """ The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance. 
            This value should be set only if it’s specified on the mssql connection string. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.mssql.instance_name"].strip(), f"Test is failing for {db_operation}"

    @bug(library="python", reason="bug on pyodbc driver?")
    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self):
        super().test_db_name()

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @bug(library="python", reason="bug on pyodbc driver?")
    def test_db_system(self):
        super().test_db_system()

    @bug(library="python", reason="bug on pyodbc driver?")
    def test_db_user(self):
        super().test_db_user()


class Test_Agent_Mssql_db_integration(_BaseAgentIntegrationsSqlTestClass):
    db_service = "mssql"

    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    def test_db_mssql_instance__name(self):
        """ The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance. 
            This value should be set only if it’s specified on the mssql connection string. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.mssql.instance_name"].strip(), f"Test is failing for {db_operation}"

    @bug(library="python", reason="bug on pyodbc driver?")
    @missing_feature(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self):
        super().test_db_name()

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @bug(library="python", reason="bug on pyodbc driver?")
    def test_db_system(self):
        super().test_db_system()

    @bug(library="python", reason="bug on pyodbc driver?")
    def test_db_user(self):
        super().test_db_user()

    def test_obfuscate_query(self):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            # We launch all queries with two parameters (from weblog)
            # Insert and procedure:These operations also receive two parameters, but are obfuscated as only one.
            if db_operation in ["insert"]:
                assert span["meta"]["sql.query"].count("?") == 1
            elif db_operation in ["procedure"]:
                # The proccedure has a input parameter, but we are calling through method execute and we can't see the parameters in the traces
                assert span["meta"]["sql.query"].count("?") == 0
            else:
                assert span["meta"]["sql.query"].count("?") == 2

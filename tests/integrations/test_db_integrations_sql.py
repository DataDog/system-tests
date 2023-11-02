# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import weblog, interfaces, context, bug, missing_feature, irrelevant, scenarios
from utils.tools import logger


class _BaseIntegrationsSqlTestClass:

    """ Verify basic DB operations over different databases.
        Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645 """

    db_service = None
    requests = {}

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
    def test_sql_traces(self, excluded_operations=()):
        """ After make the requests we check that we are producing sql traces """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue
            assert self._get_sql_span_for_request(request) is not None, f"Test is failing for {db_operation}"

    def test_resource(self):
        """ Usually the query """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation not in ["procedure", "select_error"]:
                span = self._get_sql_span_for_request(request)
                assert db_operation in span["resource"].lower()

    def test_sql_success(self, excluded_operations=()):
        """ We check all sql launched for the app work """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue
            if db_operation not in ["select_error"]:
                span = self._get_sql_span_for_request(request)
                assert "error" not in span or span["error"] == 0

    @irrelevant(library="python", reason="Python is using the correct span: db.system")
    @irrelevant(library="java_otel", reason="Open Telemetry is using the correct span: db.system")
    @irrelevant(library="python_otel", reason="Open Telemetry is using the correct span: db.system")
    @irrelevant(library="nodejs_otel", reason="Open Telemetry is using the correct span: db.system")
    def test_db_type(self, excluded_operations=()):
        """ DEPRECATED!! Now it is db.system. An identifier for the database management system (DBMS) product being used.
            Must be one of the available values: https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.type"] == self.db_service, f"Test is failing for {db_operation}"

    @irrelevant(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self):
        """ DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name."""
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.name"] == db_container.db_instance, f"Test is failing for {db_operation}"

    def test_span_kind(self, excluded_operations=()):
        """ Describes the relationship between the Span, its parents, and its children in a Trace."""
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

            span = self._get_sql_span_for_request(request)
            assert span["meta"]["span.kind"] == "client"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @irrelevant(library="java_otel", reason="not supported by open telemetry")
    @irrelevant(library="python_otel", reason="not supported by open telemetry")
    @irrelevant(library="nodejs_otel", reason="not supported by open telemetry")
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
    @missing_feature(library="python_otel", reason="Open telemetry doesn't send this span for python")
    def test_db_connection__string(self):
        """ The connection string used to connect to the database. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.connection_string"].strip(), f"Test is failing for {db_operation}"

    def test_db_user(self, excluded_operations=()):
        """ Username for accessing the database. """
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

            span = self._get_sql_span_for_request(request)
            assert (
                span["meta"]["db.user"].casefold() == db_container.db_user.casefold()
            ), f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    @irrelevant(library="java_otel", reason="Open Telemetry uses db.name")
    @irrelevant(library="python_otel", reason="Open Telemetry uses db.name")
    @irrelevant(library="nodejs_otel", reason="Open Telemetry uses db.name")
    def test_db_instance(self, excluded_operations=()):
        """ The name of the database being connected to. Database instance name. Formerly db.name"""
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.instance"] == db_container.db_instance, f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    def test_db_statement_query(self):
        """ Usually the query """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation not in ["procedure", "select_error"]:
                span = self._get_sql_span_for_request(request)
                assert (
                    db_operation in span["meta"]["db.statement"].lower()
                ), f"db.statement span not found for operation {db_operation}"

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="python", reason="not implemented yet")
    @bug(library="python_otel", reason="Open Telemetry doesn't send this span for python but it should do")
    @bug(library="nodejs_otel", reason="Open Telemetry doesn't send this span for nodejs but it should do")
    def test_db_operation(self, excluded_operations=()):
        """ The name of the operation being executed """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

            span = self._get_sql_span_for_request(request)
            if db_operation == "select_error":
                continue
            if db_operation == "procedure":
                assert any(
                    substring in span["meta"]["db.operation"].lower() for substring in ["call", "exec"]
                ), "db.operation span not found for procedure operation"
            else:
                assert (
                    db_operation.lower() in span["meta"]["db.operation"].lower()
                ), f"Test is failing for {db_operation}"
            if db_operation == "select_error":
                continue
            if db_operation == "procedure":
                assert any(
                    substring in span["meta"]["db.operation"].lower() for substring in ["call", "exec"]
                ), "db.operation span not found for procedure operation"
            else:
                assert (
                    db_operation.lower() in span["meta"]["db.operation"].lower()
                ), f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(
        library="python_otel",
        reason="Open Telemetry doesn't send this span for python. But according to the OTEL specification it would be recommended ",
    )
    @missing_feature(
        library="nodejs_otel",
        reason="Open Telemetry doesn't send this span for nodejs. But according to the OTEL specification it would be recommended",
    )
    def test_db_sql_table(self):
        """ The name of the primary table that the operation is acting upon, including the database name (if applicable). """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            if db_operation is not "procedure":
                assert span["meta"]["db.sql.table"].strip(), f"Test is failing for {db_operation}"
            if db_operation is not "procedure":
                assert span["meta"]["db.sql.table"].strip(), f"Test is failing for {db_operation}"

    @missing_feature(library="python", reason="not implemented yet")
    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    def test_db_row__count(self):
        """ The number of rows/results from the query or operation. For caches and other datastores. 
        This tag should only set for operations that retrieve stored data, such as GET operations and queries, excluding SET and other commands not returning data.  """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select"])
        assert span["meta"]["db.row_count"] > 0, "Test is failing for select"

    def test_db_password(self, excluded_operations=()):
        """ The database password should not show in the traces """
        db_container = context.scenario.get_container_by_dd_integration_name(self.db_service)
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

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
                    "net.peer.name",
                ]:  # These fields hostname, user... are the same as password
                    assert span["meta"][key] != db_container.db_password, f"Test is failing for {db_operation}"

    @missing_feature(condition=context.library != "java", reason="Apply only java")
    @missing_feature(library="java", reason="Not implemented yet")
    def test_db_jdbc_drive__classname(self):
        """ The fully-qualified class name of the Java Database Connectivity (JDBC) driver used to connect. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"]["db.jdbc.driver_classname"].strip(), f"Test is failing for {db_operation}"

    @bug(
        library="java_otel",
        reason="OpenTelemetry uses error.msg. Pending confirmation if this is a bug or if it is irrelevant.",
    )
    @bug(
        library="python_otel",
        reason="OpenTelemetry uses error.msg. Pending confirmation if this is a bug or if it is irrelevant.",
    )
    @bug(
        library="nodejs_otel",
        reason="OpenTelemetry uses error.msg. Pending confirmation if this is a bug or if it is irrelevant.",
    )
    def test_error_message(self):
        """ A string representing the error message. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.message"].strip()

    @missing_feature(library="nodejs_otel", reason="Open telemetry with nodejs is not generating this information.")
    def test_error_type(self):
        """ A string representing the type of the error. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.type"].strip()

    @missing_feature(library="nodejs_otel", reason="Open telemetry with nodejs is not generating this information.")
    def test_error_stack(self):
        """ A human readable version of the stack trace. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert span["meta"]["error.stack"].strip()

    def _get_sql_span_for_request(self, weblog_request):
        """Returns the spans associated with a request. Should be implemented by subclasses in order to get this info from library or agent interfaces"""
        raise NotImplementedError("This method should be implemented by subclasses")


class _BaseTracerIntegrationsSqlTestClass(_BaseIntegrationsSqlTestClass):
    """ Encapsulates tracer interface specific validations """

    @missing_feature(
        library="java",
        reason="The Java tracer normalizing the SQL by replacing literals to reduce resource-name cardinality",
    )
    def test_NOT_obfuscate_query(self):
        """ All queries come out without obfuscation from tracer library """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["resource"].count("?") == 0, f"The query should not be obfuscated for operation {db_operation}"

    def _get_sql_span_for_request(self, weblog_request):
        for _, _, span in interfaces.library.get_spans(weblog_request):
            logger.info(f"Span found with trace id: {span['trace_id']} and span id: {span['span_id']}")

            # iterate over all trace to be sure to miss nothing
            for _, _, span_child in interfaces.library.get_spans():
                if span_child["trace_id"] != span["trace_id"]:
                    continue

                logger.debug(f"Check if span {span_child['span_id']} could match")

                if span_child["resource"] == "SELECT 1;":  # workaround to avoid conflicts on connection check on mssql
                    logger.debug(f"Wrong resource:{span_child.get('resource')}, continue...")
                    continue

                if span_child.get("type") != "sql":
                    logger.debug(f"Wrong type:{span_child.get('type')}, continue...")
                    continue

                logger.info(f"Span type==sql found: {span_child['span_id']}")
                return span_child

        raise ValueError(f"Span is not found for {weblog_request.request.url}")


class _BaseAgentIntegrationsSqlTestClass(_BaseIntegrationsSqlTestClass):
    """ Encapsulates agent interface specific validations """

    @irrelevant(library="java_otel", reason="OpenTelemetry uses db.statement")
    @irrelevant(library="python_otel", reason="OpenTelemetry uses db.statement")
    @irrelevant(library="nodejs_otel", reason="OpenTelemetry uses db.statement")
    def test_sql_query(self):
        """ Usually the query """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation not in ["procedure", "select_error"]:
                span = self._get_sql_span_for_request(request)
                assert (
                    db_operation in span["meta"]["sql.query"].lower()
                ), f"sql.query span not found for operation {db_operation}"

    def test_obfuscate_query(self, excluded_operations=()):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            if db_operation in excluded_operations:
                continue

            span = self._get_sql_span_for_request(request)
            # We launch all queries with two parameters (from weblog)
            # Insert and procedure:These operations also receive two parameters, but are obfuscated as only one.
            if db_operation in ["insert", "procedure"]:
                assert (
                    span["meta"]["sql.query"].count("?") == 1
                ), f"The query is not properly obfuscated for operation {db_operation}"
            else:
                assert (
                    span["meta"]["sql.query"].count("?") == 2
                ), f"The query is not properly obfuscated for operation {db_operation}"

    def _get_sql_span_for_request(self, weblog_request):
        for data, span in interfaces.agent.get_spans(weblog_request):
            logger.debug(f"Span found: trace id={span['traceID']}; span id={span['spanID']} ({data['log_filename']})")

            # iterate over everything to be sure to miss nothing
            for _, span_child in interfaces.agent.get_spans():
                if span_child["traceID"] != span["traceID"]:
                    continue

                logger.debug(f"Checking if span {span_child['spanID']} could match")

                if span_child.get("type") not in ("sql", "db"):
                    logger.debug(f"Wrong type:{span_child.get('type')}, continue...")
                    # no way it's the span we're looking for
                    continue

                # workaround to avoid conflicts on connection check on mssql
                # workaround to avoid conflicts on connection check on mssql + nodejs + opentelemetry (there is a bug in the sql obfuscation)
                if span_child["resource"] in ("SELECT ?", "SELECT 1;"):
                    logger.debug(f"Wrong resource:{span_child.get('resource')}, continue...")
                    continue

                # workaround to avoid conflicts on postgres + nodejs + opentelemetry
                if span_child["name"] == "pg.connect":
                    logger.debug(f"Wrong name:{span_child.get('name')}, continue...")
                    continue

                # workaround to avoid conflicts on mssql + nodejs + opentelemetry
                if span_child["meta"].get("db.statement") == "SELECT 1;":
                    logger.debug(f"Wrong db.statement:{span_child.get('meta', {}).get('db.statement')}, continue...")
                    continue

                logger.info(f"Span type==sql found: spanId={span_child['spanID']}")

                return span_child

        raise ValueError(f"Span is not found for {weblog_request.request.url}")


class _BaseOtelAgentIntegrationsSqlTestClass(_BaseAgentIntegrationsSqlTestClass):
    """ Overwrite or add specific methods (on agent interface) for application that has been auto intrumented by Open Telemetry """

    def test_error_msg(self):
        """ A string representing the error message. """
        span = self._get_sql_span_for_request(self.requests[self.db_service]["select_error"])
        assert len(span["meta"]["error.msg"].strip()) != 0

    @bug(library="python_otel", reason="https://datadoghq.atlassian.net/browse/OTEL-940")
    @bug(library="nodejs_otel", reason="https://datadoghq.atlassian.net/browse/OTEL-940")
    def test_obfuscate_query(self):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            if db_operation in ["update", "delete", "procedure", "select_error"]:
                assert (
                    span["meta"]["db.statement"].count("?") == 2
                ), f"The query is not properly obfuscated for operation {db_operation}"
            else:
                assert (
                    span["meta"]["db.statement"].count("?") == 3
                ), f"The query is not properly obfuscated for operation {db_operation}"

    @irrelevant(library="java_otel", reason="Open Telemetry doesn't generate this span")
    @irrelevant(library="python_otel", reason="Open Telemetry doesn't generate this span")
    @irrelevant(library="nodejs_otel", reason="Open Telemetry doesn't generate this span")
    def test_db_row__count(self):
        super().test_db_row__count()


################################################################################
# Postgres: Tracer and Agent validations (dd-tracer and open telemetry tracer)
################################################################################
class _Base_Postgres_db_integration(_BaseIntegrationsSqlTestClass):
    """ Overwrite or add specific methods for postgres (Validations works on agent and tracer interfaces) """

    db_service = "postgresql"

    @bug(library="nodejs", reason="the value of this span should be 'postgresql' instead of  'postgres' ")
    @irrelevant(library="python", reason="Python is using the correct span: db.system")
    @irrelevant(library="python_otel", reason="Open Telemetry is using the correct span: db.system")
    @irrelevant(library="java_otel", reason="Open Telemetry is using the correct span: db.system")
    @irrelevant(library="nodejs_otel", reason="Open Telemetry is using the correct span: db.system")
    def test_db_type(self):
        super().test_db_type()


@scenarios.integrations
class Test_Tracer_Postgres_db_integration(_BaseTracerIntegrationsSqlTestClass, _Base_Postgres_db_integration):
    """ Overwrite or add specific validation methods for postgres on tracer interface """

    pass


@scenarios.integrations
class Test_Agent_Postgres_db_integration(_BaseAgentIntegrationsSqlTestClass, _Base_Postgres_db_integration):
    """ Overwrite or add specific validation methods for postgres on agent interface """

    pass


@scenarios.otel_integrations
class Test_Agent_Postgres_db_otel_integration(_BaseOtelAgentIntegrationsSqlTestClass, _Base_Postgres_db_integration):
    """ Overwrite or add specific validation methods for postgres on agent interface (app instrumented by open telemetry) """

    pass


################################################################################
# Mysql: Tracer and Agent validations (dd-tracer and open telemetry tracer)
################################################################################
class _Base_Mysql_db_integration(_BaseIntegrationsSqlTestClass):
    """ Overwrite or add specific methods for Mysql (Validations works on agent and tracer interfaces) """

    db_service = "mysql"

    @irrelevant(library="java", reason="Java is using the correct span: db.instance")
    @bug(library="python", reason="the value of this span should be 'world' instead of  'b'world'' ")
    def test_db_name(self):
        super().test_db_name()

    @bug(library="python", reason="the value of this span should be 'mysqldb' instead of  'b'mysqldb'' ")
    @bug(context.library >= "java@1.23.0", reason="procedure is not generating this span")
    def test_db_user(self, excluded_operations=()):
        super().test_db_user()

    @irrelevant(context.library != "java")
    def test_db_user_partial(self):
        super().test_db_user(excluded_operations=("procedure",))


@scenarios.integrations
class Test_Tracer_Mysql_db_integration(_BaseTracerIntegrationsSqlTestClass, _Base_Mysql_db_integration):
    """ Overwrite or add specific validation methods for mysql on tracer interface """

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_password(self, excluded_operations=()):
        super().test_db_password()

    @irrelevant(context.library != "java")
    def test_db_password_partial(self):
        """ continue testing other operation on java"""
        super().test_db_password(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_operation(self, excluded_operations=()):
        super().test_db_operation()

    @irrelevant(context.library != "java")
    def test_db_operation_partial(self):
        """ continue testing other operation on java"""
        super().test_db_operation(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_instance(self, excluded_operations=()):
        super().test_db_instance()

    @irrelevant(context.library != "java")
    def test_db_instance_partial(self):
        """ continue testing other operation on java"""
        super().test_db_instance(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_span_kind(self, excluded_operations=()):
        super().test_span_kind()

    @irrelevant(context.library != "java")
    def test_span_kind_partial(self):
        """ continue testing other operation on java"""
        super().test_span_kind(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_type(self, excluded_operations=()):
        super().test_db_type()

    @irrelevant(context.library != "java")
    def test_db_type_partial(self):
        """ continue testing other operation on java"""
        super().test_db_type(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_sql_success(self, excluded_operations=()):
        super().test_sql_success()

    @irrelevant(context.library != "java")
    def test_sql_success_partial(self):
        """ continue testing other operation on java"""
        super().test_sql_success(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_sql_traces(self, excluded_operations=()):
        super().test_sql_traces()

    @irrelevant(context.library != "java")
    def test_sql_traces_partial(self):
        """ continue testing other operation on java"""
        super().test_sql_traces(excluded_operations=("procedure",))


@scenarios.integrations
class Test_Agent_Mysql_db_integration(_BaseAgentIntegrationsSqlTestClass, _Base_Mysql_db_integration):
    """ Overwrite or add specific validation methods for mysql on agent interface """

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_obfuscate_query(self, excluded_operations=()):
        super().test_obfuscate_query()

    @irrelevant(context.library != "java")
    def test_obfuscate_query_partial(self):
        """ continue testing other operation on java"""
        super().test_obfuscate_query(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_password(self, excluded_operations=()):
        super().test_db_password()

    @irrelevant(context.library != "java")
    def test_db_password_partial(self):
        """ continue testing other operation on java"""
        super().test_db_password(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_operation(self, excluded_operations=()):
        super().test_db_operation()

    @irrelevant(context.library != "java")
    def test_db_operation_partial(self):
        """ continue testing other operation on java"""
        super().test_db_operation(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_instance(self, excluded_operations=()):
        super().test_db_instance()

    @irrelevant(context.library != "java")
    def test_db_instance_partial(self):
        """ continue testing other operation on java"""
        super().test_db_instance(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_span_kind(self, excluded_operations=()):
        super().test_span_kind()

    @irrelevant(context.library != "java")
    def test_span_kind_partial(self):
        """ continue testing other operation on java"""
        super().test_span_kind(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_db_type(self, excluded_operations=()):
        super().test_db_type()

    @irrelevant(context.library != "java")
    def test_db_type_partial(self):
        """ continue testing other operation on java"""
        super().test_db_type(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_sql_success(self, excluded_operations=()):
        super().test_sql_success()

    @irrelevant(context.library != "java")
    def test_sql_success_partial(self):
        """ continue testing other operation on java"""
        super().test_sql_success(excluded_operations=("procedure",))

    @bug(context.library >= "java@1.23.0", reason="procedure queries are not reported")
    def test_sql_traces(self, excluded_operations=()):
        super().test_sql_success()

    @irrelevant(context.library != "java")
    def test_sql_traces_partial(self):
        """ continue testing other operation on java"""
        super().test_sql_traces(excluded_operations=("procedure",))


@scenarios.otel_integrations
class Test_Agent_Mysql_db_otel_integration(_BaseOtelAgentIntegrationsSqlTestClass, _Base_Mysql_db_integration):
    """ Overwrite or add specific validation methods for mysql on agent interface (app instrumented by open telemetry) """

    pass


################################################################################
# Mssql: Tracer and Agent validations (dd-tracer and open telemetry tracer)
################################################################################
class _Base_Mssql_db_integration(_BaseIntegrationsSqlTestClass):
    """ Overwrite or add specific methods for Mssql (Validations works on agent and tracer interfaces) """

    db_service = "mssql"

    @missing_feature(library="python", reason="Not implemented yet")
    @missing_feature(library="java", reason="Not implemented yet")
    @missing_feature(library="nodejs", reason="Not implemented yet")
    @irrelevant(
        library="java_otel", reason="Open Telemetry doesn't generate this span. It's recomended but not mandatory"
    )
    @irrelevant(
        library="nodejs_otel", reason="Open Telemetry doesn't generate this span. It's recomended but not mandatory"
    )
    def test_db_mssql_instance__name(self):
        """ The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance. 
            This value should be set only if it’s specified on the mssql connection string. """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            assert span["meta"][
                "db.mssql.instance_name"
            ].strip(), f"db.mssql.instance_name must not be empty for operation {db_operation}"

    @bug(library="python", reason=" https://github.com/DataDog/dd-trace-py/issues/7104")
    @irrelevant(library="java", reason="Java is using the correct span: db.instance")
    def test_db_name(self):
        super().test_db_name()

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @bug(library="python", reason="https://github.com/DataDog/dd-trace-py/issues/7104")
    def test_db_system(self):
        super().test_db_system()

    @bug(library="python", reason="https://github.com/DataDog/dd-trace-py/issues/7104")
    def test_db_user(self):
        super().test_db_user()


@scenarios.integrations
class Test_Tracer_Mssql_db_integration(_BaseTracerIntegrationsSqlTestClass, _Base_Mssql_db_integration):
    """ Overwrite or add specific validation methods for mssql on tracer interface """

    pass


@scenarios.integrations
class Test_Agent_Mssql_db_integration(_BaseAgentIntegrationsSqlTestClass, _Base_Mssql_db_integration):
    """ Overwrite or add specific validation methods for mssql on agent interface """

    def test_obfuscate_query(self):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            # We launch all queries with two parameters (from weblog)
            if db_operation == "insert":
                expected_obfuscation_count = 1
            elif db_operation == "procedure":
                # Insert and procedure:These operations also receive two parameters, but are obfuscated as only one.
                # Nodejs: The proccedure has a input parameter, but we are calling through method `execute`` and we can't see the parameters in the traces
                expected_obfuscation_count = 0 if context.library.library == "nodejs" else 2
            else:
                expected_obfuscation_count = 2

            observed_obfuscation_count = span["meta"]["sql.query"].count("?")
            assert (
                observed_obfuscation_count == expected_obfuscation_count
            ), f"The mssql query is not properly obfuscated for operation {db_operation}, expecting {expected_obfuscation_count} obfuscation(s), found {observed_obfuscation_count}:\n {span['meta']['sql.query']}"


@scenarios.otel_integrations
class Test_Agent_Mssql_db_otel_integration(_BaseOtelAgentIntegrationsSqlTestClass, _Base_Mssql_db_integration):
    """ Overwrite or add specific validation methods for mssql on agent interface (app instrumented by open telemetry) """

    @bug(library="nodejs_otel", reason="We are not generating this span")
    def test_db_operation(self):
        """ The name of the operation being executed. Mssql and Open Telemetry doesn't report this span when we call to procedure """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)
            # db.operation span is not generating by Open Telemetry when we call to procedure or we have a syntax error on the SQL
            if db_operation not in ["select_error", "procedure"]:
                assert (
                    db_operation.lower() in span["meta"]["db.operation"].lower()
                ), f"Test is failing for {db_operation}"

    @bug(
        library="nodejs_otel",
        reason="Resource span is not generating correctly. We find resource value: execsql master",
    )
    def test_resource(self):
        super().test_resource()

    @irrelevant(
        library="nodejs_otel",
        reason="Open telemetry doesn't send this span for nodejs and mssql. It's recomended but not mandatory",
    )
    def test_db_connection__string(self):
        super().test_db_connection__string()

    @bug(library="nodejs_otel", reason="https://datadoghq.atlassian.net/browse/OTEL-940")
    def test_obfuscate_query(self):
        """ All queries come out obfuscated from agent """
        for db_operation, request in self.requests[self.db_service].items():
            span = self._get_sql_span_for_request(request)

            if db_operation in ["insert", "select"]:
                expected_obfuscation_count = 3
            else:
                expected_obfuscation_count = 2

            observed_obfuscation_count = span["meta"]["db.statement"].count("?")
            assert (
                observed_obfuscation_count == expected_obfuscation_count
            ), f"The mssql query is not properly obfuscated for operation {db_operation}, expecting {expected_obfuscation_count} obfuscation(s), found {observed_obfuscation_count}:\n {span['meta']['db.statement']}"

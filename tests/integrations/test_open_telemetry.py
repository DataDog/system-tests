from utils import context, features, interfaces, scenarios, logger
from .utils import BaseDbIntegrationsTestClass

import json


class _BaseOtelDbIntegrationTestClass(BaseDbIntegrationsTestClass):
    """Verify basic DB operations over different databases.
    Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645
    """

    def test_properties(self):
        """Generic check on all operations"""

        db_container = context.get_container_by_dd_integration_name(self.db_service)

        for db_operation, request in self.get_requests():
            logger.info(f"Validating {self.db_service}/{db_operation}")

            span, span_format = self.get_span_from_agent(request)

            assert span is not None, f"Span is not found for {db_operation}"

            # DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name.
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            assert span_meta["db.name"] == db_container.db_instance

            # Describes the relationship between the Span, its parents, and its children in a Trace.
            assert interfaces.agent.get_span_kind(span, span_format) in ("client", "SPAN_KIND_CLIENT")

            # An identifier for the database management system (DBMS) product being used. Formerly db.type
            # Must be one of the available values:
            # https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system
            assert span_meta["db.system"] == self.db_service

            # Username for accessing the database.
            assert span_meta["db.user"].casefold() == db_container.db_user.casefold()

            # The database password should not show in the traces
            for key in span_meta:
                if key not in [
                    "peer.hostname",
                    "db.user",
                    "env",
                    "db.instance",
                    "out.host",
                    "db.name",
                    "peer.service",
                    "net.peer.name",
                    "server.address",
                ]:  # These fields hostname, user... are the same as password
                    assert span_meta[key] != db_container.db_password, f"Test is failing for {db_operation}"

    def test_resource(self):
        """Usually the query"""
        for db_operation, request in self.get_requests(excluded_operations=["procedure", "select_error"]):
            span, span_format = self.get_span_from_agent(request)
            assert db_operation in interfaces.agent.get_span_resource(span, span_format).lower()

    def test_db_connection_string(self):
        """The connection string used to connect to the database."""
        for db_operation, request in self.get_requests():
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            assert span_meta["db.connection_string"].strip(), f"Test is failing for {db_operation}"

    def test_db_operation(self):
        """The name of the operation being executed"""
        for db_operation, request in self.get_requests(excluded_operations=["select_error"]):
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)

            if db_operation == "procedure":
                assert any(substring in span_meta["db.operation"].lower() for substring in ["call", "exec"]), (
                    "db.operation span not found for procedure operation"
                )
            else:
                assert db_operation.lower() in span_meta["db.operation"].lower(), f"Test is failing for {db_operation}"

    def test_db_sql_table(self):
        """The name of the primary table that the operation is acting upon, including the database name (if applicable)."""
        for db_operation, request in self.get_requests(excluded_operations=["procedure"]):
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            assert span_meta["db.sql.table"].strip(), f"Test is failing for {db_operation}"

    def test_error_message(self):
        """A string representing the error message."""
        span, span_format = self.get_span_from_agent(self.requests[self.db_service]["select_error"])
        span_meta = interfaces.agent.get_span_meta(span, span_format)
        assert len(span_meta["error.msg"].strip()) != 0

    def test_error_type_and_stack(self):
        span, span_format = self.get_span_from_agent(self.requests[self.db_service]["select_error"])
        span_meta = interfaces.agent.get_span_meta(span, span_format)

        # A string representing the type of the error
        assert span_meta["error.type"].strip()

        # A human readable version of the stack trace
        assert span_meta["error.stack"].strip()

    def test_error_exception_event(self):
        """New version of test_error_type_and_stack() starting agent@7.75.0"""

        span, span_format = self.get_span_from_agent(self.requests[self.db_service]["select_error"])
        span_meta = interfaces.agent.get_span_meta(span, span_format)
        events = json.loads(span_meta["events"])
        exception_events = [event for event in events if event["name"] == "exception"]
        assert len(exception_events) > 0
        for event in exception_events:
            assert event["attributes"]["exception.type"].strip()
            assert event["attributes"]["exception.message"].strip()
            assert event["attributes"]["exception.stacktrace"].strip()

    def test_obfuscate_query(self):
        """All queries come out obfuscated from agent"""
        for db_operation, request in self.get_requests():
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            if db_operation in ["update", "delete", "procedure", "select_error", "select"]:
                assert span_meta["db.statement"].count("?") == 2, (
                    f"The query is not properly obfuscated for operation {db_operation}"
                )
            else:
                assert span_meta["db.statement"].count("?") == 3, (
                    f"The query is not properly obfuscated for operation {db_operation}"
                )

    def test_sql_success(self):
        """We check all sql launched for the app work"""
        for _, request in self.get_requests(excluded_operations=["select_error"]):
            span, _ = self.get_span_from_agent(request)
            assert "error" not in span or span["error"] == 0

    def test_db_statement_query(self):
        """Usually the query"""
        for db_operation, request in self.get_requests(excluded_operations=["procedure", "select_error"]):
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            assert db_operation in span_meta["db.statement"].lower(), (
                f"{db_operation}  not found in {span_meta['db.statement']}"
            )


@features.otel_postgres_support
@scenarios.otel_integrations
class Test_Postgres(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/Postgres integration"""

    db_service = "postgresql"


@features.otel_mysql_support
@scenarios.otel_integrations
class Test_MySql(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/MySql integration"""

    db_service = "mysql"

    def test_properties(self):
        super().test_properties()


@features.otel_mssql_support
@scenarios.otel_integrations
class Test_MsSql(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/MsSql integration"""

    db_service = "mssql"

    def test_db_mssql_instance_name(self):
        """The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance.
        This value should be set only if it's specified on the mssql connection string.
        """
        for db_operation, request in self.get_requests():
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            assert span_meta["db.mssql.instance_name"].strip(), (
                f"db.mssql.instance_name must not be empty for operation {db_operation}"
            )

    def test_db_operation(self):
        """The name of the operation being executed. Mssql and Open Telemetry doesn't report this span when we call to procedure"""
        for db_operation, request in self.get_requests(excluded_operations=["select_error", "procedure"]):
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)
            # db.operation span is not generating by Open Telemetry when we call to procedure or we have a syntax error on the SQL
            if db_operation not in ["select_error", "procedure"]:
                assert db_operation.lower() in span_meta["db.operation"].lower(), f"Test is failing for {db_operation}"

    def test_resource(self):
        super().test_resource()

    def test_db_connection_string(self):
        super().test_db_connection_string()

    def test_obfuscate_query(self):
        """All queries come out obfuscated from agent"""
        for db_operation, request in self.get_requests():
            span, span_format = self.get_span_from_agent(request)
            span_meta = interfaces.agent.get_span_meta(span, span_format)

            if db_operation in ["insert", "select"]:
                expected_obfuscation_count = 3
            else:
                expected_obfuscation_count = 2

            # Fix for Java otel 2.2.0
            if db_operation == "select" and context.library == "java_otel":
                expected_obfuscation_count = 2

            observed_obfuscation_count = span_meta["db.statement"].count("?")
            assert observed_obfuscation_count == expected_obfuscation_count, (
                f"The mssql query is not properly obfuscated for operation {db_operation}, expecting {expected_obfuscation_count} obfuscation(s), found {observed_obfuscation_count}:\n {span_meta['db.statement']}"
            )

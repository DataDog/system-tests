from utils import context, bug, features, irrelevant, missing_feature, scenarios, logger
from .utils import BaseDbIntegrationsTestClass


class _BaseOtelDbIntegrationTestClass(BaseDbIntegrationsTestClass):
    """Verify basic DB operations over different databases.
    Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645
    """

    def test_properties(self):
        """Generic check on all operations"""

        db_container = context.get_container_by_dd_integration_name(self.db_service)

        for db_operation, request in self.get_requests():
            logger.info(f"Validating {self.db_service}/{db_operation}")

            span = self.get_span_from_agent(request)

            assert span is not None, f"Span is not found for {db_operation}"

            # DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name.
            assert span["meta"]["db.name"] == db_container.db_instance

            # Describes the relationship between the Span, its parents, and its children in a Trace.
            assert span["meta"]["span.kind"] == "client"

            # An identifier for the database management system (DBMS) product being used. Formerly db.type
            # Must be one of the available values:
            # https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system
            assert span["meta"]["db.system"] == self.db_service

            # Username for accessing the database.
            assert span["meta"]["db.user"].casefold() == db_container.db_user.casefold()

            # The database password should not show in the traces
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
                    "server.address",
                ]:  # These fields hostname, user... are the same as password
                    assert span["meta"][key] != db_container.db_password, f"Test is failing for {db_operation}"

    def test_resource(self):
        """Usually the query"""
        for db_operation, request in self.get_requests(excluded_operations=["procedure", "select_error"]):
            span = self.get_span_from_agent(request)
            assert db_operation in span["resource"].lower()

    @missing_feature(library="python_otel", reason="Open telemetry doesn't send this span for python")
    def test_db_connection_string(self):
        """The connection string used to connect to the database."""
        for db_operation, request in self.get_requests():
            span = self.get_span_from_agent(request)
            assert span["meta"]["db.connection_string"].strip(), f"Test is failing for {db_operation}"

    @missing_feature(library="python_otel", reason="Open Telemetry doesn't send this span for python but it should do")
    @missing_feature(library="nodejs_otel", reason="Open Telemetry doesn't send this span for nodejs but it should do")
    def test_db_operation(self):
        """The name of the operation being executed"""
        for db_operation, request in self.get_requests(excluded_operations=["select_error"]):
            span = self.get_span_from_agent(request)

            if db_operation == "procedure":
                assert any(
                    substring in span["meta"]["db.operation"].lower() for substring in ["call", "exec"]
                ), "db.operation span not found for procedure operation"
            else:
                assert (
                    db_operation.lower() in span["meta"]["db.operation"].lower()
                ), f"Test is failing for {db_operation}"

    @missing_feature(
        context.library in ("python_otel", "nodejs_otel"),
        reason="Open Telemetry doesn't send this span for python. But according to the OTEL specification it would be recommended ",
    )
    def test_db_sql_table(self):
        """The name of the primary table that the operation is acting upon, including the database name (if applicable)."""
        for db_operation, request in self.get_requests(excluded_operations=["procedure"]):
            span = self.get_span_from_agent(request)
            assert span["meta"]["db.sql.table"].strip(), f"Test is failing for {db_operation}"

    def test_error_message(self):
        """A string representing the error message."""
        span = self.get_span_from_agent(self.requests[self.db_service]["select_error"])
        assert len(span["meta"]["error.msg"].strip()) != 0

    @missing_feature(library="nodejs_otel", reason="Open telemetry with nodejs is not generating this information.")
    def test_error_type_and_stack(self):
        span = self.get_span_from_agent(self.requests[self.db_service]["select_error"])

        # A string representing the type of the error
        assert span["meta"]["error.type"].strip()

        # A human readable version of the stack trace
        assert span["meta"]["error.stack"].strip()

    @bug(library="python_otel", reason="OTEL-940")
    @bug(library="nodejs_otel", reason="OTEL-940")
    def test_obfuscate_query(self):
        """All queries come out obfuscated from agent"""
        for db_operation, request in self.get_requests():
            span = self.get_span_from_agent(request)
            if db_operation in ["update", "delete", "procedure", "select_error", "select"]:
                assert (
                    span["meta"]["db.statement"].count("?") == 2
                ), f"The query is not properly obfuscated for operation {db_operation}"
            else:
                assert (
                    span["meta"]["db.statement"].count("?") == 3
                ), f"The query is not properly obfuscated for operation {db_operation}"

    def test_sql_success(self):
        """We check all sql launched for the app work"""
        for _, request in self.get_requests(excluded_operations=["select_error"]):
            span = self.get_span_from_agent(request)
            assert "error" not in span or span["error"] == 0

    def test_db_statement_query(self):
        """Usually the query"""
        for db_operation, request in self.get_requests(excluded_operations=["procedure", "select_error"]):
            span = self.get_span_from_agent(request)
            assert (
                db_operation in span["meta"]["db.statement"].lower()
            ), f"{db_operation}  not found in {span['meta']['db.statement']}"


@features.otel_postgres_support
@scenarios.otel_integrations
class Test_Postgres(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/Postgres integration"""

    db_service = "postgresql"

    @bug(library="java_otel", reason="OTEL-2778")
    def test_obfuscate_query(self):
        super().test_obfuscate_query()


@features.otel_mysql_support
@scenarios.otel_integrations
class Test_MySql(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/MySql integration"""

    db_service = "mysql"

    @bug(library="java_otel", reason="OTEL-2778")
    def test_obfuscate_query(self):
        super().test_obfuscate_query()

    @bug(library="java_otel", reason="OTEL-2778")
    def test_properties(self):
        super().test_properties()


@features.otel_mssql_support
@scenarios.otel_integrations
class Test_MsSql(_BaseOtelDbIntegrationTestClass):
    """OpenTelemetry/MsSql integration"""

    db_service = "mssql"

    @irrelevant(
        context.library in ("java_otel", "nodejs_otel"),
        reason="Open Telemetry doesn't generate this span. It's recomended but not mandatory",
    )
    def test_db_mssql_instance_name(self):
        """The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance.
        This value should be set only if it's specified on the mssql connection string.
        """
        for db_operation, request in self.get_requests():
            span = self.get_span_from_agent(request)
            assert span["meta"][
                "db.mssql.instance_name"
            ].strip(), f"db.mssql.instance_name must not be empty for operation {db_operation}"

    @missing_feature(library="nodejs_otel", reason="We are not generating this span")
    def test_db_operation(self):
        """The name of the operation being executed. Mssql and Open Telemetry doesn't report this span when we call to procedure"""
        for db_operation, request in self.get_requests(excluded_operations=["select_error", "procedure"]):
            span = self.get_span_from_agent(request)
            # db.operation span is not generating by Open Telemetry when we call to procedure or we have a syntax error on the SQL
            if db_operation not in ["select_error", "procedure"]:
                assert (
                    db_operation.lower() in span["meta"]["db.operation"].lower()
                ), f"Test is failing for {db_operation}"

    @missing_feature(
        library="nodejs_otel",
        reason="Resource span is not generating correctly. We find resource value: execsql master",
    )
    def test_resource(self):
        super().test_resource()

    @irrelevant(
        library="nodejs_otel",
        reason="Open telemetry doesn't send this span for nodejs and mssql. It's recomended but not mandatory",
    )
    def test_db_connection_string(self):
        super().test_db_connection_string()

    @bug(library="nodejs_otel", reason="OTEL-940")
    @bug(library="java_otel", reason="OTEL-2778")
    def test_obfuscate_query(self):
        """All queries come out obfuscated from agent"""
        for db_operation, request in self.get_requests():
            span = self.get_span_from_agent(request)

            if db_operation in ["insert", "select"]:
                expected_obfuscation_count = 3
            else:
                expected_obfuscation_count = 2

            # Fix for Java otel 2.2.0
            if db_operation == "select" and context.library == "java_otel":
                expected_obfuscation_count = 2

            observed_obfuscation_count = span["meta"]["db.statement"].count("?")
            assert (
                observed_obfuscation_count == expected_obfuscation_count
            ), f"The mssql query is not properly obfuscated for operation {db_operation}, expecting {expected_obfuscation_count} obfuscation(s), found {observed_obfuscation_count}:\n {span['meta']['db.statement']}"

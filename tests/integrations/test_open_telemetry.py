import pytest
from utils.tools import logger
from .sql_utils import BaseDbIntegrationsTestClass
from utils import weblog, interfaces
from utils import (
    context,
    sql_bug,
    missing_sql_feature,
    sql_irrelevant,
    manage_sql_decorators,
    bug,
    missing_feature,
    irrelevant,
    scenarios,
    flaky,
)

testdata_cache = {}

# Define the data for test case generation
otel_sql_operations = ["select", "insert", "update", "delete", "procedure", "select_error"]
otel_sql_services = ["mysql", "postgresql", "mssql"]


def pytest_generate_tests(metafunc):
    """ Generate parametrized tests for given sql_operations (basic sql operations; ie select,insert...) over sql_services (db services ie mysql,mssql...)"""

    if (
        "otel_sql_service"
        and "otel_sql_operation" in metafunc.fixturenames
        and context.scenario == scenarios.otel_integrations
    ):
        class_name = metafunc.cls.__name__.split("_")[1]
        if class_name not in testdata_cache:
            test_parameters = []
            test_ids = []
            for test_sql_service in otel_sql_services:
                weblog.get("/db", params={"service": test_sql_service, "operation": "init"}, timeout=20)

                for test_sql_operation in otel_sql_operations:
                    weblog_request = weblog.get(
                        "/db", params={"service": test_sql_service, "operation": test_sql_operation}
                    )
                    test_parameters.append((test_sql_service, test_sql_operation, weblog_request))
                    test_ids.append("db:" + test_sql_service + ",op:" + test_sql_operation)
            testdata_cache[class_name] = test_parameters
            testdata_cache[class_name + ".id"] = test_ids

        metafunc.parametrize(
            "otel_sql_service,otel_sql_operation,weblog_request",
            testdata_cache[class_name],
            ids=testdata_cache[class_name + ".id"],
        )


@scenarios.otel_integrations
class Test_OtelDbIntegrationTestClass(BaseDbIntegrationsTestClass):

    """ Verify basic DB operations over different databases.
        Check integration spans status: https://docs.google.com/spreadsheets/d/1qm3B0tJ-gG11j_MHoEd9iMXf4_DvWAGCLwmBhWCxbA8/edit#gid=623219645 """

    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_properties(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ generic check on all operations """

        db_container = context.scenario.get_container_by_dd_integration_name(otel_sql_service)

        span = self.get_span_from_agent(weblog_request)

        assert span is not None, f"Span is not found for {otel_sql_operation}"

        # DEPRECATED!! Now it is db.instance. The name of the database being connected to. Database instance name.
        assert span["meta"]["db.name"] == db_container.db_instance

        # Describes the relationship between the Span, its parents, and its children in a Trace.
        assert span["meta"]["span.kind"] == "client"

        # An identifier for the database management system (DBMS) product being used. Formerly db.type
        # Must be one of the available values:
        # https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2357395856/Span+attributes#db.system
        assert span["meta"]["db.system"] == otel_sql_service

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
            ]:  # These fields hostname, user... are the same as password
                assert span["meta"][key] != db_container.db_password, f"Test is failing for {otel_sql_operation}"

    @bug(
        library="nodejs_otel",
        reason="Resource span is not generating correctly. We find resource value: execsql master",
    )
    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation in ["procedure", "select_error"])
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_resource(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ Usually the query """
        span = self.get_span_from_agent(weblog_request)
        assert otel_sql_operation in span["resource"].lower()

    @missing_feature(library="python_otel", reason="Open telemetry doesn't send this span for python")
    @sql_irrelevant(
        library="nodejs_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Open telemetry doesn't send this span for nodejs and mssql. It's recomended but not mandatory",
    )
    def test_db_connection_string(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ The connection string used to connect to the database. """
        span = self.get_span_from_agent(weblog_request)
        assert span["meta"]["db.connection_string"].strip()

    @bug(library="python_otel", reason="Open Telemetry doesn't send this span for python but it should do")
    @bug(library="nodejs_otel", reason="Open Telemetry doesn't send this span for nodejs but it should do")
    @sql_bug(
        library="java_otel",
        condition=lambda otel_sql_operation, otel_sql_service: otel_sql_service == "mssql"
        and otel_sql_operation == "procedure",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation == "select_error")
    @sql_bug(
        library="nodejs_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="We are not generating this span",
    )
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_db_operation(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ The name of the operation being executed """
        span = self.get_span_from_agent(weblog_request)

        if otel_sql_operation == "procedure":
            assert any(
                substring in span["meta"]["db.operation"].lower() for substring in ["call", "exec"]
            ), "db.operation span not found for procedure operation"
        else:
            assert (
                otel_sql_operation.lower() in span["meta"]["db.operation"].lower()
            ), f"Test is failing for {otel_sql_operation}"

    @missing_feature(
        context.library in ("python_otel", "nodejs_otel"),
        reason="Open Telemetry doesn't send this span for python. But according to the OTEL specification it would be recommended ",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation == "procedure")
    def test_db_sql_table(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ The name of the primary table that the operation is acting upon, including the database name (if applicable). """
        span = self.get_span_from_agent(weblog_request)
        assert span["meta"]["db.sql.table"].strip()

    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation != "select_error")
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_error_message(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ A string representing the error message. """
        span = self.get_span_from_agent(weblog_request)
        assert len(span["meta"]["error.msg"].strip()) != 0

    @missing_feature(library="nodejs_otel", reason="Open telemetry with nodejs is not generating this information.")
    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation != "select_error")
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_error_type_and_stack(self, otel_sql_service, otel_sql_operation, weblog_request):
        span = self.get_span_from_agent(weblog_request)

        # A string representing the type of the error
        assert span["meta"]["error.type"].strip()

        # A human readable version of the stack trace
        assert span["meta"]["error.stack"].strip()

    @bug(library="python_otel", reason="https://datadoghq.atlassian.net/browse/OTEL-940")
    @bug(library="nodejs_otel", reason="https://datadoghq.atlassian.net/browse/OTEL-940")
    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_obfuscate_query(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ All queries come out obfuscated from agent """
        span = self.get_span_from_agent(weblog_request)

        if otel_sql_operation in ["update", "delete", "procedure", "select_error"]:
            assert (
                span["meta"]["db.statement"].count("?") == 2
            ), f"The query is not properly obfuscated for operation {otel_sql_operation}"
        else:
            assert (
                span["meta"]["db.statement"].count("?") == 3
            ), f"The query is not properly obfuscated for operation {otel_sql_operation}"

    @irrelevant(context.library != "nodejs_otel")
    @sql_bug(
        library="nodejs_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="https://datadoghq.atlassian.net/browse/OTEL-940",
    )
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_obfuscate_query_nodejs(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ All queries come out obfuscated from agent """
        span = self.get_span_from_agent(weblog_request)

        if otel_sql_operation in ["insert", "select"]:
            expected_obfuscation_count = 3
        else:
            expected_obfuscation_count = 2

        observed_obfuscation_count = span["meta"]["db.statement"].count("?")
        assert (
            observed_obfuscation_count == expected_obfuscation_count
        ), f"The query is not properly obfuscated for operation {otel_sql_operation}, expecting {expected_obfuscation_count} obfuscation(s), found {observed_obfuscation_count}:\n {span['meta']['db.statement']}"

    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation == "select_error")
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_sql_success(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ We check all sql launched for the app work """
        span = self.get_span_from_agent(weblog_request)
        assert "error" not in span or span["error"] == 0

    @missing_sql_feature(
        library="python_otel",
        condition=lambda otel_sql_service: otel_sql_service == "mssql",
        reason="Python OpenTel doesn't support mssql",
    )
    @sql_irrelevant(condition=lambda otel_sql_operation: otel_sql_operation in ["select_error", "procedure"])
    @pytest.mark.usefixtures("manage_sql_decorators")
    def test_db_statement_query(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ Usually the query """
        span = self.get_span_from_agent(weblog_request)
        assert (
            otel_sql_operation in span["meta"]["db.statement"].lower()
        ), f"{otel_sql_operation}  not found in {span['meta']['db.statement']}"

    @irrelevant(
        context.library in ("java_otel", "nodejs_otel", "python_otel"),
        reason="Open Telemetry doesn't generate this span. It's recomended but not mandatory",
    )
    def test_db_mssql_instance_name(self, otel_sql_service, otel_sql_operation, weblog_request):
        """ The Microsoft SQL Server instance name connecting to. This name is used to determine the port of a named instance. 
            This value should be set only if it’s specified on the mssql connection string. """

        span = self.get_span_from_agent(weblog_request)
        assert span["meta"]["db.mssql.instance_name"].strip()

from utils import scenario_groups, features, context, interfaces, scenarios


from .utils.schemas_validators import SchemaBug, assert_no_schema_error


@features.not_reported
@scenario_groups.end_to_end
class Test_DdtraceSchemas:
    def test_library(self):
        known_bugs = [
            SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content[]",
                condition=context.library >= "php@1.12.0",
                ticket="DEBUG-4431",
            ),
            SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$",
                condition=context.library > "nodejs@5.36.0",
                ticket="DEBUG-3487",
            ),
            SchemaBug(
                endpoint="/v0.4/traces", data_path="$", condition=context.library == "java", ticket="APMAPI-1161"
            ),
            SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload.configuration[]",
                condition=context.library >= "nodejs@2.27.1",
                ticket="APPSEC-52805",
            ),
            SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library < "python@v2.9.0.dev",
                ticket="APPSEC-52845",
            ),
            SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload.configuration[].value",
                condition=context.library == "golang",
                ticket="APMS-12697",
            ),
            SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content",
                condition=context.library < "nodejs@5.31.0",
                ticket="DEBUG-2864",
            ),
            SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content[].debugger.diagnostics",
                condition=context.library == "nodejs",
                ticket="DEBUG-3245",
            ),
            SchemaBug(
                endpoint="/debugger/v1/input",
                data_path="$[].debugger.snapshot.stack[].lineNumber",
                condition=context.library in ("python@2.16.2", "python@2.16.3")
                and context.scenario is scenarios.debugger_expression_language,
                ticket="APMRP-360",
            ),
            SchemaBug(
                endpoint="/debugger/v1/input",
                data_path="$[].debugger.snapshot.probe.location.method",
                condition=context.library == "dotnet",
                ticket="DEBUG-3734",
            ),
            SchemaBug(
                endpoint="/symdb/v1/input",
                data_path=None,
                condition=context.library == "dotnet" and context.scenario is scenarios.debugger_symdb,
                ticket="DEBUG-3298",
            ),
            SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library > "php@1.7.3",
                ticket="APMAPI-1270",
            ),
            SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[]",
                condition=context.library >= "php@1.8.3",
                ticket="DEBUG-3709",
            ),
            SchemaBug(
                endpoint="/v0.6/stats",
                data_path=None,
                condition=context.library
                in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "java", "nodejs", "php", "python", "ruby")
                and context.scenario
                in (
                    scenarios.appsec_blocking,
                    scenarios.trace_stats_computation,
                    scenarios.tracing_config_nondefault_3,
                ),
                ticket="APMSP-2158",
            ),
            SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library >= "python@4.3.0-rc1" and context.scenario is scenarios.profiling,
                ticket="APMSP-2590",
            ),
        ]

        assert_no_schema_error(interfaces.library, known_bugs)

    def test_agent(self):
        known_bugs = [
            SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$",
                condition=context.library > "nodejs@5.36.0",
                ticket="DEBUG-3487",
            ),
            SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload.configuration[]",
                condition=context.library >= "nodejs@2.27.1"
                or context.scenario in (scenarios.crossed_tracing_libraries, scenarios.graphql_appsec),
                ticket="APPSEC-52805",
            ),
            SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library < "python@v2.9.0.dev",
                ticket="APPSEC-52845",
            ),
            SchemaBug(
                endpoint="/api/v2/apmtelemetry", data_path="$", condition=True, ticket="???"
            ),  # the main payload sent by the agent may be an array i/o an object
            SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload.configuration[].value",
                condition=context.library == "golang",
                ticket="APMS-12697",
            ),
            SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[].content",
                condition=context.library < "nodejs@5.31.0",
                ticket="DEBUG-2864",
            ),
            SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[]",
                condition=context.library == "dotnet" and context.scenario is scenarios.debugger_symdb,
                ticket="DEBUG-3298",
            ),
            SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library > "php@1.7.3",
                ticket="XXX-1234",
            ),
            SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[]",
                condition=context.library >= "php@1.8.3",
                ticket="DEBUG-3709",
            ),
            SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=context.library >= "python@4.3.0-rc1" and context.scenario is scenarios.profiling,
                ticket="APMSP-2590",
            ),
        ]

        assert_no_schema_error(interfaces.agent, known_bugs)


@features.not_reported
@scenarios.otel_collector
@scenarios.otel_collector_e2e
class Test_OtelSchemas:
    def test_main(self):
        assert_no_schema_error(interfaces.otel_collector, [])

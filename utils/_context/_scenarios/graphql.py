from ._core import EndToEndScenario, scenario_groups, ScenarioGroup
from utils._context.constants import WeblogCategory


class _GraphQlEndToEndScenario(EndToEndScenario):
    """Scenario targeting GraphQl feature of a dd-trace library"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        agent_env: dict[str, str | None] | None = None,
        scenario_groups: list[ScenarioGroup] | None = None,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict | None = None,
    ) -> None:
        super().__init__(
            name,
            agent_env=agent_env,
            doc=doc,
            scenario_groups=scenario_groups,
            weblog_categories=[WeblogCategory.dd_trace_graphql],
            weblog_env=weblog_env,
            weblog_volumes=weblog_volumes,
        )


# This GraphQL scenario can be used for any GraphQL testing, not just AppSec
class GraphqlAppsec(_GraphQlEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "GRAPHQL_APPSEC",
            weblog_env={
                "DD_APPSEC_RULES": "/appsec_blocking_rule.json",
                "DD_TRACE_GRAPHQL_ERROR_EXTENSIONS": "int,float,str,bool,other",
            },
            weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
            doc="AppSec tests for GraphQL integrations",
            scenario_groups=[scenario_groups.appsec, scenario_groups.graphql],
        )


# This GraphQL scenario can be used for any GraphQL testing, not just AppSec
class GraphqlErrorTracking(_GraphQlEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "GRAPHQL_ERROR_TRACKING",
            weblog_env={
                "DD_TRACE_GRAPHQL_ERROR_EXTENSIONS": "int,float,str,bool,other",
                "DD_TRACE_GRAPHQL_ERROR_TRACKING": "true",
            },
            weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
            doc="GraphQL error tracking tests with OpenTelemetry semantics",
            scenario_groups=[scenario_groups.appsec, scenario_groups.graphql],
        )

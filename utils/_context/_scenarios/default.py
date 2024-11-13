from .core import ScenarioGroup
from .endtoend import EndToEndScenario


class DefaultScenario(EndToEndScenario):
    def __init__(self, name: str):
        super().__init__(
            name,
            weblog_env={
                "DD_DBM_PROPAGATION_MODE": "service",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
                "DD_TRACE_FEATURES": "discovery",
                "DD_TRACE_COMPUTE_STATS": "true",
                "SOME_SECRET_ENV": "leaked-env-var",  # used for test that env var are not leaked
            },
            agent_env={"SOME_SECRET_ENV": "leaked-env-var"},
            include_postgres_db=True,
            doc="Default scenario, spawn tracer, the Postgres databases and agent, and run most of exisiting tests",
        )

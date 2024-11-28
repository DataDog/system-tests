from .core import ScenarioGroup
from .endtoend import EndToEndScenario


# TODO : short explaination of the purpose of this value
# a link to the RFC would be perfect
_iast_security_controls_map = {
    "cpp": "TODO",
    "dotnet": "TODO",
    "golang": "TODO",
    "java": "SANITIZER:XSS:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:sanitize;SANITIZER:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:sanitizeForAllVulns;SANITIZER:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:overloadedSanitize:java.lang.String;INPUT_VALIDATOR:XSS:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:validate;INPUT_VALIDATOR:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:validateForAllVulns;INPUT_VALIDATOR:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:overloadedValidation:java.lang.Object,java.lang.String,java.lang.String:1,2",
    "nodejs": "TODO",
    "php": "TODO",
    "python": "TODO",
    "ruby": "TODO",
}


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
            scenario_groups=[ScenarioGroup.ESSENTIALS],
            doc="Default scenario, spawn tracer, the Postgres databases and agent, and run most of exisiting tests",
        )

    def configure(self, config):
        super().configure(config)

        self.weblog_container.environment["DD_IAST_SECURITY_CONTROLS_CONFIGURATION"] = _iast_security_controls_map[
            self.weblog_container.library.library
        ]

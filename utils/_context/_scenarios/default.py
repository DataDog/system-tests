import pytest
from .core import scenario_groups
from .endtoend import EndToEndScenario


# When Security Controls configuration is set, tracers must instrument all the designated methods in the
# configuration as security controls.
# RFC(https://docs.google.com/document/d/1j1hp87-2wJnXUGADZxzLnvKJmaF_Gd6ZR1hPS3LVguQ/edit?pli=1&tab=t.0)

_iast_security_controls_map = {
    "cpp_nginx": "TODO",
    "cpp_httpd": "TODO",
    "dotnet": "TODO",
    "golang": "TODO",
    "java": (
        "SANITIZER:COMMAND_INJECTION:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:sanitize;"
        "SANITIZER:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:sanitizeForAllVulns;"
        "SANITIZER:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:overloadedSanitize:java.lang.String;"
        "INPUT_VALIDATOR:COMMAND_INJECTION:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:validate;"
        "INPUT_VALIDATOR:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:validateForAllVulns;"
        "INPUT_VALIDATOR:*:com.datadoghq.system_tests.iast.utils.SecurityControlUtil:"
        "overloadedValidation:java.lang.Object,java.lang.String,java.lang.String:1,2"
    ),
    "nodejs": (
        "SANITIZER:COMMAND_INJECTION:iast/utils/securityControlUtil.js:sanitize;"
        "SANITIZER:*:iast/utils/securityControlUtil.js:sanitizeForAllVulns;"
        "SANITIZER:*:iast/utils/securityControlUtil.js:overloadedSanitize:0;"
        "INPUT_VALIDATOR:COMMAND_INJECTION:iast/utils/securityControlUtil.js:validate;"
        "INPUT_VALIDATOR:*:iast/utils/securityControlUtil.js:validateForAllVulns;"
        "INPUT_VALIDATOR:*:iast/utils/securityControlUtil.js:overloadedValidation:1,2;"
        # typescript definitions
        "SANITIZER:COMMAND_INJECTION:dist/utils/securityControlUtil.js:sanitize;"
        "SANITIZER:*:dist/utils/securityControlUtil.js:sanitizeForAllVulns;"
        "SANITIZER:*:dist/utils/securityControlUtil.js:overloadedSanitize:0;"
        "INPUT_VALIDATOR:COMMAND_INJECTION:dist/utils/securityControlUtil.js:validate;"
        "INPUT_VALIDATOR:*:dist/utils/securityControlUtil.js:validateForAllVulns;"
        "INPUT_VALIDATOR:*:dist/utils/securityControlUtil.js:overloadedValidation:1,2"
    ),
    "php": "TODO",
    "python": (
        "SANITIZER:COMMAND_INJECTION:app:_sc_s_validate;"
        "SANITIZER:*:app:_sc_s_validate_for_all;"
        "SANITIZER:*:app:_sc_s_overloaded:0;"
        "INPUT_VALIDATOR:COMMAND_INJECTION:app:_sc_v_validate;"
        "INPUT_VALIDATOR:*:app:_sc_v_validate_for_all;"
        "INPUT_VALIDATOR:*:app:_sc_v_overloaded:1,2"
    ),
    "ruby": "TODO",
}


class DefaultScenario(EndToEndScenario):
    def __init__(self, name: str):
        super().__init__(
            name,
            weblog_env={
                "DD_DBM_PROPAGATION_MODE": "service",
                "SOME_SECRET_ENV": "leaked-env-var",  # used for test that env var are not leaked
                "DD_EXTERNAL_ENV": "it-false,cn-weblog,pu-75a2b6d5-3949-4afb-ad0d-92ff0674e759",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
                # API security should be enabled by default soon
                # though, it conflict with many tests.
                # ideally, we should keep all defaults setting for the default scenario
                # but we need proper investigation to see how to properly tests everything
                # waiting for this audit, we disable API security
                "DD_API_SECURITY_ENABLED": "false",
            },
            agent_env={"SOME_SECRET_ENV": "leaked-env-var"},
            include_postgres_db=True,
            scenario_groups=[scenario_groups.essentials, scenario_groups.telemetry],
            doc="Default scenario, spawn tracer, the Postgres databases and agent, and run most of exisiting tests",
        )

    def configure(self, config: pytest.Config):
        super().configure(config)
        library = self.weblog_container.image.labels["system-tests-library"]
        value = _iast_security_controls_map[library]
        self.weblog_container.environment["DD_IAST_SECURITY_CONTROLS_CONFIGURATION"] = value

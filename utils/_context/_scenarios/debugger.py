from .core import ScenarioGroup
from .endtoend import EndToEndScenario


class DebuggerScenario(EndToEndScenario):
    def __init__(self, name, doc, weblog_env) -> None:
        base_weblog_env = {
            "DD_REMOTE_CONFIG_ENABLED": "1",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "1",
            "DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL": "100",
            "DD_DYNAMIC_INSTRUMENTATION_DIAGNOSTICS_INTERVAL": "1",
        }

        base_weblog_env.update(weblog_env)

        super().__init__(
            name=name,
            doc=doc,
            rc_api_enabled=True,
            library_interface_timeout=5,
            weblog_env=base_weblog_env,
            scenario_groups=[ScenarioGroup.DEBUGGER],
        )

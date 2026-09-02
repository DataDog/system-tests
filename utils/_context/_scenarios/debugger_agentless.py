from .agentless_endtoend import AgentlessEndToEndScenario
from .core import scenario_groups


class DebuggerAgentlessScenario(AgentlessEndToEndScenario):
    """Agentless Dynamic Instrumentation (probes) and Symbol DB, without a Datadog Agent.

    Reuses the same TUF test root/key already trusted by the real Agent
    (`utils._context.containers.AgentContainer`) for the native agentless Remote
    Configuration client, and the same mocked-backend protobuf responses
    (`rc_api_enabled`/`rc_backend_enabled`) already served to the Agent's own RC poller --
    both wired generically in `AgentlessEndToEndScenario` whenever `rc_backend_enabled=True`.
    """

    def __init__(self, name: str, *, doc: str, weblog_env: dict[str, str | None] | None = None) -> None:
        base_weblog_env: dict[str, str | None] = {
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
            "DD_DYNAMIC_INSTRUMENTATION_UPLOAD_INTERVAL_SECONDS": "0.1",
            "DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL": "0.1",
        }
        base_weblog_env.update(weblog_env or {})

        super().__init__(
            name,
            doc=doc,
            rc_api_enabled=True,
            rc_backend_enabled=True,
            library_interface_timeout=5,
            scenario_groups=(scenario_groups.debugger,),
            weblog_env=base_weblog_env,
        )

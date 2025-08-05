import pytest

from .core import scenario_groups
from .endtoend import EndToEndScenario


class DebuggerScenario(EndToEndScenario):
    def __init__(self, name: str, doc: str, weblog_env: dict[str, str | None]) -> None:
        base_weblog_env: dict[str, str | None] = {
            "DD_REMOTE_CONFIG_ENABLED": "1",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "1",
        }

        base_weblog_env.update(weblog_env)

        super().__init__(
            name=name,
            doc=doc,
            rc_api_enabled=True,
            library_interface_timeout=5,
            weblog_env=base_weblog_env,
            scenario_groups=[scenario_groups.debugger],
        )

    def configure(self, config: pytest.Config):
        super().configure(config)

        library = self.weblog_container.image.labels["system-tests-library"]
        if library == "python":
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL"] = "0.1"
        else:
            self.weblog_container.environment["DD_DYNAMIC_INSTRUMENTATION_UPLOAD_FLUSH_INTERVAL"] = "100"
        if library == "golang":
            self.agent_container.privileged = True
            self.agent_container.pid_mode = "host"
            # Set the system-probe to output to the proxy
            self.agent_container.environment["DD_TRACE_AGENT_PORT"] = self.weblog_container.environment[
                "DD_TRACE_AGENT_PORT"
            ]
            self.agent_container.environment["DD_AGENT_HOST"] = self.weblog_container.environment["DD_AGENT_HOST"]
            self.agent_container.volumes["./utils/build/docker/agent/system-probe.yaml"] = {
                "bind": "/etc/datadog-agent/system-probe.yaml",
                "mode": "ro",
            }
            self.agent_container.volumes["/sys/kernel/debug"] = {"bind": "/sys/kernel/debug", "mode": "ro"}
            self.agent_container.volumes["/sys/fs/cgroup"] = {"bind": "/sys/fs/cgroup", "mode": "ro"}

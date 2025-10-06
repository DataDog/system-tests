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
            # The Go debugger is primarily implemented in the system-probe, so
            # make sure to mount the system-probe.yaml file so that the
            # system-probe sub-agent is launched and runs with the correct
            # configuration.
            self.agent_container.volumes["./utils/build/docker/agent/system-probe.yaml"] = {
                "bind": "/etc/datadog-agent/system-probe.yaml",
                "mode": "ro",
            }
            # The system-probe needs to be privileged to be able to attach to
            # the processes and read the memory.
            self.agent_container.privileged = True
            self.agent_container.pid_mode = "host"
            # Additionally, the system-probe needs to be able to access the
            # kernel debug and cgroup filesystems so that it can discover
            # process container information and load bpf programs.
            #
            # Docker for mac magically does the right thing to make this work
            # when run from macOS as well.
            self.agent_container.volumes["/sys/kernel/debug"] = {"bind": "/sys/kernel/debug", "mode": "ro"}
            self.agent_container.volumes["/sys/fs/cgroup"] = {"bind": "/sys/fs/cgroup", "mode": "ro"}
            # Set the system-probe to output to the proxy the same way the
            # libraries are being told to. For golang, the system-probe acts
            # as a tracer library and sends data to the trace-agent just like
            # the other libraries.
            weblog_env = self.weblog_container.environment
            self.agent_container.environment["DD_TRACE_AGENT_PORT"] = weblog_env["DD_TRACE_AGENT_PORT"]
            self.agent_container.environment["DD_AGENT_HOST"] = weblog_env["DD_AGENT_HOST"]

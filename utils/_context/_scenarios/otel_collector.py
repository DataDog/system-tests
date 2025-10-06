import pytest
from utils import interfaces
from utils._context.component_version import ComponentVersion
from utils._context.containers import OpenTelemetryCollectorContainer
from utils.proxy.ports import ProxyPorts

from .core import scenario_groups
from .endtoend import DockerScenario


class OtelCollectorScenario(DockerScenario):
    def __init__(self, name: str):
        super().__init__(
            name,
            github_workflow="endtoend",
            doc="TODO",
            scenario_groups=[scenario_groups.end_to_end],
            include_postgres_db=True,
            use_proxy=True,
        )
        self.library = ComponentVersion("otel_collector", "0.0.0")

        self.collector_container = OpenTelemetryCollectorContainer(
            config_file="./utils/build/docker/otelcol-config-with-postgres.yaml",
            environment={
                "DD_API_KEY": "fake",
                "DD_SITE": "datadoghq.com",
                "HTTP_PROXY": f"http://proxy:{ProxyPorts.otel_collector}",
                "HTTPS_PROXY": f"http://proxy:{ProxyPorts.otel_collector}",
            },
            volumes={
                "./utils/build/docker/agent/ca-certificates.crt": {
                    "bind": "/etc/ssl/certs/ca-certificates.crt",
                    "mode": "ro",
                },
            },
        )
        self._required_containers.append(self.collector_container)

    def configure(self, config: pytest.Config) -> None:
        interfaces.otel_collector.configure(self.host_log_folder, replay=self.replay)

        super().configure(config)

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.otel_collector])

    def get_warmups(self) -> list:
        warmups = super().get_warmups()

        if not self.replay:
            warmups.insert(1, self._start_interfaces_watchdog)

        return warmups

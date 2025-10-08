import pytest
from utils import interfaces
from utils._context.component_version import ComponentVersion
from utils._context.containers import OpenTelemetryCollectorContainer
from utils._logger import logger
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
                "DD_API_KEY": "0123",
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
        super().configure(config)

        interfaces.otel_collector.configure(self.host_log_folder, replay=self.replay)
        self.library = ComponentVersion(
            "otel_collector", self.collector_container.image.labels["org.opencontainers.image.version"]
        )

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.otel_collector])

    def _print_otel_collector_version(self):
        logger.stdout(f"Otel collector: {self.library}")

    def get_warmups(self) -> list:
        warmups = super().get_warmups()

        warmups.append(self._print_otel_collector_version)

        if not self.replay:
            warmups.insert(1, self._start_interfaces_watchdog)

        return warmups

    def post_setup(self, session: pytest.Session):  # noqa: ARG002
        # if no test are run, skip interface timeouts
        # is_empty_test_run = session.config.option.skip_empty_scenario and len(session.items) == 0

        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

    def _wait_and_stop_containers(self):
        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.otel_collector.load_data_from_logs()
        else:
            logger.terminal.write_sep("-", f"Wait for {interfaces.otel_collector} (0s)")
            logger.terminal.flush()

            self.collector_container.stop()
            interfaces.otel_collector.wait(0)

        interfaces.otel_collector.check_deserialization_errors()

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        self.test_schemas(session, interfaces.otel_collector, [])
        super().pytest_sessionfinish(session, exitstatus)

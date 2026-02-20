import os
import pytest
from pathlib import Path

from utils import interfaces
from utils._context.component_version import Version
from utils._context.containers import OpenTelemetryCollectorContainer, PostgresContainer
from utils._logger import logger
from utils.proxy.ports import ProxyPorts

from .core import scenario_groups
from .endtoend import DockerScenario


class OtelCollectorScenario(DockerScenario):
    otel_collector_version: Version
    postgres_container: PostgresContainer

    def __init__(self, name: str, *, use_proxy: bool = True, mocked_backend: bool = True):
        super().__init__(
            name,
            github_workflow="endtoend",
            doc="TODO",
            scenario_groups=[scenario_groups.end_to_end, scenario_groups.all],
            use_proxy=use_proxy,
            mocked_backend=mocked_backend,
        )

        self.postgres_container = PostgresContainer()
        self._containers.append(self.postgres_container)

        self.collector_container = OpenTelemetryCollectorContainer(
            config_file="./utils/build/docker/e2eotel/otelcol-config.yml",
            environment={
                "DD_API_KEY": "0123",
                "DD_SITE": os.environ.get("DD_SITE", "datad0g.com"),
                "HTTP_PROXY": f"http://proxy:{ProxyPorts.otel_collector}",
                "HTTPS_PROXY": f"http://proxy:{ProxyPorts.otel_collector}",
            },
            volumes={
                "./utils/build/docker/agent/ca-certificates.crt": {
                    "bind": "/etc/ssl/certs/ca-certificates.crt",
                    "mode": "ro",
                },
                "./utils/build/docker/e2eotel/": {
                    "bind": "/etc/config/",
                    "mode": "ro",
                },
            },
        )
        self._containers.append(self.collector_container)

    def configure(self, config: pytest.Config) -> None:
        super().configure(config)

        self.collector_container.depends_on.append(self.postgres_container)

        if not self.proxy_container.mocked_backend:
            interfaces.backend.configure(self.host_log_folder, replay=self.replay)

            if "DD_API_KEY" not in os.environ:
                pytest.exit(f"{self.name} scenario requires a valid DD_API_KEY")

            self.collector_container.environment["DD_API_KEY"] = os.environ["DD_API_KEY"]

        postgres_image = self.postgres_container.image.name
        image_parts = postgres_image.split(":")
        docker_image_name = image_parts[0] if len(image_parts) > 0 else "unknown"
        docker_image_tag = image_parts[1] if len(image_parts) > 1 else "unknown"

        self.collector_container.environment["DOCKER_IMAGE_NAME"] = docker_image_name
        self.collector_container.environment["DOCKER_IMAGE_TAG"] = docker_image_tag

        interfaces.otel_collector.configure(self.host_log_folder, replay=self.replay)
        self.otel_collector_version = Version(self.collector_container.image.labels["org.opencontainers.image.version"])

        self.components["otel_collector"] = self.otel_collector_version
        # Extract version from image name
        image_name = self.postgres_container.image.name
        postgres_version = image_name.split(":", 1)[1] if ":" in image_name else "unknown"
        self.components["postgresql"] = postgres_version

        self.warmups.append(self._print_otel_collector_version)

        if not self.replay:
            self.warmups.insert(1, self._start_interfaces_watchdog)

    def customize_feature_parity_dashboard(self, result: dict) -> None:
        result["configuration"]["collector_version"] = str(self.otel_collector_version)
        result["configuration"]["collector_image"] = self.collector_container.image.name

        # Extract image commit/revision if available from labels
        if self.collector_container.image.labels:
            image_labels = self.collector_container.image.labels
            if "org.opencontainers.image.revision" in image_labels:
                result["configuration"]["collector_image_commit"] = image_labels["org.opencontainers.image.revision"]

        # Parse OTel collector configuration file
        config_file_path = Path(self.collector_container.config_file)
        result["configuration"]["config_file"] = config_file_path.name

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.otel_collector])

    def _print_otel_collector_version(self):
        logger.stdout(f"Otel collector: {self.otel_collector_version}")

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
            logger.terminal.write_sep("-", f"Wait for {interfaces.otel_collector} (20s)")
            logger.terminal.flush()

            interfaces.otel_collector.wait(20)
            self.collector_container.stop()

        interfaces.otel_collector.check_deserialization_errors()

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        self.test_schemas(session, interfaces.otel_collector, [])
        super().pytest_sessionfinish(session, exitstatus)

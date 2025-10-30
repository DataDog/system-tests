import os
import pytest
import yaml
from pathlib import Path

from utils import interfaces
from utils._context.component_version import ComponentVersion
from utils._context.containers import OpenTelemetryCollectorContainer
from utils._logger import logger
from utils.proxy.ports import ProxyPorts

from .core import scenario_groups
from .endtoend import DockerScenario


class OtelCollectorScenario(DockerScenario):
    def __init__(self, name: str, *, use_proxy: bool = True, mocked_backend: bool = True):
        super().__init__(
            name,
            github_workflow="endtoend",
            doc="TODO",
            scenario_groups=[scenario_groups.end_to_end],
            include_postgres_db=True,
            use_proxy=use_proxy,
            mocked_backend=mocked_backend,
        )
        self.library = ComponentVersion("otel_collector", "0.0.0")

        self.collector_container = OpenTelemetryCollectorContainer(
            config_file="./utils/build/docker/otelcol-config-with-postgres.yaml",
            environment={
                "DD_API_KEY": "0123",
                "DD_SITE": os.environ.get("DD_SITE", "datadoghq.com"),
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
        self.library = ComponentVersion(
            "otel_collector", self.collector_container.image.labels["org.opencontainers.image.version"]
        )

    def customize_feature_parity_dashboard(self, result: dict) -> None:
        result["configuration"]["collector_version"] = str(self.library.version)
        result["configuration"]["collector_image"] = self.collector_container.image.name

        # Extract image commit/revision if available from labels
        if self.collector_container.image.labels:
            image_labels = self.collector_container.image.labels
            if "org.opencontainers.image.revision" in image_labels:
                result["configuration"]["collector_image_commit"] = image_labels["org.opencontainers.image.revision"]

        # Parse OTel collector configuration file
        config_file_path = Path(self.collector_container.config_file)
        result["configuration"]["config_file"] = config_file_path.name

        try:
            with open(config_file_path, "r", encoding="utf-8") as f:
                otel_config = yaml.safe_load(f)

            if "receivers" in otel_config:
                result["configuration"]["receivers"] = list(otel_config["receivers"].keys())
                if "postgresql" in otel_config["receivers"]:
                    pg_config = otel_config["receivers"]["postgresql"]
                    result["configuration"]["postgresql_receiver"] = {
                        "endpoint": pg_config.get("endpoint"),
                        "databases": pg_config.get("databases", []),
                    }

            if "exporters" in otel_config:
                result["configuration"]["exporters"] = list(otel_config["exporters"].keys())
                if "datadog" in otel_config["exporters"]:
                    dd_exporter_config = otel_config["exporters"]["datadog"]
                    result["configuration"]["datadog_exporter_config"] = {
                        "metrics": dd_exporter_config.get("metrics", {}),
                    }

            if "service" in otel_config and "pipelines" in otel_config["service"]:
                result["configuration"]["pipelines"] = list(otel_config["service"]["pipelines"].keys())

        except Exception as e:
            pytest.exit(f"Failed to parse OTel collector config: {e}", 1)

        # Extract version from image name
        image_name = self.postgres_container.image.name
        postgres_version = image_name.split(":", 1)[1] if ":" in image_name else "unknown"

        result["testedDependencies"].append({"name": "postgresql", "version": postgres_version})

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
            logger.terminal.write_sep("-", f"Wait for {interfaces.otel_collector} (20s)")
            logger.terminal.flush()

            interfaces.otel_collector.wait(20)
            self.collector_container.stop()

        interfaces.otel_collector.check_deserialization_errors()

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        self.test_schemas(session, interfaces.otel_collector, [])
        super().pytest_sessionfinish(session, exitstatus)

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = "n/a"

        return result

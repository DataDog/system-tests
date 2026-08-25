import json
import os
import pytest
from pathlib import Path

from utils import interfaces
from utils._context.component_version import ComponentVersion, Version
from utils._context.constants import WeblogCategory
from utils._context.containers import (
    OpenTelemetryCollectorContainer,
    WeblogContainer,
)
from utils._logger import logger
from utils.proxy.ports import ProxyPorts

from .core import scenario_groups
from .endtoend import DockerScenario


class AppSecOtelCollectorScenario(DockerScenario):
    """DD Tracer + OTel Collector (data plane), no DD Agent (no Remote Config).

    Tests AppSec with dd-tracer exporting via OTLP to an OTel Collector
    with the datadog exporter, instead of the Datadog agent.

    Architecture:
      Weblog (dd-trace, AppSec, OTLP export)
        -> proxy (captures tracer->collector OTLP)
        -> OTel Collector (receives OTLP, exports via datadog exporter)
        -> proxy (captures collector->backend)
        -> Datadog Backend (or mocked)

    No DD Agent -> No Remote Config -> static rules only.
    """

    otel_collector_version: Version

    def __init__(
        self,
        name: str,
        *,
        mocked_backend: bool = True,
        weblog_env: dict | None = None,
        weblog_volumes: dict | None = None,
    ):
        super().__init__(
            name,
            github_workflow="endtoend",
            doc="AppSec with dd-tracer OTLP export to OTel Collector (no DD Agent, no RC)",
            scenario_groups=[scenario_groups.appsec, scenario_groups.open_telemetry],
            use_proxy=True,
            mocked_backend=mocked_backend,
            weblog_categories=[WeblogCategory.dd_trace],
        )

        # OTel Collector (data plane -- replaces DD agent)
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
        self.collector_container.name = "system-tests-collector"
        self._containers.append(self.collector_container)

        # AppSec-enabled weblog with OTLP export to the collector (via proxy)
        base_env = {
            "OTEL_TRACES_EXPORTER": "otlp",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=collector",
            "DD_TRACE_OTEL_ENABLED": "true",
            "DD_AGENT_HOST": "",
        }
        if weblog_env:
            base_env.update(weblog_env)

        self.weblog_container = WeblogContainer(
            environment=dict(base_env),
            appsec_enabled=True,
            iast_enabled=True,
            volumes=weblog_volumes,
        )
        self.weblog_container.depends_on.append(self.collector_container)
        self._containers.append(self.weblog_container)

    def post_start(self):
        """Override to handle otel-api version string from DD_TRACE_OTEL_ENABLED."""
        with open(self.weblog_container.healthcheck_log_file, encoding="utf-8") as f:
            data = json.load(f)
            lib = data["library"]

        # When DD_TRACE_OTEL_ENABLED=true, version may be "otel-api" which
        # can't be parsed by semantic_version. Fall back to 0.0.0.
        version = lib["version"]
        try:
            self.weblog_container._library = ComponentVersion(lib["name"], version)  # noqa: SLF001
        except ValueError:
            logger.warning(f"Cannot parse library version '{version}', using 0.0.0")
            self.weblog_container._library = ComponentVersion(lib["name"], "0.0.0")  # noqa: SLF001

        logger.stdout(f"Library: {self.weblog_container.library}")

    def configure(self, config: pytest.Config) -> None:
        # Set dummy docker image vars for the collector config (no postgres in this scenario)
        self.collector_container.environment["DOCKER_IMAGE_NAME"] = "none"
        self.collector_container.environment["DOCKER_IMAGE_TAG"] = "none"
        super().configure(config)

        if not self.proxy_container.mocked_backend:
            interfaces.backend.configure(self.host_log_folder, replay=self.replay)

            if "DD_API_KEY" not in os.environ:
                pytest.exit(f"{self.name} scenario requires a valid DD_API_KEY")

            self.collector_container.environment["DD_API_KEY"] = os.environ["DD_API_KEY"]

        interfaces.otel_collector.configure(self.host_log_folder, replay=self.replay)
        interfaces.open_telemetry.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)

        labels = self.collector_container.image.labels or {}
        self.otel_collector_version = Version(labels.get("org.opencontainers.image.version", "0.0.0"))
        self.components["otel_collector"] = self.otel_collector_version

        self.warmups.append(self._print_otel_collector_version)

        if not self.replay:
            self.warmups.insert(1, self._start_interfaces_watchdog)

    def customize_feature_parity_dashboard(self, result: dict) -> None:
        result["configuration"]["collector_version"] = str(self.otel_collector_version)
        result["configuration"]["collector_image"] = self.collector_container.image.name
        config_file_path = Path(self.collector_container.config_file)
        result["configuration"]["config_file"] = config_file_path.name

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog([interfaces.open_telemetry, interfaces.otel_collector, interfaces.library])

    def _print_otel_collector_version(self):
        logger.stdout(f"Otel collector: {self.otel_collector_version}")

    def post_setup(self, session: pytest.Session):  # noqa: ARG002
        try:
            if self.replay:
                logger.terminal.write_sep("-", "Load all data from logs")
                logger.terminal.flush()
                interfaces.otel_collector.load_data_from_logs()
                interfaces.open_telemetry.load_data_from_logs()
            else:
                logger.terminal.write_sep("-", f"Wait for {interfaces.open_telemetry} (5s)")
                logger.terminal.flush()
                interfaces.open_telemetry.wait(5)

                logger.terminal.write_sep("-", f"Wait for {interfaces.otel_collector} (20s)")
                logger.terminal.flush()
                interfaces.otel_collector.wait(20)
                self.collector_container.stop()
        finally:
            self.close_targets()

        interfaces.otel_collector.check_deserialization_errors()
        interfaces.open_telemetry.check_deserialization_errors()

"""OpenTelemetry scenario with PostgreSQL metrics collection"""

from utils._context.custom_otel_containers import PostgresOpenTelemetryCollectorContainer
from .core import scenario_groups
from .endtoend import EndToEndScenario
import os
import pytest
from utils import interfaces


class OpenTelemetryPostgreSQLScenario(EndToEndScenario):
    """Scenario for testing OpenTelemetry with PostgreSQL metrics collection"""

    def __init__(
        self,
        name: str,
        *,
        doc: str,
        weblog_env: dict | None = None,
        include_collector: bool = True,
        include_intake: bool = True,
        backend_interface_timeout: int = 20,
        require_api_key: bool = False,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            scenario_groups=[scenario_groups.all, scenario_groups.open_telemetry],
            weblog_env=weblog_env,
            include_postgres_db=True,
            require_api_key=require_api_key,
            backend_interface_timeout=backend_interface_timeout,
        )

        self.include_collector = include_collector
        self.include_intake = include_intake

        if include_collector:
            # Use collector with static merged PostgreSQL configuration
            self.collector_container = PostgresOpenTelemetryCollectorContainer(self.host_log_folder)
            self._required_containers.append(self.collector_container)
            self.weblog_container.depends_on.append(self.collector_container)

    def configure(self, config: pytest.Config):
        super().configure(config)
        self._check_env_vars()
        dd_site = os.environ.get("DD_SITE", "datad0g.com")

        if self.include_intake:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_INTAKE"] = "True"
            self.weblog_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY")
            self.weblog_container.environment["DD_SITE"] = dd_site

        if self.include_collector:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_COLLECTOR"] = "True"
            self.collector_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY")
            self.collector_container.environment["DD_SITE"] = dd_site

        # Configure OpenTelemetry interface (EndToEndScenario handles other interfaces)
        interfaces.open_telemetry.configure(self.host_log_folder, replay=self.replay)

    def _check_env_vars(self):
        if self._require_api_key:
            required_keys = ["DD_API_KEY", "DD_APP_KEY"]
            for key in required_keys:
                if not os.environ.get(key):
                    raise ValueError(f"Missing required environment variable: {key}")

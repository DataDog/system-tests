import os

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from utils.tools import logger
from utils._context.library_version import Version

from utils._context.containers import (
    AgentContainer,
    OpenTelemetryCollectorContainer,
    WeblogContainer,
)


from .core import DockerScenario, ScenarioGroup


class OpenTelemetryScenario(DockerScenario):
    """Scenario for testing opentelemetry"""

    def __init__(
        self,
        name,
        doc,
        weblog_env=None,
        include_agent=True,
        include_collector=True,
        include_intake=True,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        backend_interface_timeout=20,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="opentelemetry",
            scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.OPEN_TELEMETRY],
            use_proxy=True,
            include_postgres_db=include_postgres_db,
            include_cassandra_db=include_cassandra_db,
            include_mongo_db=include_mongo_db,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_mysql_db=include_mysql_db,
            include_sqlserver=include_sqlserver,
        )
        if include_agent:
            self.agent_container = AgentContainer(host_log_folder=self.host_log_folder, use_proxy=True)
            self._required_containers.append(self.agent_container)
        if include_collector:
            self.collector_container = OpenTelemetryCollectorContainer(self.host_log_folder)
            self._required_containers.append(self.collector_container)
        self.weblog_container = WeblogContainer(self.host_log_folder, environment=weblog_env)
        if include_agent:
            self.weblog_container.depends_on.append(self.agent_container)
        if include_collector:
            self.weblog_container.depends_on.append(self.collector_container)
        self._required_containers.append(self.weblog_container)
        self.include_agent = include_agent
        self.include_collector = include_collector
        self.include_intake = include_intake
        self.backend_interface_timeout = backend_interface_timeout

    def configure(self, config):
        super().configure(config)
        self._check_env_vars()
        dd_site = os.environ.get("DD_SITE", "datad0g.com")
        if self.include_intake:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_INTAKE"] = True
            self.weblog_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_2")
            self.weblog_container.environment["DD_SITE"] = dd_site
        if self.include_collector:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_COLLECTOR"] = True
            self.collector_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_3")
            self.collector_container.environment["DD_SITE"] = dd_site
        if self.include_agent:
            self.weblog_container.environment["OTEL_SYSTEST_INCLUDE_AGENT"] = True

    def _create_interface_folders(self):
        for interface in ("open_telemetry", "backend"):
            self.create_log_subfolder(f"interfaces/{interface}")
        if self.include_agent:
            self.create_log_subfolder("interfaces/agent")

    def _start_interface_watchdog(self):
        from utils import interfaces

        class Event(FileSystemEventHandler):
            def __init__(self, interface) -> None:
                super().__init__()
                self.interface = interface

            def _ingest(self, event):
                if event.is_directory:
                    return

                self.interface.ingest_file(event.src_path)

            on_modified = _ingest
            on_created = _ingest

        observer = PollingObserver()
        observer.schedule(
            Event(interfaces.open_telemetry), path=f"{self.host_log_folder}/interfaces/open_telemetry", recursive=True
        )
        if self.include_agent:
            observer.schedule(Event(interfaces.agent), path=f"{self.host_log_folder}/interfaces/agent")

        observer.start()

    def _get_warmups(self):
        warmups = super()._get_warmups()

        if not self.replay:
            warmups.insert(0, self._create_interface_folders)
            warmups.insert(1, self._start_interface_watchdog)
            warmups.append(self._wait_for_app_readiness)

        return warmups

    def _wait_for_app_readiness(self):
        from utils import interfaces  # import here to avoid circular import

        if self.use_proxy:
            logger.debug("Wait for app readiness")

            if not interfaces.open_telemetry.ready.wait(40):
                raise Exception("Open telemetry interface not ready")
            logger.debug("Open telemetry ready")

    def post_setup(self):
        from utils import interfaces

        if self.use_proxy:
            self._wait_interface(interfaces.open_telemetry, 5)
            self._wait_interface(interfaces.backend, self.backend_interface_timeout)

        self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_interface(self, interface, timeout):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    def _check_env_vars(self):
        if self.include_intake:
            assert all(
                key in os.environ for key in ("DD_API_KEY_2", "DD_APP_KEY_2")
            ), "OTel E2E test requires DD_API_KEY_2 and DD_APP_KEY_2"
        if self.include_collector:
            assert all(
                key in os.environ for key in ("DD_API_KEY_3", "DD_APP_KEY_3")
            ), "OTel E2E test requires DD_API_KEY_3 and DD_APP_KEY_3"

    @property
    def library(self):
        return self.weblog_container.library

    @property
    def agent_version(self):
        return self.agent_container.agent_version if self.include_agent else Version("0.0.0")

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant

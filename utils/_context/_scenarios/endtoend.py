import os
import pytest

from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from utils import interfaces
from utils._context.containers import (
    WeblogContainer,
    AgentContainer,
    ProxyContainer,
    PostgresContainer,
    MongoContainer,
    KafkaContainer,
    CassandraContainer,
    RabbitMqContainer,
    MySqlContainer,
    MsSqlServerContainer,
    BuddyContainer,
    TestedContainer,
    _get_client as get_docker_client,
)

from utils.tools import logger

from .core import Scenario, ScenarioGroup


class DockerScenario(Scenario):
    """Scenario that tests docker containers"""

    _network: Network = None

    def __init__(
        self,
        name,
        github_workflow,
        doc,
        scenario_groups=None,
        enable_ipv6: bool = False,
        use_proxy=True,
        rc_api_enabled=False,
        meta_structs_disabled=False,
        span_events=True,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self.use_proxy = use_proxy
        self.enable_ipv6 = enable_ipv6
        self.rc_api_enabled = rc_api_enabled
        self.meta_structs_disabled = False
        self.span_events = span_events

        if not self.use_proxy and self.rc_api_enabled:
            raise ValueError("rc_api_enabled requires use_proxy")

        self._required_containers: list[TestedContainer] = []
        self._supporting_containers: list[TestedContainer] = []

        if self.use_proxy:
            self.proxy_container = ProxyContainer(
                host_log_folder=self.host_log_folder,
                rc_api_enabled=rc_api_enabled,
                meta_structs_disabled=meta_structs_disabled,
                span_events=span_events,
                enable_ipv6=enable_ipv6,
            )

            self._required_containers.append(self.proxy_container)

        if include_postgres_db:
            self._supporting_containers.append(PostgresContainer(host_log_folder=self.host_log_folder))

        if include_mongo_db:
            self._supporting_containers.append(MongoContainer(host_log_folder=self.host_log_folder))

        if include_cassandra_db:
            self._supporting_containers.append(CassandraContainer(host_log_folder=self.host_log_folder))

        if include_kafka:
            self._supporting_containers.append(KafkaContainer(host_log_folder=self.host_log_folder))

        if include_rabbitmq:
            self._supporting_containers.append(RabbitMqContainer(host_log_folder=self.host_log_folder))

        if include_mysql_db:
            self._supporting_containers.append(MySqlContainer(host_log_folder=self.host_log_folder))

        if include_sqlserver:
            self._supporting_containers.append(MsSqlServerContainer(host_log_folder=self.host_log_folder))

        self._required_containers.extend(self._supporting_containers)

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        return [
            image_name
            for container in self._required_containers
            for image_name in container.get_image_list(library, weblog)
        ]

    def configure(self, config):
        for container in reversed(self._required_containers):
            container.configure(self.replay)

    def get_container_by_dd_integration_name(self, name):
        for container in self._required_containers:
            if hasattr(container, "dd_integration_service") and container.dd_integration_service == name:
                return container
        return None

    def _start_interfaces_watchdog(self, interfaces):
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

        # lot of issue using the default OS dependant notifiers (not working on WSL, reaching some inotify watcher
        # limits on Linux) -> using the good old bare polling system
        observer = PollingObserver()

        for interface in interfaces:
            observer.schedule(Event(interface), path=interface.log_folder)

        observer.start()

    def _create_network(self) -> None:
        name = "system-tests-ipv6" if self.enable_ipv6 else "system-tests-ipv4"

        for network in get_docker_client().networks.list(names=[name,]):
            self._network = network
            logger.debug(f"Network {name} still exists")
            return

        logger.debug(f"Create network {name}")

        if self.enable_ipv6:
            self._network = get_docker_client().networks.create(
                name=name,
                driver="bridge",
                enable_ipv6=True,
                ipam=IPAMConfig(driver="default", pool_configs=[IPAMPool(subnet="2001:db8:1::/64")]),
            )
            assert self._network.attrs["EnableIPv6"] is True, self._network.attrs
        else:
            get_docker_client().networks.create(name, check_duplicate=True)

    def get_warmups(self):
        warmups = super().get_warmups()

        if not self.replay:
            warmups.append(lambda: logger.stdout("Starting containers..."))
            warmups.append(self._create_network)
            warmups.append(self._start_containers)

        for container in self._required_containers:
            warmups.append(container.post_start)

        return warmups

    def _start_containers(self):
        threads = []

        for container in self._required_containers:
            threads.append(container.async_start(self._network))

        for thread in threads:
            thread.join()

        for container in self._required_containers:
            if container.healthy is False:
                pytest.exit(f"Container {container.name} can't be started", 1)

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
            except:
                logger.exception(f"Failed to remove container {container}")


class EndToEndScenario(DockerScenario):
    """Scenario that implier an instrumented HTTP application shipping a datadog tracer (weblog) and an datadog agent"""

    def __init__(
        self,
        name,
        doc,
        github_workflow="endtoend",
        scenario_groups=None,
        weblog_env=None,
        weblog_volumes=None,
        agent_env=None,
        enable_ipv6: bool = False,
        tracer_sampling_rate=None,
        appsec_enabled=True,
        iast_enabled=True,
        additional_trace_header_tags=(),
        library_interface_timeout=None,
        agent_interface_timeout=5,
        use_proxy=True,
        rc_api_enabled=False,
        meta_structs_disabled=False,
        span_events=True,
        backend_interface_timeout=0,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        include_otel_drop_in=False,
        include_buddies=False,
        require_api_key=False,
    ) -> None:

        scenario_groups = [ScenarioGroup.ALL, ScenarioGroup.END_TO_END, ScenarioGroup.TRACER_RELEASE] + (
            scenario_groups or []
        )

        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            enable_ipv6=enable_ipv6,
            use_proxy=use_proxy,
            rc_api_enabled=rc_api_enabled,
            meta_structs_disabled=meta_structs_disabled,
            span_events=span_events,
            include_postgres_db=include_postgres_db,
            include_cassandra_db=include_cassandra_db,
            include_mongo_db=include_mongo_db,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_mysql_db=include_mysql_db,
            include_sqlserver=include_sqlserver,
        )

        self._require_api_key = require_api_key

        self.agent_container = AgentContainer(
            host_log_folder=self.host_log_folder, use_proxy=use_proxy, environment=agent_env
        )

        if self.use_proxy:
            self.agent_container.depends_on.append(self.proxy_container)

        weblog_env = dict(weblog_env) if weblog_env else {}
        weblog_env.update(
            {
                "INCLUDE_POSTGRES": str(include_postgres_db).lower(),
                "INCLUDE_CASSANDRA": str(include_cassandra_db).lower(),
                "INCLUDE_MONGO": str(include_mongo_db).lower(),
                "INCLUDE_KAFKA": str(include_kafka).lower(),
                "INCLUDE_RABBITMQ": str(include_rabbitmq).lower(),
                "INCLUDE_MYSQL": str(include_mysql_db).lower(),
                "INCLUDE_SQLSERVER": str(include_sqlserver).lower(),
                "INCLUDE_OTEL_DROP_IN": str(include_otel_drop_in).lower(),
            }
        )

        self.weblog_container = WeblogContainer(
            self.host_log_folder,
            environment=weblog_env,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_enabled=appsec_enabled,
            iast_enabled=iast_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy,
            volumes=weblog_volumes,
        )

        self.weblog_container.depends_on.append(self.agent_container)
        self.weblog_container.depends_on.extend(self._supporting_containers)

        self.weblog_container.environment["SYSTEMTESTS_SCENARIO"] = self.name

        self._required_containers.append(self.agent_container)
        self._required_containers.append(self.weblog_container)

        # buddies are a set of weblog app that are not directly the test target
        # but are used only to test feature that invlove another app with a datadog tracer
        self.buddies: list[BuddyContainer] = []

        if include_buddies:
            # so far, only python, nodejs, java, ruby and golang are supported
            supported_languages = [("python", 9006), ("nodejs", 9002), ("java", 9003), ("ruby", 9004), ("golang", 9005)]

            self.buddies += [
                BuddyContainer(
                    f"{language}_buddy",
                    f"datadog/system-tests:{language}_buddy-v1",
                    self.host_log_folder,
                    proxy_port=port,
                    environment=weblog_env,
                )
                for language, port in supported_languages
            ]

            for buddy in self.buddies:
                buddy.depends_on.append(self.agent_container)
                buddy.depends_on.extend(self._supporting_containers)

            self._required_containers += self.buddies

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self.library_interface_timeout = library_interface_timeout

    def is_part_of(self, declared_scenario):
        return declared_scenario in (self.name, "EndToEndScenario")

    def configure(self, config):
        super().configure(config)

        if self._require_api_key and "DD_API_KEY" not in os.environ and not self.replay:
            pytest.exit("DD_API_KEY is required for this scenario", 1)

        if config.option.force_dd_trace_debug:
            self.weblog_container.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self.weblog_container.environment["_DD_IAST_DEBUG"] = "true"  # probably not used anymore ?
            self.weblog_container.environment["DD_IAST_DEBUG_ENABLED"] = "true"

        interfaces.agent.configure(self.host_log_folder, self.replay)
        interfaces.library.configure(self.host_log_folder, self.replay)
        interfaces.backend.configure(self.host_log_folder, self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, self.replay)

        for container in self.buddies:
            # a little bit of python wizzardry to solve circular import
            container.interface = getattr(interfaces, container.name)
            container.interface.configure(self.host_log_folder, self.replay)

        library = self.weblog_container.image.env["SYSTEM_TESTS_LIBRARY"]

        if self.library_interface_timeout is None:
            if library == "java":
                self.library_interface_timeout = 25
            elif library in ("golang",):
                self.library_interface_timeout = 10
            elif library in ("nodejs", "ruby"):
                self.library_interface_timeout = 0
            elif library in ("php",):
                # possibly something weird on obfuscator, let increase the delay for now
                self.library_interface_timeout = 10
            elif library in ("python",):
                self.library_interface_timeout = 5
            else:
                self.library_interface_timeout = 40

    def _get_weblog_system_info(self):
        try:
            code, (stdout, stderr) = self.weblog_container._container.exec_run("uname -a", demux=True)
            if code or stdout is None:
                message = f"Failed to get weblog system info: [{code}] {stderr.decode()} {stdout.decode()}"
            else:
                message = stdout.decode()
        except BaseException:
            logger.exception("can't get weblog system info")
        else:
            logger.stdout(f"Weblog system: {message.strip()}")

        if self.weblog_container.environment.get("DD_TRACE_DEBUG") == "true":
            logger.stdout("\t/!\\ Debug logs are activated in weblog")

        logger.stdout("")

    def _start_interface_watchdog(self):
        super()._start_interfaces_watchdog(
            [interfaces.library, interfaces.agent] + [container.interface for container in self.buddies]
        )

    def get_warmups(self):
        warmups = super().get_warmups()

        if not self.replay:
            warmups.insert(1, self._start_interface_watchdog)
            warmups.append(self._get_weblog_system_info)
            warmups.append(self._wait_for_app_readiness)

        return warmups

    def _wait_for_app_readiness(self):
        if self.use_proxy:
            logger.debug("Wait for app readiness")

            if not interfaces.library.ready.wait(40):
                raise Exception("Library not ready")

            logger.debug("Library ready")

            for container in self.buddies:
                if not container.interface.ready.wait(5):
                    raise ValueError(f"{container.name} not ready")

                logger.debug(f"{container.name} ready")

            if not interfaces.agent.ready.wait(40):
                raise Exception("Datadog agent not ready")
            logger.debug("Agent ready")

    def post_setup(self):
        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_and_stop_containers(self):

        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.library.load_data_from_logs()
            interfaces.library.check_deserialization_errors()

            for container in self.buddies:
                container.interface.load_data_from_logs()
                container.interface.check_deserialization_errors()

            interfaces.agent.load_data_from_logs()
            interfaces.agent.check_deserialization_errors()

            interfaces.backend.load_data_from_logs()

        elif self.use_proxy:
            self._wait_interface(interfaces.library, self.library_interface_timeout)

            if self.library in ("nodejs",):
                # for weblogs who supports it, call the flush endpoint
                try:
                    r = self.weblog_container.request("GET", "/flush", timeout=10)
                    assert r.status_code == 200
                except:
                    self.weblog_container.healthy = False
                    logger.stdout(
                        f"Warning: Failed to flush weblog, please check {self.host_log_folder}/docker/weblog/stdout.log"
                    )

            self.weblog_container.stop()
            interfaces.library.check_deserialization_errors()

            for container in self.buddies:
                # we already have waited for self.library_interface_timeout, so let's timeout=0
                self._wait_interface(container.interface, 0)
                container.stop()
                container.interface.check_deserialization_errors()

            self._wait_interface(interfaces.agent, self.agent_interface_timeout)
            self.agent_container.stop()
            interfaces.agent.check_deserialization_errors()

            self._wait_interface(interfaces.backend, self.backend_interface_timeout)

    def _wait_interface(self, interface, timeout):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    @property
    def dd_site(self):
        return self.agent_container.dd_site

    @property
    def library(self):
        return self.weblog_container.library

    @property
    def agent_version(self):
        return self.agent_container.agent_version

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant

    @property
    def tracer_sampling_rate(self):
        return self.weblog_container.tracer_sampling_rate

    @property
    def appsec_rules_file(self):
        return self.weblog_container.appsec_rules_file

    @property
    def uds_socket(self):
        return self.weblog_container.uds_socket

    @property
    def uds_mode(self):
        return self.weblog_container.uds_mode

    @property
    def telemetry_heartbeat_interval(self):
        return self.weblog_container.telemetry_heartbeat_interval

    def get_junit_properties(self):
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.agent]"] = self.agent_version
        result["dd_tags[systest.suite.context.library.name]"] = self.library.library
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant
        result["dd_tags[systest.suite.context.sampling_rate]"] = self.weblog_container.tracer_sampling_rate
        result["dd_tags[systest.suite.context.appsec_rules_file]"] = self.weblog_container.appsec_rules_file

        return result

    @property
    def components(self):
        return {
            "agent": self.agent_version,
            "library": self.library.version,
        }

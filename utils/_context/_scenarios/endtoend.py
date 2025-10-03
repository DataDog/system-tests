from dataclasses import dataclass
from http import HTTPStatus
import os
import sys
import pytest
from _pytest.reports import TestReport

from docker.models.networks import Network
from docker.types import IPAMConfig, IPAMPool

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.buddies import BuddyHostPorts
from utils.proxy.ports import ProxyPorts
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
    LocalstackContainer,
    ElasticMQContainer,
    _get_client as get_docker_client,
)

from utils._logger import logger

from .core import Scenario, ScenarioGroup, scenario_groups as all_scenario_groups


@dataclass
class _SchemaBug:
    endpoint: str
    data_path: str | None  # None means that all data_path will be considered as bug
    condition: bool
    ticket: str


class DockerScenario(Scenario):
    """Scenario that tests docker containers"""

    _network: Network = None

    def __init__(
        self,
        name: str,
        *,
        github_workflow: str | None,
        doc: str,
        scenario_groups: list[ScenarioGroup] | None = None,
        enable_ipv6: bool = False,
        use_proxy: bool = True,
        mocked_backend: bool = True,
        rc_api_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        include_postgres_db: bool = False,
        include_cassandra_db: bool = False,
        include_mongo_db: bool = False,
        include_kafka: bool = False,
        include_rabbitmq: bool = False,
        include_mysql_db: bool = False,
        include_sqlserver: bool = False,
        include_localstack: bool = False,
        include_elasticmq: bool = False,
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
                rc_api_enabled=rc_api_enabled,
                meta_structs_disabled=meta_structs_disabled,
                span_events=span_events,
                enable_ipv6=enable_ipv6,
                mocked_backend=mocked_backend,
            )

            self._required_containers.append(self.proxy_container)

        if include_postgres_db:
            self._supporting_containers.append(PostgresContainer())

        if include_mongo_db:
            self._supporting_containers.append(MongoContainer())

        if include_cassandra_db:
            self._supporting_containers.append(CassandraContainer())

        if include_kafka:
            self._supporting_containers.append(KafkaContainer())

        if include_rabbitmq:
            self._supporting_containers.append(RabbitMqContainer())

        if include_mysql_db:
            self._supporting_containers.append(MySqlContainer())

        if include_sqlserver:
            self._supporting_containers.append(MsSqlServerContainer())

        if include_localstack:
            self._supporting_containers.append(LocalstackContainer())

        if include_elasticmq:
            self._supporting_containers.append(ElasticMQContainer())

        self._required_containers.extend(self._supporting_containers)

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        return [
            image_name
            for container in self._required_containers
            for image_name in container.get_image_list(library, weblog)
        ]

    def configure(self, config: pytest.Config):  # noqa: ARG002
        if not self.replay:
            docker_info = get_docker_client().info()
            self.components["docker.Cgroup"] = docker_info.get("CgroupVersion", None)

        for container in reversed(self._required_containers):
            container.configure(host_log_folder=self.host_log_folder, replay=self.replay)

    def get_container_by_dd_integration_name(self, name: str):
        for container in self._required_containers:
            if hasattr(container, "dd_integration_service") and container.dd_integration_service == name:
                return container
        return None

    def start_interfaces_watchdog(self, interfaces: list[ProxyBasedInterfaceValidator]):
        class Event(FileSystemEventHandler):
            def __init__(self, interface: ProxyBasedInterfaceValidator) -> None:
                super().__init__()
                self.interface = interface

            def _ingest(self, event: FileSystemEvent):
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

        for network in get_docker_client().networks.list(names=[name]):
            self._network = network
            logger.debug(f"Network {name} still exists")
            return

        logger.debug(f"Create network {name}")

        if self.enable_ipv6:
            self._network = get_docker_client().networks.create(
                name=name,
                driver="bridge",
                enable_ipv6=True,
                ipam=IPAMConfig(
                    driver="default",
                    pool_configs=[IPAMPool(subnet="2001:db8:1::/64")],
                ),
            )
            assert self._network.attrs["EnableIPv6"] is True, self._network.attrs
        else:
            self._network = get_docker_client().networks.create(name, check_duplicate=True)

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

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):  # noqa: ARG002
        self.close_targets()

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
        name: str,
        *,
        doc: str,
        github_workflow: str = "endtoend",
        scenario_groups: list[ScenarioGroup] | None = None,
        weblog_env: dict[str, str | None] | None = None,
        weblog_volumes: dict | None = None,
        agent_env: dict[str, str | None] | None = None,
        enable_ipv6: bool = False,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        iast_enabled: bool = True,
        additional_trace_header_tags: tuple[str, ...] = (),
        library_interface_timeout: int | None = None,
        agent_interface_timeout: int = 5,
        use_proxy_for_weblog: bool = True,
        use_proxy_for_agent: bool = True,
        rc_api_enabled: bool = False,
        meta_structs_disabled: bool = False,
        span_events: bool = True,
        runtime_metrics_enabled: bool = False,
        backend_interface_timeout: int = 0,
        include_postgres_db: bool = False,
        include_cassandra_db: bool = False,
        include_mongo_db: bool = False,
        include_kafka: bool = False,
        include_rabbitmq: bool = False,
        include_mysql_db: bool = False,
        include_sqlserver: bool = False,
        include_localstack: bool = False,
        include_elasticmq: bool = False,
        include_otel_drop_in: bool = False,
        include_buddies: bool = False,
        require_api_key: bool = False,
    ) -> None:
        scenario_groups = [
            all_scenario_groups.all,
            all_scenario_groups.end_to_end,
            all_scenario_groups.tracer_release,
        ] + (scenario_groups or [])

        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            enable_ipv6=enable_ipv6,
            use_proxy=use_proxy_for_agent or use_proxy_for_weblog,
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
            include_localstack=include_localstack,
            include_elasticmq=include_elasticmq,
        )

        self._use_proxy_for_agent = use_proxy_for_agent
        self._use_proxy_for_weblog = use_proxy_for_weblog

        self._require_api_key = require_api_key

        self.agent_container = AgentContainer(use_proxy=use_proxy_for_agent, environment=agent_env)

        if use_proxy_for_agent:
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
            environment=weblog_env,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_enabled=appsec_enabled,
            iast_enabled=iast_enabled,
            runtime_metrics_enabled=runtime_metrics_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy_for_weblog,
            volumes=weblog_volumes,
        )

        self.weblog_container.depends_on.append(self.agent_container)
        self.weblog_container.depends_on.extend(self._supporting_containers)

        if use_proxy_for_weblog:
            self.weblog_container.depends_on.append(self.proxy_container)

        self._required_containers.append(self.agent_container)
        self._required_containers.append(self.weblog_container)

        # buddies are a set of weblog app that are not directly the test target
        # but are used only to test feature that invlove another app with a datadog tracer
        self.buddies: list[BuddyContainer] = []

        if include_buddies:
            # so far, only python, nodejs, java, ruby and golang are supported.
            # This list contains :
            # 1. the language
            # 2. the trace agent port where the buddy connect to the agent
            # 3. and the host port where the buddy is accessible
            supported_languages = [
                ("python", ProxyPorts.python_buddy, BuddyHostPorts.python, "datadog/system-tests:python_buddy-v2"),
                ("nodejs", ProxyPorts.nodejs_buddy, BuddyHostPorts.nodejs, "datadog/system-tests:nodejs_buddy-v1"),
                ("java", ProxyPorts.java_buddy, BuddyHostPorts.java, "datadog/system-tests:java_buddy-v1"),
                ("ruby", ProxyPorts.ruby_buddy, BuddyHostPorts.ruby, "datadog/system-tests:ruby_buddy-v2"),
                ("golang", ProxyPorts.golang_buddy, BuddyHostPorts.golang, "datadog/system-tests:golang_buddy-v2"),
            ]

            self.buddies += [
                BuddyContainer(
                    f"{language}_buddy",
                    image_name,
                    host_port=host_port,
                    trace_agent_port=trace_agent_port,
                    environment=weblog_env,
                )
                for language, trace_agent_port, host_port, image_name in supported_languages
            ]

            for buddy in self.buddies:
                buddy.depends_on.append(self.agent_container)
                buddy.depends_on.extend(self._supporting_containers)

            self._required_containers += self.buddies

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self._library_interface_timeout = library_interface_timeout

    def configure(self, config: pytest.Config):
        super().configure(config)

        self.weblog_container.environment["SYSTEMTESTS_SCENARIO"] = self.name

        if self._require_api_key and "DD_API_KEY" not in os.environ and not self.replay:
            pytest.exit("DD_API_KEY is required for this scenario", 1)

        if config.option.force_dd_trace_debug:
            self.weblog_container.environment["DD_TRACE_DEBUG"] = "true"

        if config.option.force_dd_iast_debug:
            self.weblog_container.environment["_DD_IAST_DEBUG"] = "true"  # probably not used anymore ?
            self.weblog_container.environment["DD_IAST_DEBUG_ENABLED"] = "true"

        interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent_stdout.configure(self.host_log_folder, replay=self.replay)

        for container in self.buddies:
            container.interface.configure(self.host_log_folder, replay=self.replay)

        library = self.weblog_container.image.labels["system-tests-library"]

        if self._library_interface_timeout is None:
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
        else:
            self.library_interface_timeout = self._library_interface_timeout

    def _get_weblog_system_info(self):
        try:
            code, (stdout, stderr) = self.weblog_container.exec_run("uname -a", demux=True)
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

    def _start_interfaces_watchdog(self):
        super().start_interfaces_watchdog(
            [interfaces.library, interfaces.agent] + [container.interface for container in self.buddies]
        )

    def _set_weblog_domain(self):
        if self.enable_ipv6:
            from utils import weblog  # TODO better interface

            if sys.platform == "linux":
                # on Linux, with ipv6 mode, we can't use localhost anymore for a reason I ignore
                # To fix, we use the container ipv4 address as weblog doamin, as it's accessible from host
                weblog.domain = self.weblog_container.network_ip(self._network)
                logger.info(f"Linux => Using Container IPv6 address [{weblog.domain}] as weblog domain")

            elif sys.platform == "darwin":
                # on Mac, this ipv4 address can't be used, because container IP are not accessible from host
                # as they are on an network intermal to the docker VM. But we can still use localhost.
                logger.info("Mac => Using localhost as weblog domain")
            else:
                pytest.exit(f"Unsupported platform {sys.platform} with ipv6 enabled", 1)

    def _set_components(self):
        self.components["agent"] = self.agent_version
        self.components["library"] = self.library.version

    def get_warmups(self):
        warmups = super().get_warmups()

        if not self.replay:
            warmups.insert(1, self._start_interfaces_watchdog)
            warmups.append(self._get_weblog_system_info)
            warmups.append(self._wait_for_app_readiness)
            warmups.append(self._set_weblog_domain)
            warmups.append(self._set_components)

        return warmups

    def _wait_for_app_readiness(self):
        if self._use_proxy_for_weblog:
            logger.debug("Wait for app readiness")

            if not interfaces.library.ready.wait(40):
                raise ValueError("Library not ready")

            logger.debug("Library ready")

            for container in self.buddies:
                if not container.interface.ready.wait(5):
                    raise ValueError(f"{container.name} not ready")

                logger.debug(f"{container.name} ready")

        if self._use_proxy_for_agent:
            if not interfaces.agent.ready.wait(40):
                raise ValueError("Datadog agent not ready")
            logger.debug("Agent ready")

    def post_setup(self, session: pytest.Session):
        # if no test are run, skip interface tomeouts
        is_empty_test_run = session.config.option.skip_empty_scenario and len(session.items) == 0

        try:
            self._wait_and_stop_containers(force_interface_timout_to_zero=is_empty_test_run)
        finally:
            self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_and_stop_containers(self, *, force_interface_timout_to_zero: bool):
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

        else:
            self._wait_interface(
                interfaces.library, 0 if force_interface_timout_to_zero else self.library_interface_timeout
            )

            if self.library in (
                "nodejs",
                "ruby",
            ):
                from utils import weblog  # TODO better interface

                # for weblogs who supports it, call the flush endpoint
                try:
                    r = weblog.get("/flush", timeout=10)
                    assert r.status_code == HTTPStatus.OK
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

            self._wait_interface(
                interfaces.agent, 0 if force_interface_timout_to_zero else self.agent_interface_timeout
            )
            self.agent_container.stop()
            interfaces.agent.check_deserialization_errors()

            self._wait_interface(
                interfaces.backend, 0 if force_interface_timout_to_zero else self.backend_interface_timeout
            )

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int):
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()

        interface.wait(timeout)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        library_bugs = [
            _SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content[]",
                condition=self.library >= "php@1.12.0",
                ticket="DEBUG-4431",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$",
                condition=self.library > "nodejs@5.36.0",
                ticket="DEBUG-3487",
            ),
            _SchemaBug(endpoint="/v0.4/traces", data_path="$", condition=self.library == "java", ticket="APMAPI-1161"),
            _SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload.configuration[]",
                condition=self.library >= "nodejs@2.27.1",
                ticket="APPSEC-52805",
            ),
            _SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=self.library < "python@v2.9.0.dev",
                ticket="APPSEC-52845",
            ),
            _SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload.configuration[].value",
                condition=self.library == "golang",
                ticket="APMS-12697",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content",
                condition=self.library < "nodejs@5.31.0",
                ticket="DEBUG-2864",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[].content[].debugger.diagnostics",
                condition=self.library == "nodejs",
                ticket="DEBUG-3245",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/input",
                data_path="$[].debugger.snapshot.stack[].lineNumber",
                condition=self.library in ("python@2.16.2", "python@2.16.3")
                and self.name == "DEBUGGER_EXPRESSION_LANGUAGE",
                ticket="APMRP-360",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/input",
                data_path="$[].debugger.snapshot.probe.location.method",
                condition=self.library == "dotnet",
                ticket="DEBUG-3734",
            ),
            _SchemaBug(
                endpoint="/symdb/v1/input",
                data_path=None,
                condition=self.library == "dotnet" and self.name == "DEBUGGER_SYMDB",
                ticket="DEBUG-3298",
            ),
            _SchemaBug(
                endpoint="/telemetry/proxy/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=self.library > "php@1.7.3",
                ticket="APMAPI-1270",
            ),
            _SchemaBug(
                endpoint="/debugger/v1/diagnostics",
                data_path="$[]",
                condition=self.library >= "php@1.8.3",
                ticket="DEBUG-3709",
            ),
            _SchemaBug(
                endpoint="/v0.6/stats",
                data_path=None,
                condition=self.library
                in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "java", "nodejs", "php", "python", "ruby")
                and self.name in ("TRACE_STATS_COMPUTATION", "TRACING_CONFIG_NONDEFAULT_3"),
                ticket="APMSP-2158",
            ),
            _SchemaBug(
                endpoint="/symdb/v1/input",
                data_path="$[].content",
                condition=self.library >= "golang@2.4.0-dev" and self.name == "DEBUGGER_SYMDB",
                ticket="DEBUG-4541",
            ),
        ]

        self._test_schemas(session, interfaces.library, library_bugs)

        agent_bugs = [
            _SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$",
                condition=self.library > "nodejs@5.36.0",
                ticket="DEBUG-3487",
            ),
            _SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload.configuration[]",
                condition=self.library >= "nodejs@2.27.1"
                or self.name in ("CROSSED_TRACING_LIBRARIES", "GRAPHQL_APPSEC"),
                ticket="APPSEC-52805",
            ),
            _SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=self.library < "python@v2.9.0.dev",
                ticket="APPSEC-52845",
            ),
            _SchemaBug(
                endpoint="/api/v2/apmtelemetry", data_path="$", condition=True, ticket="???"
            ),  # the main payload sent by the agent may be an array i/o an object
            _SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload.configuration[].value",
                condition=self.library == "golang",
                ticket="APMS-12697",
            ),
            _SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[].content",
                condition=self.library < "nodejs@5.31.0",
                ticket="DEBUG-2864",
            ),
            _SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[]",
                condition=self.library == "dotnet" and self.name == "DEBUGGER_SYMDB",
                ticket="DEBUG-3298",
            ),
            _SchemaBug(
                endpoint="/api/v2/apmtelemetry",
                data_path="$.payload",
                condition=self.library > "php@1.7.3",
                ticket="XXX-1234",
            ),
            _SchemaBug(
                endpoint="/api/v2/debugger",
                data_path="$[]",
                condition=self.library >= "php@1.8.3",
                ticket="DEBUG-3709",
            ),
        ]
        self._test_schemas(session, interfaces.agent, agent_bugs)

        return super().pytest_sessionfinish(session, exitstatus)

    def _test_schemas(
        self, session: pytest.Session, interface: ProxyBasedInterfaceValidator, known_bugs: list[_SchemaBug]
    ) -> None:
        long_repr = []

        excluded_points = {(bug.endpoint, bug.data_path) for bug in known_bugs if bug.condition}

        for error in interface.get_schemas_errors():
            if (error.endpoint, error.data_path) not in excluded_points and (
                error.endpoint,
                None,
            ) not in excluded_points:
                long_repr.append(f"* {error.message}")

        if len(long_repr) != 0:
            report = TestReport(
                f"{os.path.relpath(__file__)}::{self.__class__.__name__}::_test_schemas",
                (f"{interface.name} Schema Validation", 12, f"{interface.name}'s schema validation"),
                {},
                "failed",
                "\n".join(long_repr),
                "call",
            )

            if "error" not in logger.terminal.stats:
                logger.terminal.stats["error"] = []

            logger.terminal.stats["error"].append(report)
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

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

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.agent]"] = self.agent_version
        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant
        result["dd_tags[systest.suite.context.appsec_rules_file]"] = self.weblog_container.appsec_rules_file or ""

        return result

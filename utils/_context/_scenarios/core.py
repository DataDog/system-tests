from enum import Enum
from logging import FileHandler
import os
from pathlib import Path
import shutil
from threading import Thread

import pytest
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from utils._context.containers import (
    WeblogContainer,
    AgentContainer,
    ProxyContainer,
    PostgresContainer,
    MongoContainer,
    KafkaContainer,
    ZooKeeperContainer,
    CassandraContainer,
    RabbitMqContainer,
    MySqlContainer,
    ElasticMQContainer,
    LocalstackContainer,
    SqlServerContainer,
    create_network,
    BuddyContainer,
    TestedContainer,
    start_container,
)

from utils._context.library_version import LibraryVersion
from utils.tools import logger, get_log_formatter


class ScenarioGroup(Enum):
    ALL = "all"
    APPSEC = "appsec"
    DEBUGGER = "debugger"
    END_TO_END = "end-to-end"
    GRAPHQL = "graphql"
    INTEGRATIONS = "integrations"
    LIB_INJECTION = "lib-injection"
    OPEN_TELEMETRY = "open-telemetry"
    PARAMETRIC = "parametric"
    PROFILING = "profiling"
    SAMPLING = "sampling"


VALID_GITHUB_WORKFLOWS = {
    None,
    "endtoend",
    "graphql",
    "libinjection",
    "opentelemetry",
    "parametric",
    "testthetest",
}


class Scenario:
    def __init__(self, name, github_workflow, doc, scenario_groups=None) -> None:
        self.name = name
        self.replay = False
        self.doc = doc
        self.rc_api_enabled = False
        self.github_workflow = github_workflow
        self.scenario_groups = scenario_groups or []

        self.scenario_groups = list(set(self.scenario_groups))  # removes duplicates

        assert (
            self.github_workflow in VALID_GITHUB_WORKFLOWS
        ), f"Invalid github_workflow {self.github_workflow} for {self.name}"

        for group in self.scenario_groups:
            assert group in ScenarioGroup, f"Invalid scenario group {group} for {self.name}: {group}"

    def create_log_subfolder(self, subfolder, remove_if_exists=False):
        if self.replay:
            return

        path = os.path.join(self.host_log_folder, subfolder)

        if remove_if_exists:
            shutil.rmtree(path, ignore_errors=True)

        Path(path).mkdir(parents=True, exist_ok=True)

    def __call__(self, test_object):
        """handles @scenarios.scenario_name"""

        # Check that no scenario has been already declared
        for marker in getattr(test_object, "pytestmark", []):
            if marker.name == "scenario":
                raise ValueError(f"Error on {test_object}: You can declare only one scenario")

        pytest.mark.scenario(self.name)(test_object)

        return test_object

    def configure(self, config):
        self.replay = config.option.replay

        if not hasattr(config, "workerinput"):
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker

            # xdist use case: with xdist subworkers, this function is called
            # * at very first command
            # * then once per worker

            # the issue is that create_log_subfolder() remove the folder if it exists, then create it. This scenario is then possible :
            # 1. some worker A creates logs/
            # 2. another worker B removes it
            # 3. worker A want to create logs/tests.log -> boom

            # to fix that, only the main worker can create the log folder

            self.create_log_subfolder("", remove_if_exists=True)

        handler = FileHandler(f"{self.host_log_folder}/tests.log", encoding="utf-8")
        handler.setFormatter(get_log_formatter())

        logger.addHandler(handler)

    def session_start(self):
        """called at the very begning of the process"""

        logger.terminal.write_sep("=", "test context", bold=True)

        try:
            for warmup in self._get_warmups():
                logger.info(f"Executing warmup {warmup}")
                warmup()
        except:
            self.close_targets()
            raise

    def pytest_sessionfinish(self, session):
        """called at the end of the process"""

    def _get_warmups(self):
        return [
            lambda: logger.stdout(f"Scenario: {self.name}"),
            lambda: logger.stdout(f"Logs folder: ./{self.host_log_folder}"),
        ]

    def post_setup(self):
        """called after test setup"""

    def close_targets(self):
        """called after setup"""

    @property
    def host_log_folder(self):
        return "logs" if self.name == "DEFAULT" else f"logs_{self.name.lower()}"

    # Set of properties used in test decorators
    @property
    def dd_site(self):
        return ""

    @property
    def library(self):
        return LibraryVersion("undefined")

    @property
    def agent_version(self):
        return ""

    @property
    def weblog_variant(self):
        return ""

    @property
    def tracer_sampling_rate(self):
        return 0

    @property
    def appsec_rules_file(self):
        return ""

    @property
    def uds_socket(self):
        return ""

    @property
    def libddwaf_version(self):
        return ""

    @property
    def appsec_rules_version(self):
        return ""

    @property
    def uds_mode(self):
        return False

    @property
    def telemetry_heartbeat_interval(self):
        return 0

    @property
    def components(self):
        return {}

    @property
    def parametrized_tests_metadata(self):
        return {}

    def get_junit_properties(self):
        return {"dd_tags[systest.suite.context.scenario]": self.name}

    def customize_feature_parity_dashboard(self, result):
        pass

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"

    def is_part_of(self, declared_scenario):
        return self.name == declared_scenario


class DockerScenario(Scenario):
    """Scenario that tests docker containers"""

    def __init__(
        self,
        name,
        github_workflow,
        doc,
        scenario_groups=None,
        use_proxy=True,
        rc_api_enabled=False,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        include_elasticmq=False,
        include_localstack=False,
    ) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self.use_proxy = use_proxy
        self.rc_api_enabled = rc_api_enabled

        if not self.use_proxy and self.rc_api_enabled:
            raise ValueError("rc_api_enabled requires use_proxy")

        self._required_containers: list[TestedContainer] = []

        if self.use_proxy:
            self._required_containers.append(
                ProxyContainer(host_log_folder=self.host_log_folder, rc_api_enabled=rc_api_enabled)
            )  # we want the proxy being the first container to start

        if include_postgres_db:
            self._required_containers.append(PostgresContainer(host_log_folder=self.host_log_folder))

        if include_mongo_db:
            self._required_containers.append(MongoContainer(host_log_folder=self.host_log_folder))

        if include_cassandra_db:
            self._required_containers.append(CassandraContainer(host_log_folder=self.host_log_folder))

        if include_kafka:
            # kafka requires zookeeper
            self._required_containers.append(ZooKeeperContainer(host_log_folder=self.host_log_folder))
            self._required_containers.append(KafkaContainer(host_log_folder=self.host_log_folder))

        if include_rabbitmq:
            self._required_containers.append(RabbitMqContainer(host_log_folder=self.host_log_folder))

        if include_mysql_db:
            self._required_containers.append(MySqlContainer(host_log_folder=self.host_log_folder))

        if include_sqlserver:
            self._required_containers.append(SqlServerContainer(host_log_folder=self.host_log_folder))

        if include_elasticmq:
            self._required_containers.append(ElasticMQContainer(host_log_folder=self.host_log_folder))

        if include_localstack:
            self._required_containers.append(LocalstackContainer(host_log_folder=self.host_log_folder))

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        return [
            image_name
            for container in self._required_containers
            for image_name in container.get_image_list(library, weblog)
        ]

    def configure(self, config):
        super().configure(config)

        for container in reversed(self._required_containers):
            container.configure(self.replay)

    def get_container_by_dd_integration_name(self, name):
        for container in self._required_containers:
            if hasattr(container, "dd_integration_service") and container.dd_integration_service == name:
                return container
        return None

    def _get_warmups(self):
        warmups = super()._get_warmups()

        if not self.replay:
            warmups.append(create_network)

        # on replay mode, _start_containers() won't actually start containers, 
        # but will only call the necessary post_start method
        warmups.append(self._start_containers)

        return warmups

    def _start_containers(self):
        dependencies = self._get_dependencies()
        threads = {}

        for container in self._required_containers:
            self._start_container(container, dependencies, threads)

        for thread in threads.values():
            thread.join()

    def _start_container(self, container, dependencies, threads):
        if threads.get(container): return threads.get(container)

        for dependency_thread in self._start_dependencies(container, dependencies, threads):
            dependency_thread.join()

        thread = Thread(target=start_container, args=(container, self.replay,))
        thread.start()
        threads[container] = thread

        return thread

    def _start_dependencies(self, container, dependencies, threads):
        dependency_threads = []

        for dependency in dependencies[container]:
            thread = self._start_container(dependency, dependencies, threads)
            dependency_threads.append(thread)

        return dependency_threads

    def _get_dependencies(self):
        dependencies = {}
        image_containers = {}

        for container in self._required_containers:
            containers = image_containers.get(container.__class__, [])
            containers.append(container)
            
            image_containers[container.__class__] = containers

            dependencies[container] = []

        for container in self._required_containers:
            for dependency in container.depends_on:
                for dependency_container in image_containers.get(dependency, []):
                    dependencies[container].append(dependency_container)

        return dependencies

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
        tracer_sampling_rate=None,
        appsec_rules=None,
        appsec_enabled=True,
        additional_trace_header_tags=(),
        library_interface_timeout=None,
        agent_interface_timeout=5,
        use_proxy=True,
        rc_api_enabled=False,
        backend_interface_timeout=0,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        include_buddies=False,
        include_elasticmq=False,
        include_localstack=False,
    ) -> None:

        scenario_groups = [ScenarioGroup.ALL, ScenarioGroup.END_TO_END] + (scenario_groups or [])

        super().__init__(
            name,
            doc=doc,
            github_workflow=github_workflow,
            scenario_groups=scenario_groups,
            use_proxy=use_proxy,
            rc_api_enabled=rc_api_enabled,
            include_postgres_db=include_postgres_db,
            include_cassandra_db=include_cassandra_db,
            include_mongo_db=include_mongo_db,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_mysql_db=include_mysql_db,
            include_sqlserver=include_sqlserver,
            include_elasticmq=include_elasticmq,
            include_localstack=include_localstack,
        )

        self.agent_container = AgentContainer(host_log_folder=self.host_log_folder, use_proxy=use_proxy)

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
                "INCLUDE_ELASTICMQ": str(include_elasticmq).lower(),
                "INCLUDE_LOCALSTACK": str(include_localstack).lower(),
            }
        )

        self.weblog_container = WeblogContainer(
            self.host_log_folder,
            environment=weblog_env,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_rules=appsec_rules,
            appsec_enabled=appsec_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
            use_proxy=use_proxy,
        )

        self.weblog_container.environment["SYSTEMTESTS_SCENARIO"] = self.name

        self._required_containers.append(self.agent_container)
        self._required_containers.append(self.weblog_container)

        # buddies are a set of weblog app that are not directly the test target
        # but are used only to test feature that invlove another app with a datadog tracer
        self.buddies: list[BuddyContainer] = []

        if include_buddies:
            # so far, only python, nodejs, java, ruby and golang are supported
            supported_languages = [("python", 9001), ("nodejs", 9002), ("java", 9003), ("ruby", 9004), ("golang", 9005)]

            self.buddies += [
                BuddyContainer(
                    f"{language}_buddy",
                    f"datadog/system-tests:{language}_buddy-v0",
                    self.host_log_folder,
                    proxy_port=port,
                    environment=weblog_env,
                )
                for language, port in supported_languages
            ]

            self._required_containers += self.buddies

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self.library_interface_timeout = library_interface_timeout

    def is_part_of(self, declared_scenario):
        return declared_scenario in (self.name, "EndToEndScenario")

    def configure(self, config):
        from utils import interfaces

        super().configure(config)

        interfaces.agent.configure(self.replay)
        interfaces.library.configure(self.replay)
        interfaces.backend.configure(self.replay)
        interfaces.library_dotnet_managed.configure(self.replay)

        for container in self.buddies:
            # a little bit of python wizzardry to solve circular import
            container.interface = getattr(interfaces, container.name)
            container.interface.configure(self.replay)

        if self.library_interface_timeout is None:
            if self.weblog_container.library == "java":
                self.library_interface_timeout = 25
            elif self.weblog_container.library.library in ("golang",):
                self.library_interface_timeout = 10
            elif self.weblog_container.library.library in ("nodejs", "ruby"):
                self.library_interface_timeout = 0
            elif self.weblog_container.library.library in ("php",):
                # possibly something weird on obfuscator, let increase the delay for now
                self.library_interface_timeout = 10
            elif self.weblog_container.library.library in ("python",):
                self.library_interface_timeout = 5
            else:
                self.library_interface_timeout = 40

    def session_start(self):
        super().session_start()

        if self.replay:
            return

        try:
            code, (stdout, stderr) = self.weblog_container._container.exec_run("uname -a", demux=True)
            if code or stdout is None:
                message = f"Failed to get weblog system info: [{code}] {stderr.decode()} {stdout.decode()}"
            else:
                message = stdout.decode()
        except BaseException:
            logger.exception("can't get weblog system info")
        else:
            logger.stdout(f"Weblog system: {message}")

    def _create_interface_folders(self):
        for interface in ("agent", "library", "backend"):
            self.create_log_subfolder(f"interfaces/{interface}")

        for container in self.buddies:
            self.create_log_subfolder(f"interfaces/{container.interface.name}")

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

        # lot of issue using the default OS dependant notifiers (not working on WSL, reaching some inotify watcher
        # limits on Linux) -> using the good old bare polling system
        observer = PollingObserver()

        observer.schedule(Event(interfaces.library), path=f"{self.host_log_folder}/interfaces/library")
        observer.schedule(Event(interfaces.agent), path=f"{self.host_log_folder}/interfaces/agent")

        for container in self.buddies:
            observer.schedule(Event(container.interface), path=container.interface._log_folder)

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
        from utils import interfaces

        try:
            self._wait_and_stop_containers()
        finally:
            self.close_targets()

        interfaces.library_dotnet_managed.load_data()

    def _wait_and_stop_containers(self):
        from utils import interfaces

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
                except Exception as e:
                    self.weblog_container.collect_logs()
                    raise Exception(
                        f"Failed to flush weblog, please check {self.host_log_folder}/docker/weblog/stdout.log"
                    ) from e

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
    def libddwaf_version(self):
        return self.weblog_container.libddwaf_version

    @property
    def appsec_rules_version(self):
        return self.weblog_container.appsec_rules_version

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
        result["dd_tags[systest.suite.context.libddwaf_version]"] = self.weblog_container.libddwaf_version
        result["dd_tags[systest.suite.context.appsec_rules_file]"] = self.weblog_container.appsec_rules_file

        return result

    @property
    def components(self):
        return {
            "agent": self.agent_version,
            "library": self.library.version,
            "libddwaf": self.weblog_container.libddwaf_version,
            "appsec_rules": self.appsec_rules_version,
        }

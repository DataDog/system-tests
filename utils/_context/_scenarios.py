from logging import FileHandler
import os
from pathlib import Path
import shutil
import time
import subprocess
import json
import glob

import pytest
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from utils._context.library_version import LibraryVersion, Version

from utils._context.header_tag_vars import VALID_CONFIGS, INVALID_CONFIGS
from utils.onboarding.provision_utils import ProvisionMatrix, ProvisionFilter

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
    LocalstackContainer,
    OpenTelemetryCollectorContainer,
    SqlServerContainer,
    create_network,
    # SqlDbTestedContainer,
    BuddyContainer,
)

from utils.tools import logger, get_log_formatter, update_environ_with_local_env

update_environ_with_local_env()


class _Scenario:
    def __init__(self, name, doc) -> None:
        self.name = name
        self.replay = False
        self.doc = doc

    def create_log_subfolder(self, subfolder, remove_if_exists=False):
        if self.replay:
            return

        path = os.path.join(self.host_log_folder, subfolder)

        if remove_if_exists:
            shutil.rmtree(path, ignore_errors=True)

        Path(path).mkdir(parents=True, exist_ok=True)

    def __call__(self, test_object):
        """ handles @scenarios.scenario_name """

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

        if self.replay:
            from utils import weblog

            weblog.init_replay_mode(self.host_log_folder)

    def session_start(self):
        """ called at the very begning of the process """

        self.print_test_context()

        if self.replay:
            return

        logger.stdout("Executing warmups...")

        try:
            for warmup in self._get_warmups():
                logger.info(f"Executing warmup {warmup}")
                warmup()
        except:
            self.close_targets()
            raise

    def pytest_sessionfinish(self, session):
        """ called at the end of the process  """

    def print_test_context(self):
        logger.terminal.write_sep("=", "test context", bold=True)
        logger.stdout(f"Scenario: {self.name}")
        logger.stdout(f"Logs folder: ./{self.host_log_folder}")

    def _get_warmups(self):
        return []

    def post_setup(self):
        """ called after test setup """

    def close_targets(self):
        """ called after setup"""

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
    def php_appsec(self):
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

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"


class TestTheTestScenario(_Scenario):
    @property
    def agent_version(self):
        return "0.77.0"

    @property
    def components(self):
        return {"mock_comp1": "mock_comp1_value"}

    @property
    def parametrized_tests_metadata(self):
        return {"tests/test_the_test/test_json_report.py::Test_Mock::test_mock": {"meta1": "meta1"}}

    @property
    def library(self):
        return LibraryVersion("java", "0.66.0")

    @property
    def weblog_variant(self):
        return "spring"


class _DockerScenario(_Scenario):
    """ Scenario that tests docker containers """

    def __init__(
        self,
        name,
        doc,
        use_proxy=True,
        proxy_state=None,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        include_localstack=False,
    ) -> None:
        super().__init__(name, doc=doc)

        self.use_proxy = use_proxy
        self._required_containers = []

        if self.use_proxy:
            self._required_containers.append(
                ProxyContainer(host_log_folder=self.host_log_folder, proxy_state=proxy_state)
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

        if include_localstack:
            self._required_containers.append(LocalstackContainer(host_log_folder=self.host_log_folder))

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

        warmups.append(create_network)

        for container in self._required_containers:
            warmups.append(container.start)

        return warmups

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
            except:
                logger.exception(f"Failed to remove container {container}")


class EndToEndScenario(_DockerScenario):
    """ Scenario that implier an instrumented HTTP application shipping a datadog tracer (weblog) and an datadog agent """

    def __init__(
        self,
        name,
        doc,
        weblog_env=None,
        tracer_sampling_rate=None,
        appsec_rules=None,
        appsec_enabled=True,
        additional_trace_header_tags=(),
        library_interface_timeout=None,
        agent_interface_timeout=5,
        use_proxy=True,
        proxy_state=None,
        backend_interface_timeout=0,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
        include_sqlserver=False,
        include_buddies=False,
        include_localstack=False,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            use_proxy=use_proxy,
            proxy_state=proxy_state,
            include_postgres_db=include_postgres_db,
            include_cassandra_db=include_cassandra_db,
            include_mongo_db=include_mongo_db,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_mysql_db=include_mysql_db,
            include_sqlserver=include_sqlserver,
            include_localstack=include_localstack,
        )

        self.agent_container = AgentContainer(host_log_folder=self.host_log_folder, use_proxy=use_proxy)

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
            elif self.weblog_container.library.library in ("nodejs",):
                self.library_interface_timeout = 5
            elif self.weblog_container.library.library in ("php",):
                # possibly something weird on obfuscator, let increase the delay for now
                self.library_interface_timeout = 10
            elif self.weblog_container.library.library in ("python",):
                self.library_interface_timeout = 25
            else:
                self.library_interface_timeout = 40

    def session_start(self):
        super().session_start()
        try:
            code, (stdout, stderr) = self.weblog_container._container.exec_run("uname -a", demux=True)
            if code:
                message = f"Failed to get weblog system info: [{code}] {stderr.decode()} {stdout.decode()}"
            else:
                message = stdout.decode()
        except BaseException as e:
            message = f"Unexpected exception {e}"
        logger.stdout(f"Weblog system: {message}")

    def print_test_context(self):
        from utils import weblog

        super().print_test_context()

        logger.debug(f"Docker host is {weblog.domain}")

        logger.stdout(f"Library: {self.library}")
        logger.stdout(f"Agent: {self.agent_version}")

        if self.library == "php":
            logger.stdout(f"AppSec: {self.weblog_container.php_appsec}")

        if self.weblog_container.libddwaf_version:
            logger.stdout(f"libddwaf: {self.weblog_container.libddwaf_version}")

        if self.weblog_container.appsec_rules_file:
            logger.stdout(f"AppSec rules version: {self.weblog_container.appsec_rules_version}")

        if self.weblog_container.uds_mode:
            logger.stdout(f"UDS socket: {self.weblog_container.uds_socket}")

        logger.stdout(f"Weblog variant: {self.weblog_container.weblog_variant}")
        logger.stdout(f"Backend: {self.agent_container.dd_site}")

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

    def close_targets(self):
        from utils import weblog

        super().close_targets()

        weblog.save_requests(self.host_log_folder)

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
    def php_appsec(self):
        return self.weblog_container.php_appsec

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
            "php_appsec": self.php_appsec,
            "libddwaf": self.weblog_container.libddwaf_version,
            "appsec_rules": self.appsec_rules_version,
        }


class OpenTelemetryScenario(_DockerScenario):
    """ Scenario for testing opentelemetry"""

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
        return self.agent_container.agent_version if self.include_agent else Version("0.0.0", "agent")

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant


class PerformanceScenario(EndToEndScenario):
    def __init__(self, name, doc) -> None:
        super().__init__(name, doc=doc, appsec_enabled=self.appsec_enabled, use_proxy=False)

    @property
    def appsec_enabled(self):
        return os.environ.get("DD_APPSEC_ENABLED") == "true"

    @property
    def host_log_folder(self):
        return "logs_with_appsec" if self.appsec_enabled else "logs_without_appsec"

    def _get_warmups(self):
        result = super()._get_warmups()
        result.append(self._extra_weblog_warmup)

        return result

    def _extra_weblog_warmup(self):
        from utils import weblog

        WARMUP_REQUEST_COUNT = 10
        WARMUP_LAST_SLEEP_DURATION = 3

        for _ in range(WARMUP_REQUEST_COUNT):
            weblog.warmup_request(timeout=10)
            time.sleep(0.6)

        time.sleep(WARMUP_LAST_SLEEP_DURATION)


class OnBoardingScenario(_Scenario):
    def __init__(self, name, doc) -> None:
        super().__init__(name, doc=doc)
        self.stack = None
        self.provision_vms = []
        self.provision_vm_names = []
        self.onboarding_components = {}
        self.onboarding_tests_metadata = {}

    def configure(self, config):
        super().configure(config)
        self._library = LibraryVersion(config.option.obd_library, "0.0")
        self._env = config.option.obd_env
        self._weblog = config.option.obd_weblog
        self.provision_vms = list(
            ProvisionMatrix(
                ProvisionFilter(self.name, language=self._library.library, env=self._env, weblog=self._weblog)
            ).get_infrastructure_provision()
        )
        self.provision_vm_names = [vm.name for vm in self.provision_vms]

    @property
    def components(self):
        return self.onboarding_components

    @property
    def parametrized_tests_metadata(self):
        return self.onboarding_tests_metadata

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog

    def fill_context(self):
        # fix package name for nodejs -> js
        if self._library.library == "nodejs":
            package_lang = "datadog-apm-library-js"
        else:
            package_lang = f"datadog-apm-library-{self._library.library}"

        dd_package_names = ["agent", "datadog-apm-inject", package_lang]

        try:
            for provision_vm in self.provision_vms:
                # Manage common dd software components for the scenario if it's not a skipped test
                if provision_vm.pytestmark is None:
                    for dd_package_name in dd_package_names:
                        # All the tested machines should have the same version of the DD components
                        if dd_package_name in self.onboarding_components and self.onboarding_components[
                            dd_package_name
                        ] != provision_vm.get_component(dd_package_name):
                            self.onboarding_components["NO_VALID_ONBOARDING_COMPONENTS"] = "ERROR"
                            raise ValueError(
                                f"TEST_NO_VALID: All the tested machines should have the same version of the DD components. Package: [{dd_package_name}] Versions: [{self.onboarding_components[dd_package_name]}]-[{provision_vm.get_component(dd_package_name)}]"
                            )

                        self.onboarding_components[dd_package_name] = provision_vm.get_component(dd_package_name)
                # Manage specific information for each parametrized test
                test_metadata = {
                    "vm": provision_vm.ec2_data["name"],
                    "vm_ip": provision_vm.ip,
                    "vm_ami": provision_vm.ec2_data["ami_id"],
                    "vm_distro": provision_vm.ec2_data["os_distro"],
                    "docker": provision_vm.get_component("docker"),
                    "lang_variant": provision_vm.language_variant_install_data["name"],
                }
                self.onboarding_tests_metadata[provision_vm.name] = test_metadata

        except Exception as ex:
            logger.error("Error filling the context components")
            logger.exception(ex)

    def extract_debug_info_before_close(self):
        """ Extract debug info for each machine before shutdown. We connect to machines using ssh"""
        from utils.onboarding.debug_vm import debug_info_ssh
        from utils.onboarding.pulumi_ssh import PulumiSSH

        for provision_vm in self.provision_vms:
            if provision_vm.pytestmark is None:
                debug_info_ssh(
                    provision_vm.name,
                    provision_vm.ip,
                    provision_vm.ec2_data["user"],
                    PulumiSSH.pem_file,
                    self.host_log_folder,
                )

    def _start_pulumi(self):
        from pulumi import automation as auto
        from utils.onboarding.pulumi_ssh import PulumiSSH

        def pulumi_start_program():
            # Static loading of keypairs for ec2 machines
            PulumiSSH.load()
            for provision_vm in self.provision_vms:
                logger.info(f"Executing warmup {provision_vm.name}")
                provision_vm.start()

        project_name = "system-tests-onboarding"
        stack_name = "testing_v2"

        try:
            self.stack = auto.create_or_select_stack(
                stack_name=stack_name, project_name=project_name, program=pulumi_start_program
            )
            self.stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
            up_res = self.stack.up(on_output=logger.info)
        except Exception as pulumi_exception:  #
            logger.error("Exception launching onboarding provision infraestructure")
            logger.exception(pulumi_exception)

    def _get_warmups(self):
        return [self._start_pulumi]

    def post_setup(self):
        """ Fill context with the installed components information and parametrized test metadata"""
        self.fill_context()

    def pytest_sessionfinish(self, session):
        logger.info(f"Closing onboarding scenario")
        self.extract_debug_info_before_close()
        self.close_targets()

    def close_targets(self):
        logger.info(f"Pulumi stack down")
        self.stack.destroy(on_output=logger.info)


class ParametricScenario(_Scenario):
    class PersistentParametricTestConf(dict):
        """ Parametric tests are executed in multiple thread, we need a mechanism to persist each parametrized_tests_metadata on a file"""

        def __init__(self, outer_inst):
            self.outer_inst = outer_inst
            # To handle correctly we need to add data by default
            self.update({"scenario": outer_inst.name})

        def __setitem__(self, item, value):
            super().__setitem__(item, value)
            # Append to the context file
            ctx_filename = f"{self.outer_inst.host_log_folder}/{os.environ.get('PYTEST_XDIST_WORKER')}_context.json"
            with open(ctx_filename, "a") as f:
                json.dump({item: value}, f)
                f.write(",")
                f.write(os.linesep)

        def deserialize(self):
            result = {}
            for ctx_filename in glob.glob(f"{self.outer_inst.host_log_folder}/*_context.json"):
                with open(ctx_filename, "r") as f:
                    fileContent = f.read()
                    # Remove last carriage return and the last comma. Wrap into json array.
                    all_params = json.loads(f"[{fileContent[:-2]}]")
                    # Change from array to unique dict
                    for d in all_params:
                        result.update(d)
            return result

    def __init__(self, name, doc) -> None:
        super().__init__(name, doc=doc)
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config):
        super().configure(config)
        assert "TEST_LIBRARY" in os.environ

        # get tracer version info building and executing the ddtracer-version.docker file
        parametric_appdir = os.path.join("utils", "build", "docker", os.getenv("TEST_LIBRARY"), "parametric")
        tracer_version_dockerfile = os.path.join(parametric_appdir, "ddtracer_version.Dockerfile")
        if os.path.isfile(tracer_version_dockerfile):
            try:
                subprocess.run(
                    [
                        "docker",
                        "build",
                        ".",
                        "-t",
                        "ddtracer_version",
                        "-f",
                        f"{tracer_version_dockerfile}",
                        "--quiet",
                    ],
                    stdout=subprocess.DEVNULL,
                    # stderr=subprocess.DEVNULL,
                    check=True,
                )
                result = subprocess.run(
                    ["docker", "run", "--rm", "-t", "ddtracer_version"],
                    cwd=parametric_appdir,
                    stdout=subprocess.PIPE,
                    check=False,
                )
                self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), result.stdout.decode("utf-8"))
            except subprocess.CalledProcessError as e:
                logger.error(f"{e}")
                raise RuntimeError(e)
        else:
            self._library = LibraryVersion(os.getenv("TEST_LIBRARY", "**not-set**"), "99999.99999.99999")
        logger.stdout(f"Library: {self.library}")

    def print_test_context(self):
        super().print_test_context()

        logger.stdout(f"Library: {self.library}")

    @property
    def library(self):
        return self._library


class scenarios:
    todo = _Scenario("TODO", doc="scenario that skips tests not yet executed")
    test_the_test = TestTheTestScenario("TEST_THE_TEST", doc="Small scenario that check system-tests internals")
    mock_the_test = TestTheTestScenario("MOCK_THE_TEST", doc="Mock scenario that check system-tests internals")

    default = EndToEndScenario(
        "DEFAULT",
        weblog_env={"DD_DBM_PROPAGATION_MODE": "service"},
        include_postgres_db=True,
        doc="Default scenario, spawn tracer, the Postgres databases and agent, and run most of exisiting tests",
    )

    # performance scenario just spawn an agent and a weblog, and spies the CPU and mem usage
    performances = PerformanceScenario(
        "PERFORMANCES", doc="A not very used scenario : its aim is to measure CPU and MEM usage across a basic run"
    )

    integrations = EndToEndScenario(
        "INTEGRATIONS",
        weblog_env={"DD_DBM_PROPAGATION_MODE": "full", "DD_TRACE_SPAN_ATTRIBUTE_SCHEMA": "v1"},
        include_postgres_db=True,
        include_cassandra_db=True,
        include_mongo_db=True,
        include_kafka=True,
        include_rabbitmq=True,
        include_mysql_db=True,
        include_sqlserver=True,
        doc="Spawns tracer, agent, and a full set of database. Test the intgrations of those databases with tracers",
    )

    crossed_tracing_libraries = EndToEndScenario(
        "CROSSED_TRACING_LIBRARIES",
        weblog_env={"DD_TRACE_API_VERSION": "v0.4"},
        include_kafka=True,
        include_buddies=True,
        include_localstack=True,
        doc="Spawns a buddy for each supported language of APM",
    )

    otel_integrations = OpenTelemetryScenario(
        "OTEL_INTEGRATIONS",
        weblog_env={
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://proxy:8126",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
        },
        include_intake=False,
        include_collector=False,
        include_postgres_db=True,
        include_cassandra_db=True,
        include_mongo_db=True,
        include_kafka=True,
        include_rabbitmq=True,
        include_mysql_db=True,
        include_sqlserver=True,
        doc="We use the open telemetry library to automatically instrument the weblogs instead of using the DD library. This scenario represents this case in the integration with different external systems, for example the interaction with sql database.",
    )

    profiling = EndToEndScenario(
        "PROFILING",
        library_interface_timeout=160,
        agent_interface_timeout=160,
        weblog_env={
            "DD_PROFILING_ENABLED": "true",
            "DD_PROFILING_UPLOAD_PERIOD": "10",
            "DD_PROFILING_START_DELAY": "1",
            # Reduce noise
            "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
        },
        doc="Test profiling feature. Not included in default scenario because is quite slow",
    )

    sampling = EndToEndScenario(
        "SAMPLING",
        tracer_sampling_rate=0.5,
        doc="Test sampling mechanism. Not included in default scenario because is very slow, and flaky",
    )

    trace_propagation_style_w3c = EndToEndScenario(
        "TRACE_PROPAGATION_STYLE_W3C",
        weblog_env={"DD_TRACE_PROPAGATION_STYLE_INJECT": "W3C", "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "W3C",},
        doc="Test W3C trace style",
    )

    # Telemetry scenarios
    telemetry_dependency_loaded_test_for_dependency_collection_disabled = EndToEndScenario(
        "TELEMETRY_DEPENDENCY_LOADED_TEST_FOR_DEPENDENCY_COLLECTION_DISABLED",
        weblog_env={"DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED": "false"},
        doc="Test DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED=false effect on tracers",
    )

    telemetry_app_started_products_disabled = EndToEndScenario(
        "TELEMETRY_APP_STARTED_PRODUCTS_DISABLED",
        weblog_env={
            "DD_APPSEC_ENABLED": "false",
            "DD_PROFILING_ENABLED": "false",
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "false",
        },
        appsec_enabled=False,
        doc="Disable all tracers products",
    )

    telemetry_log_generation_disabled = EndToEndScenario(
        "TELEMETRY_LOG_GENERATION_DISABLED",
        weblog_env={"DD_TELEMETRY_LOGS_COLLECTION_ENABLED": "false",},
        doc="Test env var `DD_TELEMETRY_LOGS_COLLECTION_ENABLED=false`",
    )
    telemetry_metric_generation_disabled = EndToEndScenario(
        "TELEMETRY_METRIC_GENERATION_DISABLED",
        weblog_env={"DD_TELEMETRY_METRICS_ENABLED": "false",},
        doc="Test env var `DD_TELEMETRY_METRICS_ENABLED=false`",
    )
    telemetry_metric_generation_enabled = EndToEndScenario(
        "TELEMETRY_METRIC_GENERATION_ENABLED",
        weblog_env={"DD_TELEMETRY_METRICS_ENABLED": "true",},
        doc="Test env var `DD_TELEMETRY_METRICS_ENABLED=true`",
    )

    # ASM scenarios
    appsec_missing_rules = EndToEndScenario(
        "APPSEC_MISSING_RULES", appsec_rules="/donotexists", doc="Test missing appsec rules file"
    )
    appsec_corrupted_rules = EndToEndScenario(
        "APPSEC_CORRUPTED_RULES", appsec_rules="/appsec_corrupted_rules.yml", doc="Test corrupted appsec rules file"
    )
    appsec_custom_rules = EndToEndScenario(
        "APPSEC_CUSTOM_RULES", appsec_rules="/appsec_custom_rules.json", doc="Test custom appsec rules file"
    )
    appsec_blocking = EndToEndScenario(
        "APPSEC_BLOCKING", appsec_rules="/appsec_blocking_rule.json", doc="Misc tests for appsec blocking"
    )
    appsec_rules_monitoring_with_errors = EndToEndScenario(
        "APPSEC_RULES_MONITORING_WITH_ERRORS",
        appsec_rules="/appsec_custom_rules_with_errors.json",
        doc="Appsec rule file with some errors",
    )
    appsec_disabled = EndToEndScenario(
        "APPSEC_DISABLED",
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_DBM_PROPAGATION_MODE": "disabled"},
        appsec_enabled=False,
        include_postgres_db=True,
        doc="Disable appsec and test DBM setting integration outcome when disabled",
    )
    appsec_low_waf_timeout = EndToEndScenario(
        "APPSEC_LOW_WAF_TIMEOUT", weblog_env={"DD_APPSEC_WAF_TIMEOUT": "1"}, doc="Appsec with a very low WAF timeout"
    )
    appsec_custom_obfuscation = EndToEndScenario(
        "APPSEC_CUSTOM_OBFUSCATION",
        weblog_env={
            "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
            "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
        },
        doc="Test custom appsec obfuscation parameters",
    )
    appsec_rate_limiter = EndToEndScenario(
        "APPSEC_RATE_LIMITER",
        weblog_env={"DD_APPSEC_TRACE_RATE_LIMIT": "1"},
        doc="Tests with a low rate trace limit for Appsec",
    )

    appsec_waf_telemetry = EndToEndScenario(
        "APPSEC_WAF_TELEMETRY",
        weblog_env={
            "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "true",
            "DD_TELEMETRY_METRICS_ENABLED": "true",
            "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
        },
        doc="Enable Telemetry feature for WAF",
    )

    appsec_blocking_full_denylist = EndToEndScenario(
        "APPSEC_BLOCKING_FULL_DENYLIST",
        proxy_state={"mock_remote_config_backend": "ASM_DATA_FULL_DENYLIST"},
        weblog_env={"DD_APPSEC_RULES": None},
        doc="""
            The spec says that if  DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, whem remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
    )

    appsec_request_blocking = EndToEndScenario(
        "APPSEC_REQUEST_BLOCKING",
        proxy_state={"mock_remote_config_backend": "ASM"},
        weblog_env={"DD_APPSEC_RULES": None},
        doc="",
    )

    appsec_runtime_activation = EndToEndScenario(
        "APPSEC_RUNTIME_ACTIVATION",
        proxy_state={"mock_remote_config_backend": "ASM_ACTIVATE_ONLY"},
        appsec_enabled=False,
        weblog_env={
            "DD_RC_TARGETS_KEY_ID": "TEST_KEY_ID",
            "DD_RC_TARGETS_KEY": "1def0961206a759b09ccdf2e622be20edf6e27141070e7b164b7e16e96cf402c",
            "DD_REMOTE_CONFIG_INTEGRITY_CHECK_ENABLED": "true",
        },
        doc="",
    )

    appsec_api_security = EndToEndScenario(
        "APPSEC_API_SECURITY",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_TRACE_DEBUG": "false",
            "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
        },
        doc="""
        Scenario for API Security feature, testing schema types sent into span tags if
        DD_EXPERIMENTAL_API_SECURITY_ENABLED is set to true.
        """,
    )

    appsec_auto_events_extended = EndToEndScenario(
        "APPSEC_AUTO_EVENTS_EXTENDED",
        weblog_env={"DD_APPSEC_ENABLED": "true", "DD_APPSEC_AUTOMATED_USER_EVENTS_TRACKING": "extended"},
        appsec_enabled=True,
        doc="Scenario for checking extended mode in automatic user events",
    )

    # Remote config scenarios
    # library timeout is set to 100 seconds
    # default polling interval for tracers is very low (5 seconds)
    # TODO configure the polling interval to a lower value instead of increasing the timeout

    remote_config_mocked_backend_asm_features = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
        proxy_state={"mock_remote_config_backend": "ASM_FEATURES"},
        appsec_enabled=False,
        weblog_env={"DD_REMOTE_CONFIGURATION_ENABLED": "true"},
        library_interface_timeout=100,
        doc="",
    )

    remote_config_mocked_backend_live_debugging = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
        proxy_state={"mock_remote_config_backend": "LIVE_DEBUGGING"},
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_INTERNAL_RCM_POLL_INTERVAL": "1000",
        },
        library_interface_timeout=100,
        doc="",
    )

    remote_config_mocked_backend_asm_dd = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
        proxy_state={"mock_remote_config_backend": "ASM_DD"},
        weblog_env={"DD_APPSEC_RULES": None},
        library_interface_timeout=100,
        doc="""
            The spec says that if DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, whem remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_FEATURES_NOCACHE"},
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        library_interface_timeout=100,
        doc="",
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_FEATURES_NOCACHE"},
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        library_interface_timeout=100,
        doc="",
    )

    remote_config_mocked_backend_live_debugging_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE",
        proxy_state={"mock_remote_config_backend": "LIVE_DEBUGGING_NOCACHE"},
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
        },
        library_interface_timeout=100,
        doc="",
    )

    remote_config_mocked_backend_asm_dd_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_DD_NOCACHE"},
        library_interface_timeout=100,
        doc="",
    )

    # APM tracing end-to-end scenarios

    apm_tracing_e2e = EndToEndScenario("APM_TRACING_E2E", backend_interface_timeout=5, doc="")
    apm_tracing_e2e_otel = EndToEndScenario(
        "APM_TRACING_E2E_OTEL", weblog_env={"DD_TRACE_OTEL_ENABLED": "true",}, backend_interface_timeout=5, doc="",
    )
    apm_tracing_e2e_single_span = EndToEndScenario(
        "APM_TRACING_E2E_SINGLE_SPAN",
        weblog_env={
            "DD_SPAN_SAMPLING_RULES": '[{"service": "weblog", "name": "*single_span_submitted", "sample_rate": 1.0, "max_per_second": 50}]',
            "DD_TRACE_SAMPLE_RATE": "0",
        },
        backend_interface_timeout=5,
        doc="",
    )

    otel_tracing_e2e = OpenTelemetryScenario("OTEL_TRACING_E2E", doc="")
    otel_metric_e2e = OpenTelemetryScenario("OTEL_METRIC_E2E", include_intake=False, doc="")
    otel_log_e2e = OpenTelemetryScenario("OTEL_LOG_E2E", include_intake=False, doc="")

    library_conf_custom_header_tags = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADER_TAGS",
        additional_trace_header_tags=(VALID_CONFIGS),
        doc="Scenario with custom headers to be used with DD_TRACE_HEADER_TAGS",
    )
    library_conf_custom_header_tags_invalid = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADER_TAGS_INVALID",
        additional_trace_header_tags=(INVALID_CONFIGS),
        doc="Scenario with custom headers for DD_TRACE_HEADER_TAGS that libraries should reject",
    )

    parametric = ParametricScenario("PARAMETRIC", doc="WIP")

    # Onboarding scenarios: name of scenario will be the sufix for yml provision file name (tests/onboarding/infra_provision)
    onboarding_host_install_manual = OnBoardingScenario("ONBOARDING_HOST_INSTALL_MANUAL", doc="")
    onboarding_container_install_manual = OnBoardingScenario("ONBOARDING_CONTAINER_INSTALL_MANUAL", doc="")
    onboarding_host_install_script = OnBoardingScenario("ONBOARDING_HOST_INSTALL_SCRIPT", doc="")
    onboarding_container_install_script = OnBoardingScenario("ONBOARDING_CONTAINER_INSTALL_SCRIPT", doc="")
    # Onboarding uninstall scenario: first install onboarding, the uninstall dd injection software
    onboarding_host_uninstall = OnBoardingScenario("ONBOARDING_HOST_UNINSTALL", doc="")
    onboarding_container_uninstall = OnBoardingScenario("ONBOARDING_CONTAINER_UNINSTALL", doc="")

    debugger_probes_status = EndToEndScenario(
        "DEBUGGER_PROBES_STATUS",
        proxy_state={"mock_remote_config_backend": "DEBUGGER_PROBES_STATUS"},
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_INTERNAL_RCM_POLL_INTERVAL": "2000",
            "DD_DEBUGGER_DIAGNOSTICS_INTERVAL": "1",
        },
        library_interface_timeout=100,
        doc="Test scenario for checking if method probe statuses can be successfully 'RECEIVED' and 'INSTALLED'",
    )

    debugger_method_probes_snapshot = EndToEndScenario(
        "DEBUGGER_METHOD_PROBES_SNAPSHOT",
        proxy_state={"mock_remote_config_backend": "DEBUGGER_METHOD_PROBES_SNAPSHOT"},
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=30,
        doc="Test scenario for checking if debugger successfully generates snapshots for specific method probes",
    )

    debugger_line_probes_snapshot = EndToEndScenario(
        "DEBUGGER_LINE_PROBES_SNAPSHOT",
        proxy_state={"mock_remote_config_backend": "DEBUGGER_LINE_PROBES_SNAPSHOT"},
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=30,
        doc="Test scenario for checking if debugger successfully generates snapshots for specific line probes",
    )

    debugger_mix_log_probe = EndToEndScenario(
        "DEBUGGER_MIX_LOG_PROBE",
        proxy_state={"mock_remote_config_backend": "DEBUGGER_MIX_LOG_PROBE"},
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=5,
        doc="Set both method and line probes at the same code",
    )

    fuzzer = _DockerScenario("_FUZZER", doc="Fake scenario for fuzzing (launch without pytest)")


def _main():
    for name in dir(scenarios):
        if not name.startswith("_"):
            scenario = getattr(scenarios, name)
            print(scenario.doc)


if __name__ == "__main__":
    _main()

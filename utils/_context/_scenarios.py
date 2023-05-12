from logging import FileHandler
import os
from pathlib import Path
import shutil
import time

import pytest
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from utils._context.library_version import LibraryVersion

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
    OpenTelemetryCollectorContainer,
    create_network,
)

from utils.tools import logger, get_log_formatter, update_environ_with_local_env

update_environ_with_local_env()


class _Scenario:
    def __init__(self, name) -> None:
        self.name = name
        self.terminal = None
        self.replay = False

    def create_log_subfolder(self, subfolder):
        if self.replay:
            return

        path = os.path.join(self.host_log_folder, subfolder)

        shutil.rmtree(path, ignore_errors=True)
        Path(path).mkdir(parents=True, exist_ok=True)

    def __call__(self, test_method):
        # handles @scenarios.scenario_name
        pytest.mark.scenario(self.name)(test_method)

        return test_method

    def configure(self, replay):
        self.replay = replay
        self.create_log_subfolder("")

        handler = FileHandler(f"{self.host_log_folder}/tests.log", encoding="utf-8")
        handler.setFormatter(get_log_formatter())

        logger.addHandler(handler)

        if replay:
            from utils import weblog

            weblog.init_replay_mode(self.host_log_folder)

    def session_start(self, session):
        """ called at the very begning of the process """

        self.terminal = session.config.pluginmanager.get_plugin("terminalreporter")
        self.print_test_context()

        if self.replay:
            return

        self.print_info("Executing warmups...")

        try:
            for warmup in self._get_warmups():
                logger.info(f"Executing warmup {warmup}")
                warmup()
        except:
            self.collect_logs()
            self.close_targets()
            raise

    def print_test_context(self):
        self.terminal.write_sep("=", "test context", bold=True)
        self.print_info(f"Scenario: {self.name}")
        self.print_info(f"Logs folder: ./{self.host_log_folder}")

    def print_info(self, info):
        """ print info in stdout """
        logger.info(info)
        if self.terminal is not None:
            self.terminal.write_line(info)

    def _get_warmups(self):
        return []

    def post_setup(self):
        """ called after test setup """

    def collect_logs(self):
        """ Called after setup """

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

    def get_junit_properties(self):
        return {"dd_tags[systest.suite.context.scenario]": self.name}

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"


class TestTheTestScenario(_Scenario):
    @property
    def host_log_folder(self):
        return "logs"

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
        use_proxy=True,
        proxy_state=None,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
        include_kafka=False,
        include_rabbitmq=False,
        include_mysql_db=False,
    ) -> None:
        super().__init__(name)

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

    def configure(self, replay):
        super().configure(replay)

        for container in reversed(self._required_containers):
            container.configure(replay)

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

    def collect_logs(self):

        for container in self._required_containers:
            try:
                container.save_logs()
            except:
                logger.exception(f"Fail to save logs for container {container}")


class EndToEndScenario(_DockerScenario):
    """ Scenario that implier an instrumented HTTP application shipping a datadog tracer (weblog) and an datadog agent """

    def __init__(
        self,
        name,
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
    ) -> None:
        super().__init__(
            name,
            use_proxy=use_proxy,
            proxy_state=proxy_state,
            include_postgres_db=include_postgres_db,
            include_cassandra_db=include_cassandra_db,
            include_mongo_db=include_mongo_db,
            include_kafka=include_kafka,
            include_rabbitmq=include_rabbitmq,
            include_mysql_db=include_mysql_db,
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

        self.agent_interface_timeout = agent_interface_timeout
        self.backend_interface_timeout = backend_interface_timeout
        self.library_interface_timeout = library_interface_timeout

    def configure(self, replay):
        from utils import interfaces

        super().configure(replay)
        interfaces.library_stdout.configure()

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

    def print_test_context(self):
        from utils import weblog

        super().print_test_context()

        logger.debug(f"Docker host is {weblog.domain}")

        self.print_info(f"Library: {self.library}")
        self.print_info(f"Agent: {self.agent_version}")

        if self.library == "php":
            self.print_info(f"AppSec: {self.weblog_container.php_appsec}")

        if self.weblog_container.libddwaf_version:
            self.print_info(f"libddwaf: {self.weblog_container.libddwaf_version}")

        if self.weblog_container.appsec_rules_file:
            self.print_info(f"AppSec rules version: {self.weblog_container.appsec_rules_version}")

        if self.weblog_container.uds_mode:
            self.print_info(f"UDS socket: {self.weblog_container.uds_socket}")

        self.print_info(f"Weblog variant: {self.weblog_container.weblog_variant}")
        self.print_info(f"Backend: {self.agent_container.dd_site}")

    def _create_interface_folders(self):
        for interface in ("agent", "library", "backend"):
            self.create_log_subfolder(f"interfaces/{interface}")

    def _start_interface_watchdog(self):
        from utils import interfaces

        class Event(FileSystemEventHandler):
            def __init__(self, interface) -> None:
                super().__init__()
                self.interface = interface

            def on_modified(self, event):
                if event.is_directory:
                    return

                self.interface.ingest_file(event.src_path)

        observer = Observer()
        observer.schedule(Event(interfaces.library), path=f"{self.host_log_folder}/interfaces/library", recursive=True)
        observer.schedule(Event(interfaces.agent), path=f"{self.host_log_folder}/interfaces/agent", recursive=True)

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

            if not interfaces.agent.ready.wait(40):
                raise Exception("Datadog agent not ready")
            logger.debug("Agent ready")

    def post_setup(self):
        from utils import interfaces

        if self.replay:
            interfaces.library.load_data_from_logs(f"{self.host_log_folder}/interfaces/library")
            interfaces.agent.load_data_from_logs(f"{self.host_log_folder}/interfaces/agent")
            interfaces.backend.load_data_from_logs(f"{self.host_log_folder}/interfaces/backend")
            return

        if self.use_proxy:
            self._wait_interface(interfaces.library, self.library_interface_timeout)
            self._wait_interface(interfaces.agent, self.agent_interface_timeout)
            self._wait_interface(interfaces.backend, self.backend_interface_timeout)

            self.collect_logs()

            self._wait_interface(interfaces.library_stdout, 0)
            self._wait_interface(interfaces.library_dotnet_managed, 0)
            self._wait_interface(interfaces.agent_stdout, 0)
        else:
            self.collect_logs()

        self.close_targets()

    def _wait_interface(self, interface, timeout):
        self.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        self.terminal.flush()

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


class OpenTelemetryScenario(_DockerScenario):
    """ Scenario for testing opentelemetry"""

    def __init__(self, name) -> None:
        super().__init__(name, use_proxy=True)

        self.agent_container = AgentContainer(host_log_folder=self.host_log_folder, use_proxy=True)
        self.weblog_container = WeblogContainer(self.host_log_folder)
        self.collector_container = OpenTelemetryCollectorContainer(self.host_log_folder)
        self._required_containers.append(self.agent_container)
        self._required_containers.append(self.weblog_container)
        self._required_containers.append(self.collector_container)

    def configure(self, replay):
        super().configure(replay)
        self._check_env_vars()
        dd_site = os.environ.get("DD_SITE", "datad0g.com")
        self.weblog_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_2")
        self.weblog_container.environment["DD_SITE"] = dd_site
        self.collector_container.environment["DD_API_KEY"] = os.environ.get("DD_API_KEY_3")
        self.collector_container.environment["DD_SITE"] = dd_site

    def _create_interface_folders(self):
        for interface in ("open_telemetry", "backend", "agent"):
            self.create_log_subfolder(f"interfaces/{interface}")

    def _start_interface_watchdog(self):
        from utils import interfaces

        class Event(FileSystemEventHandler):
            def __init__(self, interface) -> None:
                super().__init__()
                self.interface = interface

            def on_modified(self, event):
                if event.is_directory:
                    return

                self.interface.ingest_file(event.src_path)

        observer = Observer()
        observer.schedule(
            Event(interfaces.open_telemetry), path=f"{self.host_log_folder}/interfaces/open_telemetry", recursive=True
        )

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

            self.collect_logs()

            self._wait_interface(interfaces.library_stdout, 0)
            self._wait_interface(interfaces.library_dotnet_managed, 0)
        else:
            self.collect_logs()

    def _wait_interface(self, interface, timeout):
        self.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        self.terminal.flush()

        interface.wait(timeout)

    def _check_env_vars(self):
        for env in ["DD_API_KEY", "DD_APP_KEY", "DD_API_KEY_2", "DD_APP_KEY_2", "DD_API_KEY_3", "DD_APP_KEY_3"]:
            if env not in os.environ:
                raise Exception(f"Please set {env}, OTel E2E test requires 3 API keys and 3 APP keys")

    @property
    def library(self):
        return LibraryVersion("open_telemetry", "0.0.0")

    @property
    def agent_version(self):
        return self.agent_container.agent_version

    @property
    def weblog_variant(self):
        return self.weblog_container.weblog_variant


class CgroupScenario(EndToEndScenario):

    # cgroup test
    # require a dedicated warmup. Need to check the stability before
    # merging it into the default scenario

    def _get_warmups(self):
        warmups = super()._get_warmups()
        warmups.append(self._wait_for_weblog_cgroup_file)
        return warmups

    def _wait_for_weblog_cgroup_file(self):
        max_attempts = 10  # each attempt = 1 second
        attempt = 0

        filename = f"{self.host_log_folder}/docker/weblog/logs/weblog.cgroup"
        while attempt < max_attempts and not os.path.exists(filename):

            logger.debug(f"{filename} is missing, wait")
            time.sleep(1)
            attempt += 1

        if attempt == max_attempts:
            pytest.exit("Failed to access cgroup file from weblog container", 1)

        return True


class PerformanceScenario(EndToEndScenario):
    """ A not very used scenario : its aim is to measure CPU and MEM usage across a basic run"""

    def __init__(self, name) -> None:
        super().__init__(name, appsec_enabled=self.appsec_enabled, use_proxy=False)

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
        import requests

        WARMUP_REQUEST_COUNT = 10
        WARMUP_LAST_SLEEP_DURATION = 3

        for _ in range(WARMUP_REQUEST_COUNT):
            requests.get("http://localhost:7777", timeout=10)
            time.sleep(0.6)

        time.sleep(WARMUP_LAST_SLEEP_DURATION)


class scenarios:
    empty_scenario = _Scenario("EMPTY_SCENARIO")
    todo = _Scenario("TODO")  # scenario that skips tests not yest executed
    test_the_test = TestTheTestScenario("TEST_THE_TEST")

    default = EndToEndScenario("DEFAULT", include_postgres_db=True)
    cgroup = CgroupScenario("CGROUP")
    sleep = EndToEndScenario("SLEEP")

    # performance scenario just spawn an agent and a weblog, and spies the CPU and mem usage
    performances = PerformanceScenario("PERFORMANCES")

    integrations = EndToEndScenario(
        "INTEGRATIONS",
        weblog_env={"DD_DBM_PROPAGATION_MODE": "full"},
        include_postgres_db=True,
        include_cassandra_db=True,
        include_mongo_db=True,
        include_kafka=True,
        include_rabbitmq=True,
        include_mysql_db=True,
    )

    profiling = EndToEndScenario("PROFILING", library_interface_timeout=160, agent_interface_timeout=160)

    sampling = EndToEndScenario("SAMPLING", tracer_sampling_rate=0.5)

    trace_propagation_style_w3c = EndToEndScenario(
        "TRACE_PROPAGATION_STYLE_W3C",
        weblog_env={"DD_TRACE_PROPAGATION_STYLE_INJECT": "W3C", "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "W3C",},
    )
    # Telemetry scenarios
    telemetry_dependency_loaded_test_for_dependency_collection_disabled = EndToEndScenario(
        "TELEMETRY_DEPENDENCY_LOADED_TEST_FOR_DEPENDENCY_COLLECTION_DISABLED",
        weblog_env={"DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED": "false"},
    )
    telemetry_app_started_products_disabled = EndToEndScenario(
        "TELEMETRY_APP_STARTED_PRODUCTS_DISABLED",
        weblog_env={
            "DD_APPSEC_ENABLED": "false",
            "DD_PROFILING_ENABLED": "false",
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "false",
        },
    )
    telemetry_message_batch_event_order = EndToEndScenario(
        "TELEMETRY_MESSAGE_BATCH_EVENT_ORDER", weblog_env={"DD_FORCE_BATCHING_ENABLE": "true"}
    )
    telemetry_log_generation_disabled = EndToEndScenario(
        "TELEMETRY_LOG_GENERATION_DISABLED", weblog_env={"DD_TELEMETRY_LOGS_COLLECTION_ENABLED": "false",},
    )
    telemetry_metric_generation_disabled = EndToEndScenario(
        "TELEMETRY_METRIC_GENERATION_DISABLED", weblog_env={"DD_TELEMETRY_METRICS_COLLECTION_ENABLED": "false",},
    )

    # ASM scenarios
    appsec_missing_rules = EndToEndScenario("APPSEC_MISSING_RULES", appsec_rules="/donotexists")
    appsec_corrupted_rules = EndToEndScenario("APPSEC_CORRUPTED_RULES", appsec_rules="/appsec_corrupted_rules.yml")
    appsec_custom_rules = EndToEndScenario("APPSEC_CUSTOM_RULES", appsec_rules="/appsec_custom_rules.json")
    appsec_blocking = EndToEndScenario("APPSEC_BLOCKING", appsec_rules="/appsec_blocking_rule.json")
    appsec_rules_monitoring_with_errors = EndToEndScenario(
        "APPSEC_RULES_MONITORING_WITH_ERRORS", appsec_rules="/appsec_custom_rules_with_errors.json"
    )
    appsec_disabled = EndToEndScenario(
        "APPSEC_DISABLED", weblog_env={"DD_APPSEC_ENABLED": "false"}, appsec_enabled=False
    )
    appsec_low_waf_timeout = EndToEndScenario("APPSEC_LOW_WAF_TIMEOUT", weblog_env={"DD_APPSEC_WAF_TIMEOUT": "1"})
    appsec_custom_obfuscation = EndToEndScenario(
        "APPSEC_CUSTOM_OBFUSCATION",
        weblog_env={
            "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
            "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
        },
    )
    appsec_rate_limiter = EndToEndScenario("APPSEC_RATE_LIMITER", weblog_env={"DD_APPSEC_TRACE_RATE_LIMIT": "1"})

    appsec_waf_telemetry = EndToEndScenario(
        "APPSEC_WAF_TELEMETRY",
        weblog_env={
            "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "true",
            "DD_TELEMETRY_METRICS_ENABLED": "true",
            # Python lib has different env var until we enable Telemetry Metrics by default
            "_DD_TELEMETRY_METRICS_ENABLED": "true",
            "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
        },
    )
    # The spec says that if  DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
    # In this scenario, we use remote config. By the spec, whem remote config is available, rules file embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the data coming from remote config).
    # So, we set  DD_APPSEC_RULES to None to enable loading rules from remote config.
    # and it's okay not testing custom rule set for dev mode, as in this scenario, rules are always coming from remote config.
    appsec_ip_blocking = EndToEndScenario(
        "APPSEC_IP_BLOCKING",
        proxy_state={"mock_remote_config_backend": "ASM_DATA"},
        weblog_env={"DD_APPSEC_RULES": None},
    )
    appsec_ip_blocking_maxed = EndToEndScenario(
        "APPSEC_IP_BLOCKING_MAXED",
        proxy_state={"mock_remote_config_backend": "ASM_DATA_IP_BLOCKING_MAXED"},
        weblog_env={"DD_APPSEC_RULES": None},
    )

    appsec_request_blocking = EndToEndScenario(
        "APPSEC_REQUEST_BLOCKING",
        proxy_state={"mock_remote_config_backend": "ASM"},
        weblog_env={"DD_APPSEC_RULES": None},
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
    )

    # The spec says that if  DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
    # In this scenario, we use remote config. By the spec, whem remote config is available, rules file embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the data coming from remote config).
    # So, we set  DD_APPSEC_RULES to None to enable loading rules from remote config.
    # and it's okay not testing custom rule set for dev mode, as in this scenario, rules are always coming from remote config.
    remote_config_mocked_backend_asm_dd = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
        proxy_state={"mock_remote_config_backend": "ASM_DD"},
        weblog_env={"DD_APPSEC_RULES": None},
        library_interface_timeout=100,
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_FEATURES_NO_CACHE"},
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        library_interface_timeout=100,
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_FEATURES_NO_CACHE"},
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        library_interface_timeout=100,
    )

    remote_config_mocked_backend_live_debugging_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE",
        proxy_state={"mock_remote_config_backend": "LIVE_DEBUGGING_NO_CACHE"},
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
        },
        library_interface_timeout=100,
    )

    remote_config_mocked_backend_asm_dd_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
        proxy_state={"mock_remote_config_backend": "ASM_DD_NO_CACHE"},
        library_interface_timeout=100,
    )

    # APM tracing end-to-end scenarios
    apm_tracing_e2e = EndToEndScenario("APM_TRACING_E2E", backend_interface_timeout=5)
    apm_tracing_e2e_single_span = EndToEndScenario(
        "APM_TRACING_E2E_SINGLE_SPAN",
        weblog_env={
            "DD_SPAN_SAMPLING_RULES": '[{"service": "weblog", "name": "*single_span_submitted", "sample_rate": 1.0, "max_per_second": 50}]',
            "DD_TRACE_SAMPLE_RATE": "0",
        },
        backend_interface_timeout=5,
    )

    otel_tracing_e2e = OpenTelemetryScenario("OTEL_TRACING_E2E")

    library_conf_custom_headers_short = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADERS_SHORT", additional_trace_header_tags=("header-tag1", "header-tag2")
    )
    library_conf_custom_headers_long = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADERS_LONG",
        additional_trace_header_tags=("header-tag1:custom.header-tag1", "header-tag2:custom.header-tag2"),
    )


if __name__ == "__main__":
    for name in dir(scenarios):
        if not name.startswith("_"):
            scenario = getattr(scenarios, name)
            print(scenario.name)

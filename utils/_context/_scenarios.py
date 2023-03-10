import os
import time
import pytest

from utils._context.containers import TestedContainer, WeblogContainer, AgentContainer
from utils._context.library_version import LibraryVersion
from utils.tools import logger


class _Scenario:
    def __init__(self, name, use_interfaces=False, proxy_state=None) -> None:
        self.name = name
        self.proxy_state = proxy_state
        self.use_interfaces = use_interfaces

    def __call__(self, test_method):
        # handles @scenarios.scenario_name
        pytest.mark.scenario(self.name)(test_method)

        return test_method

    def session_start(self, session):
        # called at the very begning of the process
        pass

    def _get_warmups(self):
        return []

    def execute_warmups(self):
        """ Called before any setup """

        for warmup in self._get_warmups():
            logger.info(f"Executing warmup {warmup}")
            warmup()

    def collect_logs(self):
        """ Called after setup """

    def close_targets(self):
        """ Called after setup """

    @property
    def host_log_folder(self):
        return "logs" if self.name == "DEFAULT" else f"logs_{self.name.lower()}"

    @property
    def library(self):
        return None

    @property
    def agent_version(self):
        return None

    @property
    def weblog_variant(self):
        return None

    @property
    def php_appsec(self):
        return None

    def get_junit_properties(self):
        return {"dd_tags[systest.suite.context.scenario]": self.name}

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"


class TestTheTestScenario(_Scenario):
    @property
    def library(self):
        return LibraryVersion("java", "0.66.0")

    @property
    def weblog_variant(self):
        return "spring"


class EndToEndScenario(_Scenario):
    """ Scenario that implier an instrumented HTTP application shipping a tracer (weblog) and an agent """

    def __init__(
        self,
        name,
        weblog_env=None,
        proxy_state=None,
        tracer_sampling_rate=None,
        appsec_rules=None,
        appsec_enabled=True,
        additional_trace_header_tags=(),
        library_interface_timeout=None,
        agent_interface_timeout=None,
        backend_interface_timeout=0,
        include_postgres_db=False,
        include_cassandra_db=False,
        include_mongo_db=False,
    ) -> None:
        super().__init__(name, use_interfaces=True)

        self.agent_container = AgentContainer()
        self.weblog_container = WeblogContainer(
            self.host_log_folder,
            environment=weblog_env,
            tracer_sampling_rate=tracer_sampling_rate,
            appsec_rules=appsec_rules,
            appsec_enabled=appsec_enabled,
            additional_trace_header_tags=additional_trace_header_tags,
        )
        self.proxy_state = proxy_state
        self.include_postgres_db = include_postgres_db

        self.weblog_container.environment["SYSTEMTESTS_SCENARIO"] = self.name

        self._required_containers = []

        if include_postgres_db:
            self._required_containers.append(
                TestedContainer(
                    image_name="postgres:latest",
                    name="postgres",
                    user="postgres",
                    environment={"POSTGRES_PASSWORD": "password", "PGPORT": "5433"},
                    volumes={
                        "./utils/build/docker/postgres-init-db.sh": {
                            "bind": "/docker-entrypoint-initdb.d/init_db.sh",
                            "mode": "ro",
                        }
                    },
                )
            )

        if include_mongo_db:
            self._required_containers.append(
                TestedContainer(image_name="mongo:latest", name="mongodb", allow_old_container=True)
            )
        if include_cassandra_db:
            self._required_containers.append(
                TestedContainer(image_name="cassandra:latest", name="cassandra_db", allow_old_container=True)
            )

        if agent_interface_timeout is None:
            self.agent_interface_timeout = 5
        else:
            self.agent_interface_timeout = agent_interface_timeout

        self.backend_interface_timeout = backend_interface_timeout

        if library_interface_timeout is not None:
            self.library_interface_timeout = library_interface_timeout
        else:
            if self.weblog_container.library == "java":
                self.library_interface_timeout = 80
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

    def session_start(self, session):
        # called at the very begning of the process
        terminal = session.config.pluginmanager.get_plugin("terminalreporter")

        def print_info(info):
            logger.debug(info)
            terminal.write_line(info)

        terminal.write_sep("=", "Tested components", bold=True)
        print_info(f"Library: {self.library}")
        print_info(f"Agent: {self.agent_version}")
        if self.library == "php":
            print_info(f"AppSec: {self.weblog_container.php_appsec}")

        if self.weblog_container.libddwaf_version:
            print_info(f"libddwaf: {self.weblog_container.libddwaf_version}")

        if self.weblog_container.appsec_rules_file:
            print_info(f"AppSec rules version: {self.weblog_container.appsec_rules_version}")

        if self.weblog_container.uds_mode:
            print_info(f"UDS socket: {self.weblog_container.uds_socket}")

        print_info(f"Weblog variant: {self.weblog_container.weblog_variant}")
        print_info(f"Backend: {self.agent_container.dd_site}")
        print_info(f"Scenario: {self.name}")

    def _get_warmups(self):
        from utils.proxy.core import start_proxy  # prevent circular import

        warmups = [lambda: start_proxy(self.proxy_state)]

        for container in self._required_containers:
            warmups.append(container.start)

        warmups += [
            self.agent_container.start,
            self.weblog_container.start,
            EndToEndScenario._wait_for_app_readiness,
        ]

        return warmups

    @staticmethod
    def _wait_for_app_readiness():
        from utils import interfaces  # import here to avoid circular import

        logger.debug("Wait for app readiness")

        if not interfaces.library.ready.wait(40):
            pytest.exit("Library not ready", 1)
        logger.debug("Library ready")

        if not interfaces.agent.ready.wait(40):
            pytest.exit("Datadog agent not ready", 1)
        logger.debug("Agent ready")

    def collect_logs(self):
        try:
            self.agent_container.save_logs()
            self.weblog_container.save_logs()
        except:
            logger.exception("Fail to save logs")

    def close_targets(self):
        self.agent_container.remove()
        self.weblog_container.remove()

        for container in self._required_containers:
            container.remove()

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


class CgroupScenario(EndToEndScenario):

    # cgroup test
    # require a dedicated warmup. Need to check the stability before
    # merging it into the default scenario

    def _get_warmups(self):
        warmups = super()._get_warmups()
        warmups.append(CgroupScenario._wait_for_weblog_cgroup_file)
        return warmups

    @staticmethod
    def _wait_for_weblog_cgroup_file():
        max_attempts = 10  # each attempt = 1 second
        attempt = 0

        while attempt < max_attempts and not os.path.exists("logs/docker/weblog/logs/weblog.cgroup"):

            logger.debug("logs/docker/weblog/logs/weblog.cgroup is missing, wait")
            time.sleep(1)
            attempt += 1

        if attempt == max_attempts:
            pytest.exit("Failed to access cgroup file from weblog container", 1)

        return True


class scenarios:
    empty_scenario = _Scenario("EMPTY_SCENARIO")
    todo = _Scenario("TODO")  # scenario that skips tests not yest executed
    test_the_test = TestTheTestScenario("TEST_THE_TEST")

    default = EndToEndScenario("DEFAULT", include_postgres_db=True)
    cgroup = CgroupScenario("CGROUP")
    custom = EndToEndScenario("CUSTOM")
    sleep = EndToEndScenario("SLEEP")

    # scenario for weblog arch that does not support Appsec
    appsec_unsupported = EndToEndScenario("APPSEC_UNSUPORTED")

    integrations = EndToEndScenario(
        "INTEGRATIONS",
        weblog_env={"DD_DBM_PROPAGATION_MODE": "full"},
        include_postgres_db=True,
        include_cassandra_db=True,
        include_mongo_db=True,
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

    # Telemetry scenarios
    telemetry_message_batch_event_order = EndToEndScenario(
        "TELEMETRY_MESSAGE_BATCH_EVENT_ORDER", weblog_env={"DD_FORCE_BATCHING_ENABLE": "true"}
    )

    # ASM scenarios
    appsec_missing_rules = EndToEndScenario("APPSEC_MISSING_RULES", appsec_rules="/donotexists")
    appsec_corrupted_rules = EndToEndScenario("APPSEC_CORRUPTED_RULES", appsec_rules="/appsec_corrupted_rules.yml")
    appsec_custom_rules = EndToEndScenario("APPSEC_CUSTOM_RULES", appsec_rules="/appsec_custom_rules.json")
    appsec_blocking = EndToEndScenario("APPSEC_BLOCKING", appsec_rules="/appsec_blocking_rule.json")
    appsec_rules_monitoring_with_errors = EndToEndScenario(
        "APPSEC_RULES_MONITORING_WITH_ERRORS", appsec_rules="/appsec_custom_rules_with_errors.json"
    )
    appsec_disabled = EndToEndScenario("APPSEC_DISABLED", weblog_env={"DD_APPSEC_ENABLED": "false"})
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
        weblog_env={"DD_INSTRUMENTATION_TELEMETRY_ENABLED": "true", "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0"},
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

    library_conf_custom_headers_short = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADERS_SHORT", additional_trace_header_tags=("header-tag1", "header-tag2")
    )
    library_conf_custom_headers_long = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADERS_LONG",
        additional_trace_header_tags=("header-tag1:custom.header-tag1", "header-tag2:custom.header-tag2"),
    )


current_scenario_name = os.environ.get("SYSTEMTESTS_SCENARIO", "EMPTY_SCENARIO").lower()

if not hasattr(scenarios, current_scenario_name):
    raise ValueError(f"Scenario {current_scenario_name} does not exists")

current_scenario = getattr(scenarios, current_scenario_name)
logger.info(f"Current scenario is {current_scenario}")

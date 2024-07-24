import os
import json

import pytest
from utils._context.library_version import LibraryVersion

from utils._context.header_tag_vars import VALID_CONFIGS, INVALID_CONFIGS

from utils._context.containers import (
    create_network,
    # SqlDbTestedContainer,
    APMTestAgentContainer,
    WeblogInjectionInitContainer,
    MountInjectionVolume,
    create_inject_volume,
    TestedContainer,
)
from utils.tools import logger, update_environ_with_local_env

from .core import Scenario, ScenarioGroup, DockerScenario, EndToEndScenario
from .open_telemetry import OpenTelemetryScenario
from .parametric import ParametricScenario
from .performance import PerformanceScenario
from .test_the_test import TestTheTestScenario
from .auto_injection import InstallerAutoInjectionScenario

update_environ_with_local_env()


class _KubernetesScenario(Scenario):
    """ DEPRECATED: Replaced by Kubernetes Scenario. 
        Scenario that tests kubernetes lib injection"""

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

    def configure(self, config):
        super().configure(config)

        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY is not set"
        assert "WEBLOG_VARIANT" in os.environ, "WEBLOG_VARIANT is not set"
        assert (
            "DOCKER_IMAGE_TAG" in os.environ
        ), "DOCKER_IMAGE_TAG is not set. Select tag for the lang inject init image: latest, local, latest_snapshot or a specific version"
        assert (
            "DOCKER_REGISTRY_IMAGES_PATH" in os.environ
        ), "DOCKER_REGISTRY_IMAGES_PATH is not set. IE: ghcr.io/datadog"

        prefix_library_injection_init_image, library_injection_init_image = self._get_library_injection_init_image()
        library_injection_test_app_image = self._get_library_injection_test_app_image()

        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")
        self._weblog_variant = os.getenv("WEBLOG_VARIANT")
        self._weblog_variant_image = library_injection_test_app_image
        self._prefix_library_init_image = prefix_library_injection_init_image
        self._library_init_image = library_injection_init_image
        self._library_init_image_tag = os.getenv("DOCKER_IMAGE_TAG")

        logger.stdout("K8s Lib Injection environment:")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Weblog variant: {self._weblog_variant}")
        logger.stdout(f"Weblog variant image: {self._weblog_variant_image}")
        logger.stdout(f"Library init image: {self._library_init_image}")
        logger.stdout(f"Library init image tag: {self._library_init_image_tag}")

    def _get_library_injection_test_app_image(self):
        docker_registry_images_path = os.getenv("DOCKER_REGISTRY_IMAGES_PATH")
        library_injection_test_app_image = os.environ.get("LIBRARY_INJECTION_TEST_APP_IMAGE", None)
        if not library_injection_test_app_image:
            app_docker_image_repo = f"{docker_registry_images_path}/system-tests/{os.getenv('WEBLOG_VARIANT')}"
            if "DOCKER_IMAGE_WEBLOG_TAG" in os.environ:
                library_injection_test_app_image = (
                    f"{app_docker_image_repo}:{os.environ.get('DOCKER_IMAGE_WEBLOG_TAG')}"
                )
            else:
                library_injection_test_app_image = f"{app_docker_image_repo}:latest"
        return library_injection_test_app_image

    def _get_library_injection_init_image(self):
        test_library = os.getenv("TEST_LIBRARY")
        init_image_repo_alias = test_library
        init_image_alias = test_library
        if test_library == "nodejs":
            init_image_repo_alias = "js"
            init_image_alias = "js"
        elif test_library == "python":
            init_image_repo_alias = "py"
        elif test_library == "ruby":
            init_image_repo_alias = "rb"

        docker_image_tag = os.getenv("DOCKER_IMAGE_TAG")
        docker_registry_images_path = os.getenv("DOCKER_REGISTRY_IMAGES_PATH")

        init_docker_image_repo = ""
        prefix_init_docker_image_repo = ""
        if docker_image_tag == "latest":
            # Release version are published in docker.io
            init_docker_image_repo = f"docker.io/datadog/dd-lib-{init_image_alias}-init"
            prefix_init_docker_image_repo = f"docker.io/datadog"
        elif docker_image_tag == "local":
            # Docker hub doesn't allow multi level repo paths
            # TODO review this
            init_docker_image_repo = f"{docker_registry_images_path}/dd-lib-{init_image_alias}-init"
            prefix_init_docker_image_repo = f"{docker_registry_images_path}"
        else:
            init_docker_image_repo = (
                f"{docker_registry_images_path}/dd-trace-{init_image_repo_alias}/dd-lib-{init_image_alias}-init"
            )
            prefix_init_docker_image_repo = f"{docker_registry_images_path}/dd-trace-{init_image_repo_alias}"

        library_injection_init_image = f"{init_docker_image_repo}:{docker_image_tag}"
        return prefix_init_docker_image_repo, library_injection_init_image

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog_variant


class KubernetesScenario(Scenario):
    """ Scenario that tests kubernetes lib injection """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

    def configure(self, config):
        super().configure(config)

        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY is not set"
        assert "WEBLOG_VARIANT" in os.environ, "WEBLOG_VARIANT is not set"
        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE is not set. The init image to be tested is not set"
        assert (
            "LIBRARY_INJECTION_TEST_APP_IMAGE" in os.environ
        ), "LIBRARY_INJECTION_TEST_APP_IMAGE is not set. The test app image to be tested is not set"

        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")
        self._weblog_variant = os.getenv("WEBLOG_VARIANT")
        self._weblog_variant_image = os.getenv("LIBRARY_INJECTION_TEST_APP_IMAGE")
        self._library_init_image = os.getenv("LIB_INIT_IMAGE")

        logger.stdout("K8s Lib Injection environment:")
        logger.stdout(f"Library: {self._library}")
        logger.stdout(f"Weblog variant: {self._weblog_variant}")
        logger.stdout(f"Weblog variant image: {self._weblog_variant_image}")
        logger.stdout(f"Library init image: {self._library_init_image}")

        logger.info("K8s Lib Injection environment configured")

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return self._weblog_variant


class WeblogInjectionScenario(Scenario):
    """Scenario that runs APM test agent """

    def __init__(self, name, doc, github_workflow=None, scenario_groups=None) -> None:
        super().__init__(name, doc=doc, github_workflow=github_workflow, scenario_groups=scenario_groups)

        self._mount_injection_volume = MountInjectionVolume(
            host_log_folder=self.host_log_folder, name="volume-injector"
        )
        self._weblog_injection = WeblogInjectionInitContainer(host_log_folder=self.host_log_folder)

        self._required_containers: list(TestedContainer) = []
        self._required_containers.append(self._mount_injection_volume)
        self._required_containers.append(APMTestAgentContainer(host_log_folder=self.host_log_folder))
        self._required_containers.append(self._weblog_injection)

    def configure(self, config):
        assert "TEST_LIBRARY" in os.environ, "TEST_LIBRARY must be set: java,python,nodejs,dotnet,ruby"
        self._library = LibraryVersion(os.getenv("TEST_LIBRARY"), "0.0")

        assert "LIB_INIT_IMAGE" in os.environ, "LIB_INIT_IMAGE must be set"
        self._lib_init_image = os.getenv("LIB_INIT_IMAGE")

        self._mount_injection_volume._lib_init_image(self._lib_init_image)
        self._weblog_injection.set_environment_for_library(self.library)

        super().configure(config)

        for container in self._required_containers:
            container.configure(self.replay)

    def _get_warmups(self):
        warmups = super()._get_warmups()

        warmups.append(create_network)
        warmups.append(create_inject_volume)
        for container in self._required_containers:
            warmups.append(container.start)

        return warmups

    def pytest_sessionfinish(self, session):
        self.close_targets()

    def close_targets(self):
        for container in reversed(self._required_containers):
            try:
                container.remove()
                logger.info(f"Removing container {container}")
            except:
                logger.exception(f"Failed to remove container {container}")

    @property
    def library(self):
        return self._library

    @property
    def lib_init_image(self):
        return self._lib_init_image


class scenarios:
    @staticmethod
    def all_endtoend_scenarios(test_object):
        """particular use case where a klass applies on all scenarios"""

        # Check that no scenario has been already declared
        for marker in getattr(test_object, "pytestmark", []):
            if marker.name == "scenario":
                raise ValueError(f"Error on {test_object}: You can declare only one scenario")

        pytest.mark.scenario("EndToEndScenario")(test_object)

        return test_object

    todo = Scenario("TODO", doc="scenario that skips tests not yet executed", github_workflow=None)
    test_the_test = TestTheTestScenario("TEST_THE_TEST", doc="Small scenario that check system-tests internals")
    mock_the_test = TestTheTestScenario("MOCK_THE_TEST", doc="Mock scenario that check system-tests internals")

    default = EndToEndScenario(
        "DEFAULT",
        weblog_env={
            "DD_DBM_PROPAGATION_MODE": "service",
            "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
            "DD_TRACE_FEATURES": "discovery",
        },
        include_postgres_db=True,
        doc="Default scenario, spawn tracer, the Postgres databases and agent, and run most of exisiting tests",
    )

    # performance scenario just spawn an agent and a weblog, and spies the CPU and mem usage
    performances = PerformanceScenario(
        "PERFORMANCES", doc="A not very used scenario : its aim is to measure CPU and MEM usage across a basic run"
    )

    integrations = EndToEndScenario(
        "INTEGRATIONS",
        weblog_env={
            "DD_DBM_PROPAGATION_MODE": "full",
            "DD_TRACE_SPAN_ATTRIBUTE_SCHEMA": "v1",
            "AWS_ACCESS_KEY_ID": "my-access-key",
            "AWS_SECRET_ACCESS_KEY": "my-access-key",
        },
        include_postgres_db=True,
        include_cassandra_db=True,
        include_mongo_db=True,
        include_kafka=True,
        include_rabbitmq=True,
        include_mysql_db=True,
        include_sqlserver=True,
        include_elasticmq=True,
        include_localstack=True,
        doc="Spawns tracer, agent, and a full set of database. Test the intgrations of those databases with tracers",
        scenario_groups=[ScenarioGroup.INTEGRATIONS, ScenarioGroup.APPSEC],
    )

    crossed_tracing_libraries = EndToEndScenario(
        "CROSSED_TRACING_LIBRARIES",
        weblog_env={
            "DD_TRACE_API_VERSION": "v0.4",
            "AWS_ACCESS_KEY_ID": "my-access-key",
            "AWS_SECRET_ACCESS_KEY": "my-access-key",
        },
        include_kafka=True,
        include_buddies=True,
        include_elasticmq=True,
        include_localstack=True,
        include_rabbitmq=True,
        doc="Spawns a buddy for each supported language of APM",
        scenario_groups=[ScenarioGroup.INTEGRATIONS],
    )

    otel_integrations = OpenTelemetryScenario(
        "OTEL_INTEGRATIONS",
        weblog_env={
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://proxy:8126",
            "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            "OTEL_INTEGRATIONS_TEST": True,
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
        scenario_groups=[ScenarioGroup.PROFILING],
    )

    sampling = EndToEndScenario(
        "SAMPLING",
        tracer_sampling_rate=0.5,
        weblog_env={"DD_TRACE_RATE_LIMIT": "10000000"},
        doc="Test sampling mechanism. Not included in default scenario because it's a little bit too flaky",
        scenario_groups=[ScenarioGroup.SAMPLING],
    )

    trace_propagation_style_w3c = EndToEndScenario(
        "TRACE_PROPAGATION_STYLE_W3C",
        weblog_env={
            "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
            "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
        },
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
        "APPSEC_MISSING_RULES",
        appsec_rules="/donotexists",
        doc="Test missing appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_corrupted_rules = EndToEndScenario(
        "APPSEC_CORRUPTED_RULES",
        appsec_rules="/appsec_corrupted_rules.yml",
        doc="Test corrupted appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_custom_rules = EndToEndScenario(
        "APPSEC_CUSTOM_RULES",
        appsec_rules="/appsec_custom_rules.json",
        doc="Test custom appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_blocking = EndToEndScenario(
        "APPSEC_BLOCKING",
        appsec_rules="/appsec_blocking_rule.json",
        doc="Misc tests for appsec blocking",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    graphql_appsec = EndToEndScenario(
        "GRAPHQL_APPSEC",
        appsec_rules="/appsec_blocking_rule.json",
        doc="AppSec tests for GraphQL integrations",
        github_workflow="graphql",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_rules_monitoring_with_errors = EndToEndScenario(
        "APPSEC_RULES_MONITORING_WITH_ERRORS",
        appsec_rules="/appsec_custom_rules_with_errors.json",
        doc="Appsec rule file with some errors",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_disabled = EndToEndScenario(
        "APPSEC_DISABLED",
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_DBM_PROPAGATION_MODE": "disabled"},
        appsec_enabled=False,
        include_postgres_db=True,
        doc="Disable appsec and test DBM setting integration outcome when disabled",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_low_waf_timeout = EndToEndScenario(
        "APPSEC_LOW_WAF_TIMEOUT",
        weblog_env={"DD_APPSEC_WAF_TIMEOUT": "1"},
        doc="Appsec with a very low WAF timeout",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_custom_obfuscation = EndToEndScenario(
        "APPSEC_CUSTOM_OBFUSCATION",
        weblog_env={
            "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
            "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
        },
        doc="Test custom appsec obfuscation parameters",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_rate_limiter = EndToEndScenario(
        "APPSEC_RATE_LIMITER",
        weblog_env={"DD_APPSEC_TRACE_RATE_LIMIT": "1"},
        doc="Tests with a low rate trace limit for Appsec",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_waf_telemetry = EndToEndScenario(
        "APPSEC_WAF_TELEMETRY",
        weblog_env={
            "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "true",
            "DD_TELEMETRY_METRICS_ENABLED": "true",
            "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "2.0",
        },
        doc="Enable Telemetry feature for WAF",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_blocking_full_denylist = EndToEndScenario(
        "APPSEC_BLOCKING_FULL_DENYLIST",
        rc_api_enabled=True,
        weblog_env={"DD_APPSEC_RULES": None},
        doc="""
            The spec says that if  DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, whem remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_request_blocking = EndToEndScenario(
        "APPSEC_REQUEST_BLOCKING",
        rc_api_enabled=True,
        weblog_env={"DD_APPSEC_RULES": None},
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_runtime_activation = EndToEndScenario(
        "APPSEC_RUNTIME_ACTIVATION",
        rc_api_enabled=True,
        appsec_enabled=False,
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_api_security = EndToEndScenario(
        "APPSEC_API_SECURITY",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_API_SECURITY_ENABLED": "true",
            "DD_TRACE_DEBUG": "false",
            "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
            "DD_API_SECURITY_SAMPLE_DELAY": "0.0",
            "DD_API_SECURITY_MAX_CONCURRENT_REQUESTS": "50",
        },
        doc="""
        Scenario for API Security feature, testing schema types sent into span tags if
        DD_API_SECURITY_ENABLED is set to true.
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_api_security_rc = EndToEndScenario(
        "APPSEC_API_SECURITY_RC",
        weblog_env={"DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_SAMPLE_DELAY": "0.0",},
        rc_api_enabled=True,
        doc="""
            Scenario to test API Security Remote config
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_api_security_no_response_body = EndToEndScenario(
        "APPSEC_API_SECURITY_NO_RESPONSE_BODY",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_API_SECURITY_ENABLED": "true",
            "DD_TRACE_DEBUG": "false",
            "DD_API_SECURITY_REQUEST_SAMPLE_RATE": "1.0",
            "DD_API_SECURITY_MAX_CONCURRENT_REQUESTS": "50",
            "DD_API_SECURITY_PARSE_RESPONSE_BODY": "false",
        },
        doc="""
        Scenario for API Security feature, testing schema types sent into span tags if
        DD_API_SECURITY_ENABLED is set to true.
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_api_security_with_sampling = EndToEndScenario(
        "APPSEC_API_SECURITY_WITH_SAMPLING",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_API_SECURITY_ENABLED": "true",
            "DD_TRACE_DEBUG": "false",
        },
        doc="""
        Scenario for API Security feature, testing api security sampling rate.
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_auto_events_extended = EndToEndScenario(
        "APPSEC_AUTO_EVENTS_EXTENDED",
        weblog_env={
            "DD_APPSEC_ENABLED": "true",
            "DD_APPSEC_AUTOMATED_USER_EVENTS_TRACKING": "extended",
            "DD_APPSEC_AUTO_USER_INSTRUMENTATION_MODE": "anonymization",
        },
        appsec_enabled=True,
        doc="Scenario for checking extended mode in automatic user events",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_auto_events_rc = EndToEndScenario(
        "APPSEC_AUTO_EVENTS_RC",
        weblog_env={"DD_APPSEC_ENABLED": "true", "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": 0.5},
        rc_api_enabled=True,
        doc="""
            Scenario to test User ID collection config change via Remote config
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_standalone = EndToEndScenario(
        "APPSEC_STANDALONE",
        weblog_env={"DD_APPSEC_ENABLED": "true", "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true"},
        doc="Appsec standalone mode (APM opt out)",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    remote_config_mocked_backend_asm_features = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
        rc_api_enabled=True,
        appsec_enabled=False,
        weblog_env={"DD_REMOTE_CONFIGURATION_ENABLED": "true", "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",},
        library_interface_timeout=10,
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    remote_config_mocked_backend_live_debugging = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",
            "DD_INTERNAL_RCM_POLL_INTERVAL": "1000",
        },
        library_interface_timeout=10,
        doc="",
    )

    remote_config_mocked_backend_asm_dd = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
        rc_api_enabled=True,
        weblog_env={"DD_APPSEC_RULES": None, "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",},
        library_interface_timeout=10,
        doc="""
            The spec says that if DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, whem remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        rc_api_enabled=True,
        weblog_env={
            "DD_APPSEC_ENABLED": "false",
            "DD_REMOTE_CONFIGURATION_ENABLED": "true",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",
        },
        library_interface_timeout=10,
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    remote_config_mocked_backend_live_debugging_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",
        },
        library_interface_timeout=10,
        doc="",
    )

    remote_config_mocked_backend_asm_dd_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
        rc_api_enabled=True,
        weblog_env={"DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",},
        library_interface_timeout=10,
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
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
    otel_metric_e2e = OpenTelemetryScenario("OTEL_METRIC_E2E", doc="")
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

    debugger_probes_status = EndToEndScenario(
        "DEBUGGER_PROBES_STATUS",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_INTERNAL_RCM_POLL_INTERVAL": "2000",
            "DD_DEBUGGER_DIAGNOSTICS_INTERVAL": "1",
            "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.5",
        },
        library_interface_timeout=10,
        doc="Test scenario for checking if method probe statuses can be successfully 'RECEIVED' and 'INSTALLED'",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    debugger_method_probes_snapshot = EndToEndScenario(
        "DEBUGGER_METHOD_PROBES_SNAPSHOT",
        rc_api_enabled=True,
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=30,
        doc="Test scenario for checking if debugger successfully generates snapshots for specific method probes",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    debugger_line_probes_snapshot = EndToEndScenario(
        "DEBUGGER_LINE_PROBES_SNAPSHOT",
        rc_api_enabled=True,
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=30,
        doc="Test scenario for checking if debugger successfully generates snapshots for specific line probes",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    debugger_mix_log_probe = EndToEndScenario(
        "DEBUGGER_MIX_LOG_PROBE",
        rc_api_enabled=True,
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=5,
        doc="Set both method and line probes at the same code",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    debugger_pii_redaction = EndToEndScenario(
        "DEBUGGER_PII_REDACTION",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_DYNAMIC_INSTRUMENTATION_REDACTED_TYPES": "weblog.Models.Debugger.CustomPii,com.datadoghq.system_tests.springboot.CustomPii",
            "DD_DYNAMIC_INSTRUMENTATION_REDACTED_IDENTIFIERS": "customidentifier1,customidentifier2",
        },
        library_interface_timeout=5,
        doc="Check pii redaction",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    debugger_expression_language = EndToEndScenario(
        "DEBUGGER_EXPRESSION_LANGUAGE",
        rc_api_enabled=True,
        weblog_env={"DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1", "DD_REMOTE_CONFIG_ENABLED": "true",},
        library_interface_timeout=5,
        doc="Check expression language",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    fuzzer = DockerScenario("_FUZZER", doc="Fake scenario for fuzzing (launch without pytest)", github_workflow=None)

    # Single Step Instrumentation scenarios (HOST and CONTAINER)

    simple_installer_auto_injection = InstallerAutoInjectionScenario(
        "SIMPLE_INSTALLER_AUTO_INJECTION",
        "Onboarding Container Single Step Instrumentation scenario (minimal test scenario)",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    installer_auto_injection = InstallerAutoInjectionScenario(
        "INSTALLER_AUTO_INJECTION", doc="Installer auto injection scenario", scenario_groups=[ScenarioGroup.ONBOARDING]
    )

    installer_host_auto_injection_chaos = InstallerAutoInjectionScenario(
        "INSTALLER_HOST_AUTO_INJECTION_CHAOS",
        doc="Installer auto injection scenario with chaos (deleting installation folders, files)",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    installer_not_supported_auto_injection = InstallerAutoInjectionScenario(
        "INSTALLER_NOT_SUPPORTED_AUTO_INJECTION",
        "Onboarding host Single Step Instrumentation scenario for not supported languages",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    installer_auto_injection_block_list = InstallerAutoInjectionScenario(
        "INSTALLER_AUTO_INJECTION_BLOCK_LIST",
        "Onboarding Single Step Instrumentation scenario: Test user defined blocking lists",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    installer_auto_injection_ld_preload = InstallerAutoInjectionScenario(
        "INSTALLER_AUTO_INJECTION_LD_PRELOAD",
        "Onboarding Host Single Step Instrumentation scenario. Machines with previous ld.so.preload entries",
        vm_provision="auto-inject-ld-preload",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    simple_auto_injection_profiling = InstallerAutoInjectionScenario(
        "SIMPLE_AUTO_INJECTION_PROFILING",
        "Onboarding Single Step Instrumentation scenario with profiling activated by the app env var",
        app_env={
            "DD_PROFILING_ENABLED": "auto",
            "DD_PROFILING_UPLOAD_PERIOD": "10",
            "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500",
        },
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )
    host_auto_injection_install_script_profiling = InstallerAutoInjectionScenario(
        "HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING",
        "Onboarding Host Single Step Instrumentation scenario using agent auto install script with profiling activating by the installation process",
        vm_provision="host-auto-inject-install-script",
        agent_env={"DD_PROFILING_ENABLED": "auto"},
        app_env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"},
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    container_auto_injection_install_script_profiling = InstallerAutoInjectionScenario(
        "CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING",
        "Onboarding Container Single Step Instrumentation profiling scenario using agent auto install script",
        vm_provision="container-auto-inject-install-script",
        agent_env={"DD_PROFILING_ENABLED": "auto"},
        app_env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"},
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    host_auto_injection_install_script = InstallerAutoInjectionScenario(
        "HOST_AUTO_INJECTION_INSTALL_SCRIPT",
        "Onboarding Host Single Step Instrumentation scenario using agent auto install script",
        vm_provision="host-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    container_auto_injection_install_script = InstallerAutoInjectionScenario(
        "CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT",
        "Onboarding Container Single Step Instrumentation scenario using agent auto install script",
        vm_provision="container-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    local_auto_injection_install_script = InstallerAutoInjectionScenario(
        "LOCAL_AUTO_INJECTION_INSTALL_SCRIPT",
        "Tobe executed locally with krunvm. Installs all the software fron agent installation script, and the replace the apm-library with the uploaded tar file from binaries",
        vm_provision="local-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    ##DEPRECATED SCENARIOS: Delete after migration of tracer pipelines + auto_inject pipelines

    # Replaced by SIMPLE_INSTALLER_AUTO_INJECTION
    simple_host_auto_injection = InstallerAutoInjectionScenario(
        "SIMPLE_HOST_AUTO_INJECTION",
        "DEPRECATED: Onboarding Container Single Step Instrumentation scenario (minimal test scenario)",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )
    simple_container_auto_injection = InstallerAutoInjectionScenario(
        "SIMPLE_CONTAINER_AUTO_INJECTION",
        "DEPRECATED: Onboarding Container Single Step Instrumentation scenario (minimal test scenario)",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    # Replaced by SIMPLE_AUTO_INJECTION_PROFILING
    simple_host_auto_injection_profiling = InstallerAutoInjectionScenario(
        "SIMPLE_HOST_AUTO_INJECTION_PROFILING",
        "DEPRECATED: Onboarding Single Step Instrumentation scenario with profiling activated by the app env var",
        app_env={
            "DD_PROFILING_ENABLED": "auto",
            "DD_PROFILING_UPLOAD_PERIOD": "10",
            "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500",
        },
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )
    simple_container_auto_injection_profiling = InstallerAutoInjectionScenario(
        "SIMPLE_CONTAINER_AUTO_INJECTION_PROFILING",
        "DEPRECATED: Onboarding Single Step Instrumentation scenario with profiling activated by the app env var",
        app_env={
            "DD_PROFILING_ENABLED": "auto",
            "DD_PROFILING_UPLOAD_PERIOD": "10",
            "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500",
        },
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    # Replaced by INSTALLER_AUTO_INJECTION
    host_auto_injection = InstallerAutoInjectionScenario(
        "HOST_AUTO_INJECTION",
        doc="DEPRECATED: Installer auto injection scenario",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )
    container_auto_injection = InstallerAutoInjectionScenario(
        "CONTAINER_AUTO_INJECTION",
        doc="DEPRECATED: Installer auto injection scenario",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    # Replaced by INSTALLER_AUTO_INJECTION_BLOCK_LIST
    host_auto_injection_block_list = InstallerAutoInjectionScenario(
        "HOST_AUTO_INJECTION_BLOCK_LIST",
        "Onboarding Single Step Instrumentation scenario: Test user defined blocking lists",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    # Replaced by INSTALLER_NOT_SUPPORTED_AUTO_INJECTION
    container_not_supported_auto_injection = InstallerAutoInjectionScenario(
        "CONTAINER_NOT_SUPPORTED_AUTO_INJECTION",
        "Onboarding host Single Step Instrumentation scenario for not supported languages",
        scenario_groups=[ScenarioGroup.ONBOARDING],
    )

    # K8s LIB INJECTION SCENARIOS
    k8s_lib_injection_basic = _KubernetesScenario(
        "K8S_LIB_INJECTION_BASIC",
        doc=" Kubernetes Instrumentation basic scenario. DEPRECATED",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
    )
    k8s_library_injection_full = KubernetesScenario(
        "K8S_LIBRARY_INJECTION_FULL",
        doc=" Kubernetes Instrumentation complete scenario.",
        github_workflow="libinjection",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
    )

    k8s_library_injection_basic = KubernetesScenario(
        "K8S_LIBRARY_INJECTION_BASIC", doc=" Kubernetes Instrumentation basic scenario"
    )

    lib_injection_validation = WeblogInjectionScenario(
        "LIB_INJECTION_VALIDATION",
        doc="Validates the init images without kubernetes enviroment",
        github_workflow="libinjection",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
    )

    lib_injection_validation_unsupported_lang = WeblogInjectionScenario(
        "LIB_INJECTION_VALIDATION_UNSUPPORTED_LANG",
        doc="Validates the init images without kubernetes enviroment (unsupported lang versions)",
        github_workflow="libinjection",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
    )

    appsec_rasp = EndToEndScenario(
        "APPSEC_RASP",
        weblog_env={"DD_APPSEC_RASP_ENABLED": "true"},
        appsec_rules="/appsec_rasp_ruleset.json",
        doc="Enable APPSEC RASP",
        github_workflow="endtoend",
        scenario_groups=[ScenarioGroup.APPSEC],
    )


def get_all_scenarios() -> list[Scenario]:
    result = []
    for name in dir(scenarios):
        if not name.startswith("_"):
            scenario: Scenario = getattr(scenarios, name)
            if issubclass(scenario.__class__, Scenario):
                result.append(scenario)

    return result


def _main():
    data = {
        scenario.name: {
            "name": scenario.name,
            "doc": scenario.doc,
            "github_workflow": scenario.github_workflow,
            "scenario_groups": scenario.scenario_groups,
        }
        for scenario in get_all_scenarios()
    }

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    _main()

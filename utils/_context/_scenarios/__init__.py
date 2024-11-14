import os
import json

import pytest

from utils._context.header_tag_vars import VALID_CONFIGS, INVALID_CONFIGS
from utils.tools import update_environ_with_local_env

from .core import Scenario, ScenarioGroup
from .default import DefaultScenario
from .endtoend import DockerScenario, EndToEndScenario
from .integrations import CrossedTracingLibraryScenario, IntegrationsScenario, AWSIntegrationsScenario
from .open_telemetry import OpenTelemetryScenario
from .parametric import ParametricScenario
from .performance import PerformanceScenario
from .test_the_test import TestTheTestScenario
from .auto_injection import InstallerAutoInjectionScenario, InstallerAutoInjectionScenarioProfiling
from .k8s_lib_injection import KubernetesScenario, WeblogInjectionScenario
from .docker_ssi import DockerSSIScenario
from .external_processing import ExternalProcessingScenario

update_environ_with_local_env()


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

    default = DefaultScenario("DEFAULT")

    # performance scenario just spawn an agent and a weblog, and spies the CPU and mem usage
    performances = PerformanceScenario(
        "PERFORMANCES", doc="A not very used scenario : its aim is to measure CPU and MEM usage across a basic run"
    )
    integrations = IntegrationsScenario()
    integrations_aws = AWSIntegrationsScenario()
    crossed_tracing_libraries = CrossedTracingLibraryScenario()

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
            # Used within Spring Boot native tests to test profiling without affecting tracing scenarios
            "USE_NATIVE_PROFILING": "presence",
            # Reduce noise
            "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
        },
        doc="Test profiling feature. Not included in default scenario because is quite slow",
        scenario_groups=[ScenarioGroup.PROFILING],
        require_api_key=True,  # for an unknown reason, /flush on nodejs takes days with a fake key on this scenario
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
        scenario_groups=[ScenarioGroup.TELEMETRY],
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
        scenario_groups=[ScenarioGroup.TELEMETRY],
    )

    telemetry_log_generation_disabled = EndToEndScenario(
        "TELEMETRY_LOG_GENERATION_DISABLED",
        weblog_env={"DD_TELEMETRY_LOGS_COLLECTION_ENABLED": "false",},
        doc="Test env var `DD_TELEMETRY_LOGS_COLLECTION_ENABLED=false`",
        scenario_groups=[ScenarioGroup.TELEMETRY],
    )
    telemetry_metric_generation_disabled = EndToEndScenario(
        "TELEMETRY_METRIC_GENERATION_DISABLED",
        weblog_env={"DD_TELEMETRY_METRICS_ENABLED": "false",},
        doc="Test env var `DD_TELEMETRY_METRICS_ENABLED=false`",
        scenario_groups=[ScenarioGroup.TELEMETRY],
    )
    telemetry_metric_generation_enabled = EndToEndScenario(
        "TELEMETRY_METRIC_GENERATION_ENABLED",
        weblog_env={"DD_TELEMETRY_METRICS_ENABLED": "true",},
        doc="Test env var `DD_TELEMETRY_METRICS_ENABLED=true`",
        scenario_groups=[ScenarioGroup.TELEMETRY],
    )

    # ASM scenarios
    appsec_missing_rules = EndToEndScenario(
        "APPSEC_MISSING_RULES",
        weblog_env={"DD_APPSEC_RULES": "/donotexists"},
        doc="Test missing appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_corrupted_rules = EndToEndScenario(
        "APPSEC_CORRUPTED_RULES",
        weblog_env={"DD_APPSEC_RULES": "/appsec_corrupted_rules.yml"},
        doc="Test corrupted appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_custom_rules = EndToEndScenario(
        "APPSEC_CUSTOM_RULES",
        weblog_env={"DD_APPSEC_RULES": "/appsec_custom_rules.json"},
        weblog_volumes={"./tests/appsec/custom_rules.json": {"bind": "/appsec_custom_rules.json", "mode": "ro"}},
        doc="Test custom appsec rules file",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_blocking = EndToEndScenario(
        "APPSEC_BLOCKING",
        weblog_env={"DD_APPSEC_RULES": "/appsec_blocking_rule.json"},
        weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
        doc="Misc tests for appsec blocking",
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.ESSENTIALS],
    )
    graphql_appsec = EndToEndScenario(
        "GRAPHQL_APPSEC",
        weblog_env={"DD_APPSEC_RULES": "/appsec_blocking_rule.json"},
        weblog_volumes={"./tests/appsec/blocking_rule.json": {"bind": "/appsec_blocking_rule.json", "mode": "ro"}},
        doc="AppSec tests for GraphQL integrations",
        github_workflow="graphql",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    appsec_rules_monitoring_with_errors = EndToEndScenario(
        "APPSEC_RULES_MONITORING_WITH_ERRORS",
        weblog_env={"DD_APPSEC_RULES": "/appsec_custom_rules_with_errors.json"},
        weblog_volumes={
            "./tests/appsec/custom_rules_with_errors.json": {
                "bind": "/appsec_custom_rules_with_errors.json",
                "mode": "ro",
            }
        },
        doc="Appsec rule file with some errors",
        scenario_groups=[ScenarioGroup.APPSEC],
    )
    everything_disabled = EndToEndScenario(
        "EVERYTHING_DISABLED",
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
        weblog_env={"DD_APPSEC_TRACE_RATE_LIMIT": "1", "RAILS_MAX_THREADS": "1"},
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
        weblog_env={"DD_APPSEC_WAF_TIMEOUT": "10000000", "DD_APPSEC_TRACE_RATE_LIMIT": "10000"},  # 10 seconds
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    appsec_api_security = EndToEndScenario(
        "APPSEC_API_SECURITY",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_API_SECURITY_ENABLED": "true",
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
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.ESSENTIALS],
    )

    appsec_api_security_no_response_body = EndToEndScenario(
        "APPSEC_API_SECURITY_NO_RESPONSE_BODY",
        appsec_enabled=True,
        weblog_env={
            "DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true",
            "DD_API_SECURITY_ENABLED": "true",
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
        weblog_env={"DD_EXPERIMENTAL_API_SECURITY_ENABLED": "true", "DD_API_SECURITY_ENABLED": "true",},
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
        weblog_env={
            "DD_APPSEC_ENABLED": "true",
            "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
            "DD_IAST_ENABLED": "false",
        },
        doc="Appsec standalone mode (APM opt out)",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    iast_standalone = EndToEndScenario(
        "IAST_STANDALONE",
        weblog_env={
            "DD_APPSEC_ENABLED": "false",
            "DD_EXPERIMENTAL_APPSEC_STANDALONE_ENABLED": "true",
            "DD_IAST_ENABLED": "true",
            "DD_IAST_DETECTION_MODE": "FULL",
            "DD_IAST_DEDUPLICATION_ENABLED": "false",
            "DD_IAST_REQUEST_SAMPLING": "100",
        },
        doc="Source code vulnerability standalone mode (APM opt out)",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    remote_config_mocked_backend_asm_features = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES",
        rc_api_enabled=True,
        appsec_enabled=False,
        weblog_env={"DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.REMOTE_CONFIG, ScenarioGroup.ESSENTIALS],
    )

    remote_config_mocked_backend_live_debugging = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_INTERNAL_RCM_POLL_INTERVAL": "1000",
        },
        doc="",
        scenario_groups=[ScenarioGroup.REMOTE_CONFIG, ScenarioGroup.ESSENTIALS],
    )

    remote_config_mocked_backend_asm_dd = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD",
        rc_api_enabled=True,
        weblog_env={"DD_APPSEC_RULES": None,},
        doc="""
            The spec says that if DD_APPSEC_RULES is defined, then rules won't be loaded from remote config.
            In this scenario, we use remote config. By the spec, whem remote config is available, rules file
            embedded in the tracer will never be used (it will be the file defined in DD_APPSEC_RULES, or the
            data coming from remote config). So, we set  DD_APPSEC_RULES to None to enable loading rules from
            remote config. And it's okay not testing custom rule set for dev mode, as in this scenario, rules
            are always coming from remote config.
        """,
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.REMOTE_CONFIG, ScenarioGroup.ESSENTIALS],
    )

    remote_config_mocked_backend_asm_features_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE",
        rc_api_enabled=True,
        weblog_env={"DD_APPSEC_ENABLED": "false", "DD_REMOTE_CONFIGURATION_ENABLED": "true",},
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.REMOTE_CONFIG],
    )

    remote_config_mocked_backend_live_debugging_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_DEBUGGER_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
        },
        doc="",
        scenario_groups=[ScenarioGroup.REMOTE_CONFIG],
    )

    remote_config_mocked_backend_asm_dd_nocache = EndToEndScenario(
        "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE",
        rc_api_enabled=True,
        doc="",
        scenario_groups=[ScenarioGroup.APPSEC, ScenarioGroup.REMOTE_CONFIG],
    )

    # APM tracing end-to-end scenarios

    apm_tracing_e2e = EndToEndScenario("APM_TRACING_E2E", backend_interface_timeout=5, doc="")
    apm_tracing_e2e_otel = EndToEndScenario(
        "APM_TRACING_E2E_OTEL",
        weblog_env={"DD_TRACE_OTEL_ENABLED": "true",},
        backend_interface_timeout=5,
        require_api_key=True,
        doc="",
    )
    apm_tracing_e2e_single_span = EndToEndScenario(
        "APM_TRACING_E2E_SINGLE_SPAN",
        weblog_env={
            "DD_SPAN_SAMPLING_RULES": '[{"service": "weblog", "name": "*single_span_submitted", "sample_rate": 1.0, "max_per_second": 50}]',
            "DD_TRACE_SAMPLE_RATE": "0",
        },
        backend_interface_timeout=5,
        require_api_key=True,
        doc="",
    )

    otel_tracing_e2e = OpenTelemetryScenario("OTEL_TRACING_E2E", require_api_key=True, doc="")
    otel_metric_e2e = OpenTelemetryScenario("OTEL_METRIC_E2E", require_api_key=True, doc="")
    otel_log_e2e = OpenTelemetryScenario("OTEL_LOG_E2E", require_api_key=True, doc="")

    library_conf_custom_header_tags = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADER_TAGS",
        additional_trace_header_tags=(VALID_CONFIGS),
        rc_api_enabled=True,
        doc="Scenario with custom headers to be used with DD_TRACE_HEADER_TAGS",
    )
    library_conf_custom_header_tags_invalid = EndToEndScenario(
        "LIBRARY_CONF_CUSTOM_HEADER_TAGS_INVALID",
        additional_trace_header_tags=(INVALID_CONFIGS),
        doc="Scenario with custom headers for DD_TRACE_HEADER_TAGS that libraries should reject",
    )

    tracing_config_empty = EndToEndScenario("TRACING_CONFIG_EMPTY", weblog_env={}, doc="",)

    tracing_config_nondefault = EndToEndScenario(
        "TRACING_CONFIG_NONDEFAULT",
        weblog_env={
            "DD_TRACE_HTTP_SERVER_ERROR_STATUSES": "200-201,202",
            "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": r"ssn=\d{3}-\d{2}-\d{4}",
            "DD_TRACE_CLIENT_IP_ENABLED": "true",
            # disable ASM to test non asm client ip tagging
            "DD_APPSEC_ENABLED": "false",
            "DD_TRACE_HTTP_CLIENT_ERROR_STATUSES": "200-201,202",
            "DD_SERVICE": "service_test",
            "DD_TRACE_KAFKA_ENABLED": "false",  # Using Kafka as is the most common endpoint and integration(missing for PHP).
            "DD_TRACE_KAFKAJS_ENABLED": "false",  # In Node the integration is kafkajs.
            "DD_TRACE_PDO_ENABLED": "false",  # Use PDO for PHP,
        },
        include_kafka=True,
        include_postgres_db=True,
        doc="",
        scenario_groups=[ScenarioGroup.TRACING_CONFIG, ScenarioGroup.ESSENTIALS],
    )

    tracing_config_nondefault_2 = EndToEndScenario(
        "TRACING_CONFIG_NONDEFAULT_2",
        weblog_env={
            "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "",
            "DD_TRACE_KAFKA_ENABLED": "true",
            "DD_TRACE_KAFKAJS_ENABLED": "true",
            "DD_TRACE_PDO_ENABLED": "true",  # Use PDO for PHP
            "DD_TRACE_CLIENT_IP_HEADER": "custom-ip-header",
            "DD_TRACE_CLIENT_IP_ENABLED": "true",
        },
        include_kafka=True,
        include_postgres_db=True,
        doc="Test tracer configuration when a collection of non-default settings are applied",
        scenario_groups=[ScenarioGroup.TRACING_CONFIG],
    )
    tracing_config_nondefault_3 = EndToEndScenario(
        "TRACING_CONFIG_NONDEFAULT_3",
        weblog_env={"DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING": "false"},
        doc="",
        scenario_groups=[ScenarioGroup.TRACING_CONFIG],
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
        },
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
            "DD_DYNAMIC_INSTRUMENTATION_REDACTED_TYPES": "weblog.Models.Debugger.CustomPii,com.datadoghq.system_tests.springboot.CustomPii,CustomPii",
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

    debugger_exception_replay = EndToEndScenario(
        "DEBUGGER_EXCEPTION_REPLAY",
        rc_api_enabled=True,
        weblog_env={
            "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "1",
            "DD_REMOTE_CONFIG_ENABLED": "true",
            "DD_EXCEPTION_REPLAY_ENABLED": "true",
            "DD_EXCEPTION_DEBUGGING_ENABLED": "true",
        },
        library_interface_timeout=5,
        doc="Check exception replay",
        scenario_groups=[ScenarioGroup.DEBUGGER],
    )

    fuzzer = DockerScenario("_FUZZER", doc="Fake scenario for fuzzing (launch without pytest)", github_workflow=None)

    # Single Step Instrumentation scenarios (HOST and CONTAINER)

    simple_installer_auto_injection = InstallerAutoInjectionScenario(
        "SIMPLE_INSTALLER_AUTO_INJECTION",
        "Onboarding Container Single Step Instrumentation scenario (minimal test scenario)",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    installer_auto_injection = InstallerAutoInjectionScenario(
        "INSTALLER_AUTO_INJECTION",
        doc="Installer auto injection scenario",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    installer_not_supported_auto_injection = InstallerAutoInjectionScenario(
        "INSTALLER_NOT_SUPPORTED_AUTO_INJECTION",
        "Onboarding host Single Step Instrumentation scenario for not supported languages",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    chaos_installer_auto_injection = InstallerAutoInjectionScenario(
        "CHAOS_INSTALLER_AUTO_INJECTION",
        " Onboarding Host Single Step Instrumentation scenario. Machines with previous ld.so.preload entries. Perform chaos testing",
        vm_provision="auto-inject-ld-preload",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    simple_auto_injection_profiling = InstallerAutoInjectionScenarioProfiling(
        "SIMPLE_AUTO_INJECTION_PROFILING",
        "Onboarding Single Step Instrumentation scenario with profiling activated by the app env var",
        app_env={
            "DD_PROFILING_ENABLED": "auto",
            "DD_PROFILING_UPLOAD_PERIOD": "10",
            "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500",
        },
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )
    host_auto_injection_install_script_profiling = InstallerAutoInjectionScenarioProfiling(
        "HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING",
        "Onboarding Host Single Step Instrumentation scenario using agent auto install script with profiling activating by the installation process",
        vm_provision="host-auto-inject-install-script",
        agent_env={"DD_PROFILING_ENABLED": "auto"},
        app_env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"},
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    container_auto_injection_install_script_profiling = InstallerAutoInjectionScenarioProfiling(
        "CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING",
        "Onboarding Container Single Step Instrumentation profiling scenario using agent auto install script",
        vm_provision="container-auto-inject-install-script",
        agent_env={"DD_PROFILING_ENABLED": "auto"},
        app_env={"DD_PROFILING_UPLOAD_PERIOD": "10", "DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD": "1500"},
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    host_auto_injection_install_script = InstallerAutoInjectionScenario(
        "HOST_AUTO_INJECTION_INSTALL_SCRIPT",
        "Onboarding Host Single Step Instrumentation scenario using agent auto install script",
        vm_provision="host-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    container_auto_injection_install_script = InstallerAutoInjectionScenario(
        "CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT",
        "Onboarding Container Single Step Instrumentation scenario using agent auto install script",
        vm_provision="container-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    local_auto_injection_install_script = InstallerAutoInjectionScenario(
        "LOCAL_AUTO_INJECTION_INSTALL_SCRIPT",
        "Tobe executed locally with krunvm. Installs all the software fron agent installation script, and the replace the apm-library with the uploaded tar file from binaries",
        vm_provision="local-auto-inject-install-script",
        scenario_groups=[ScenarioGroup.ONBOARDING],
        github_workflow="libinjection",
    )

    k8s_library_injection_basic = KubernetesScenario(
        "K8S_LIBRARY_INJECTION_BASIC",
        doc=" Kubernetes Instrumentation basic scenario",
        github_workflow="libinjection",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
    )

    k8s_library_injection_profiling = KubernetesScenario(
        "K8S_LIBRARY_INJECTION_PROFILING",
        doc=" Kubernetes auto instrumentation, profiling activation",
        github_workflow="libinjection",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.LIB_INJECTION],
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

    docker_ssi = DockerSSIScenario(
        "DOCKER_SSI",
        doc="Validates the installer and the ssi on a docker environment",
        scenario_groups=[ScenarioGroup.ALL, ScenarioGroup.DOCKER_SSI],
    )

    appsec_rasp = EndToEndScenario(
        "APPSEC_RASP",
        weblog_env={"DD_APPSEC_RASP_ENABLED": "true", "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json"},
        weblog_volumes={"./tests/appsec/rasp/rasp_ruleset.json": {"bind": "/appsec_rasp_ruleset.json", "mode": "ro"}},
        doc="Enable APPSEC RASP",
        github_workflow="endtoend",
        scenario_groups=[ScenarioGroup.APPSEC],
    )

    external_processing = ExternalProcessingScenario("EXTERNAL_PROCESSING")


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

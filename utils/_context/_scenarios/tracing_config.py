from ._core import DdTraceEndToEndScenario, scenario_groups
from utils._context.containers import KafkaContainer
from utils._context.containers import PostgresContainer
from utils._context.header_tag_vars import CONFIG_WILDCARD
from utils._context.header_tag_vars import INVALID_CONFIGS
from utils._context.header_tag_vars import VALID_CONFIGS


class TracePropagationStyleW3c(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACE_PROPAGATION_STYLE_W3C",
            weblog_env={
                "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
            },
            doc="Test W3C trace style",
        )


class LibraryConfCustomHeaderTags(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "LIBRARY_CONF_CUSTOM_HEADER_TAGS",
            additional_trace_header_tags=(VALID_CONFIGS),
            rc_api_enabled=True,
            doc="Scenario with custom headers to be used with DD_TRACE_HEADER_TAGS",
        )


class LibraryConfCustomHeaderTagsInvalid(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "LIBRARY_CONF_CUSTOM_HEADER_TAGS_INVALID",
            additional_trace_header_tags=(INVALID_CONFIGS),
            doc="Scenario with custom headers for DD_TRACE_HEADER_TAGS that libraries should reject",
        )


class TracingConfigEmpty(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACING_CONFIG_EMPTY",
            weblog_env={
                # This scenario should be empty but enabling logs injection allows us to reuse this scenario for the
                # few test cases that need it
                "DD_LOGS_INJECTION": "true",
            },
            doc="",
        )


class TracingConfigNondefault(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACING_CONFIG_NONDEFAULT",
            additional_trace_header_tags=tuple(CONFIG_WILDCARD),
            weblog_env={
                "DD_TRACE_HTTP_SERVER_ERROR_STATUSES": "200-201,202",
                "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": r"ssn=\d{3}-\d{2}-\d{4}",
                "DD_TRACE_CLIENT_IP_ENABLED": "true",
                "DD_TRACE_HTTP_CLIENT_ERROR_STATUSES": "200-201,202",
                "DD_SERVICE": "service_test",
                "DD_TRACE_KAFKA_ENABLED": "false",  # most common endpoint and integration (missing for PHP).
                "DD_TRACE_KAFKAJS_ENABLED": "false",  # In Node the integration is kafkajs.
                "DD_TRACE_PDO_ENABLED": "false",  # Use PDO for PHP,
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "datadog,tracecontext,b3multi,baggage",
                "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "restart",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            },
            appsec_enabled=False,  # disable ASM to test non asm client ip tagging
            iast_enabled=False,
            other_weblog_containers=(PostgresContainer, KafkaContainer),
            rc_api_enabled=True,
            doc="",
            scenario_groups=[scenario_groups.tracing_config, scenario_groups.essentials],
        )


class TracingConfigNondefault2(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACING_CONFIG_NONDEFAULT_2",
            weblog_env={
                "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "",
                "DD_TRACE_KAFKA_ENABLED": "true",
                "DD_TRACE_KAFKAJS_ENABLED": "true",
                "DD_TRACE_PDO_ENABLED": "true",  # Use PDO for PHP
                "DD_TRACE_CLIENT_IP_HEADER": "custom-ip-header",
                "DD_TRACE_CLIENT_IP_ENABLED": "true",
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "datadog,tracecontext,b3multi,baggage",
                "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "ignore",
            },
            other_weblog_containers=(PostgresContainer, KafkaContainer),
            doc="Test tracer configuration when a collection of non-default settings are applied",
            scenario_groups=[scenario_groups.tracing_config],
        )


class TracingConfigNondefault3(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACING_CONFIG_NONDEFAULT_3",
            weblog_env={
                "DD_TRACE_HTTP_CLIENT_TAG_QUERY_STRING": "false",
                "DD_TRACE_CLIENT_IP_HEADER": "custom-ip-header",
                "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "datadog,tracecontext,b3multi,baggage",
                "DD_TRACE_PROPAGATION_BEHAVIOR_EXTRACT": "restart",
                "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "true",
                "DD_LOGS_INJECTION": "true",
                "DD_TRACE_RESOURCE_RENAMING_ENABLED": "true",
                "DD_TRACE_RESOURCE_RENAMING_ALWAYS_SIMPLIFIED_ENDPOINT": "true",
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "true",
                "DD_TRACE_COMPUTE_STATS": "true",
            },
            appsec_enabled=False,
            doc="",
            scenario_groups=[scenario_groups.tracing_config],
        )


class TracingConfigNondefault4(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "TRACING_CONFIG_NONDEFAULT_4",
            weblog_env={
                # Required by Node.js to ensure the snapshot isn't truncated due to a timeout
                "DD_DYNAMIC_INSTRUMENTATION_CAPTURE_TIMEOUT_MS": "1000",
                "DD_DYNAMIC_INSTRUMENTATION_ENABLED": "true",
                "DD_DYNAMIC_INSTRUMENTATION_REDACTED_IDENTIFIERS": "customidentifier1,customidentifier2",
                "DD_DYNAMIC_INSTRUMENTATION_REDACTED_TYPES": "weblog.Models.Debugger.CustomPii,com.datadoghq.system_tests.springboot.debugger.CustomPii,CustomPii",  # noqa: E501
                "DD_DYNAMIC_INSTRUMENTATION_REDACTION_EXCLUDED_IDENTIFIERS": "_2fa,cookie,sessionid",
                "DD_LOGS_INJECTION": "true",
                "DD_TRACE_128_BIT_TRACEID_LOGGING_ENABLED": "false",
                "DD_TRACE_OTEL_ENABLED": "true",
            },
            doc="",
            rc_api_enabled=True,
            rc_backend_enabled=True,
        )

from ._core import DdTraceEndToEndScenario, scenario_groups
from utils.proxy.ports import ProxyPorts


# Adapted from the instrumentation section of the OTel operator example:
# https://github.com/DataDog/opentelemetry-examples/blob/cyrille-leclerc/use-dd-operator/guides/kubernetes/configuration/opentelemetry-kube-stack/values.yaml
# Match instrumentation.env and the exporter/sampler/propagators fields.
# Only Kubernetes service DNS is replaced with the local Agent hostname.
# Settings absent from the example stay unset; the tests still require
# their effective defaults to appear in the startup configuration.
OTEL_STARTUP_LOGS_ENV: dict[str, str] = {
    "OTEL_SEMCONV_STABILITY_OPT_IN": "http,database,rpc,messaging",
    "OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE": "delta",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_TRACES_EXPORTER": "otlp",
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_LOGS_OTEL_ENABLED": "true",
    "DD_METRICS_OTEL_ENABLED": "true",
    "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
    "DD_AGENT_HOST": "agent",
    "DD_DBM_PROPAGATION_MODE": "full",
    "DD_DBM_TRACE_PREPARED_STATEMENTS": "true",
    "DD_DATA_STREAMS_ENABLED": "true",
    "DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED": "true",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://agent:4318/v1/traces",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://agent:4318",
    "OTEL_TRACES_SAMPLER": "parentbased_always_on",
    "OTEL_PROPAGATORS": "tracecontext,baggage",
}


class OtelStartupLogs(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_STARTUP_LOGS",
            weblog_env={**OTEL_STARTUP_LOGS_ENV},
            library_interface_timeout=0,
            agent_interface_timeout=0,
            appsec_enabled=False,
            iast_enabled=False,
            tracer_sampling_rate=None,
            use_proxy_for_weblog=False,
            doc="Require OTel configuration fields in tracer startup logs with an operator-style configuration",
            scenario_groups=[scenario_groups.open_telemetry],
        )


class OtelSemanticsOtlp(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_SEMANTICS_OTLP",
            weblog_env={
                "DD_TRACE_CLIENT_IP_ENABLED": "true",
                "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "otel-sensitive-value",
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
                # OTel semantics must override both conflicting configurations.
                "DD_TRACE_PEER_SERVICE_DEFAULTS_ENABLED": "true",
                "DD_TRACE_RESOURCE_RENAMING_ALWAYS_SIMPLIFIED_ENDPOINT": "true",
                "DD_TRACE_RESOURCE_RENAMING_ENABLED": "true",
                "DD_TRACE_SPAN_ATTRIBUTE_SCHEMA": "v1",
                "DD_TRACE_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            },
            backend_interface_timeout=5,
            include_opentelemetry=True,
            doc="Validate HTTP spans exported directly over OTLP, including typed OpenTelemetry "
            "attributes such as http.response.status_code and server.port",
            scenario_groups=[scenario_groups.open_telemetry],
        )


class OtelSemanticsOtlpCustomErrorStatuses(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_SEMANTICS_OTLP_CUSTOM_ERROR_STATUSES",
            weblog_env={
                "DD_TRACE_HTTP_CLIENT_ERROR_STATUSES": "200",
                "DD_TRACE_HTTP_SERVER_ERROR_STATUSES": "200",
                "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "otel-sensitive-value",
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            },
            backend_interface_timeout=5,
            include_opentelemetry=True,
            doc="Like OTEL_SEMANTICS_OTLP but marks HTTP status 200 as an error to verify that a custom "
            "client and server error status configuration takes precedence over the OTel defaults",
            scenario_groups=[scenario_groups.open_telemetry],
        )


class OtelSemanticsOtlpTraceMetrics(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_SEMANTICS_OTLP_TRACE_METRICS",
            weblog_env={
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
                "DD_METRICS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_TRACES_SPAN_METRICS_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/json",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/metrics",
                "OTEL_EXPORTER_OTLP_METRICS_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
                "_DD_TRACE_METRICS_OTEL_FLUSH_INTERVAL": "1000",
            },
            backend_interface_timeout=5,
            include_opentelemetry=True,
            doc="Validate that OTLP trace metrics retain the OTel HTTP method, status, name, kind, "
            "and error decision used by the corresponding span",
            scenario_groups=[scenario_groups.open_telemetry],
        )


class OtelSemanticsOtlpSamplingRules(DdTraceEndToEndScenario):
    def __init__(self) -> None:
        super().__init__(
            "OTEL_SEMANTICS_OTLP_SAMPLING_RULES",
            # Security findings can force-keep a trace before ordinary sampling rules run.
            appsec_enabled=False,
            iast_enabled=False,
            weblog_env={
                "DD_TRACE_OTEL_SEMANTICS_ENABLED": "true",
                "DD_TRACE_OTEL_ENABLED": "true",
                "DD_TRACE_SAMPLING_RULES": (
                    '[{"resource":"HTTP*","sample_rate":1.0},{"resource":"GET*","sample_rate":1.0},{"sample_rate":0.0}]'
                ),
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"http://proxy:{ProxyPorts.open_telemetry_weblog}/v1/traces",
                "OTEL_EXPORTER_OTLP_TRACES_HEADERS": "dd-protocol=otlp,dd-otlp-path=agent",
            },
            backend_interface_timeout=5,
            include_opentelemetry=True,
            doc="Validate that OTel HTTP span names are available before DD_TRACE_SAMPLING_RULES are evaluated",
            scenario_groups=[scenario_groups.open_telemetry],
        )

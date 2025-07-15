import pytest

from utils._context.core import context


class _Features:
    """See https://github.com/DataDog/system-tests/blob/main/docs/edit/features.md

    Data source is the feature parity dashboard https://feature-parity.us1.prod.dog/
    """

    @staticmethod
    def not_reported(test_object):
        """Use this fake feature to not report a test to feature parity dashboard"""
        pytest.mark.features(feature_id=-1)(test_object)
        return test_object

    @staticmethod
    def trace_global_tags(test_object):
        """Add Metadata globally to all spans (DD_TAGS)

        https://feature-parity.us1.prod.dog/#/?feature=1
        """
        pytest.mark.features(feature_id=1)(test_object)
        return test_object

    @staticmethod
    def trace_agent_connection(test_object):
        """Change Agent hostname (DD_AGENT_HOST)

        https://feature-parity.us1.prod.dog/#/?feature=2
        """
        pytest.mark.features(feature_id=2)(test_object)
        return test_object

    @staticmethod
    def add_metadata_to_spans_via_tags_dd_trace_analytics_enabled(test_object):
        """Add metadata to spans via tags (DD_TRACE_ANALYTICS_ENABLED)

        https://feature-parity.us1.prod.dog/#/?feature=3
        """
        pytest.mark.features(feature_id=3)(test_object)
        return test_object

    @staticmethod
    def trace_search_automatic_config(test_object):
        """Trace Search - automatic config

        https://feature-parity.us1.prod.dog/#/?feature=4
        """
        pytest.mark.features(feature_id=4)(test_object)
        return test_object

    @staticmethod
    def log_injection(test_object):
        """Trace-ID injection into Logs

        https://feature-parity.us1.prod.dog/#/?feature=5
        """
        pytest.mark.features(feature_id=5)(test_object)
        return test_object

    @staticmethod
    def unix_domain_sockets_support_for_traces(test_object):
        """Unix Domain Sockets support for traces

        https://feature-parity.us1.prod.dog/#/?feature=6
        """

        if "uds" in context.weblog_variant:
            pytest.mark.features(feature_id=6)(test_object)
        else:
            pytest.mark.features(feature_id=-1)(test_object)

        return test_object

    @staticmethod
    def unix_domain_sockets_automatic_detection(test_object):
        """Unix Domain Sockets automatic detection

        https://feature-parity.us1.prod.dog/#/?feature=7
        """
        pytest.mark.features(feature_id=7)(test_object)
        return test_object

    @staticmethod
    def twl_customer_controls_ingestion_dd_trace_sampling_rules(test_object):
        """TwL - Customer Controls Ingestion (DD_TRACE_SAMPLING RULES)

        https://feature-parity.us1.prod.dog/#/?feature=8
        """
        pytest.mark.features(feature_id=8)(test_object)
        return test_object

    @staticmethod
    def synthetic_apm_http_header_span_tag_x_datadog_origin(test_object):
        """Synthetic APM (http header ▶ span tag) (x-datadog-origin))

        https://feature-parity.us1.prod.dog/#/?feature=9
        """
        pytest.mark.features(feature_id=9)(test_object)
        return test_object

    @staticmethod
    def log_tracer_status_at_startup(test_object):
        """Log Tracer status at startup

        https://feature-parity.us1.prod.dog/#/?feature=10
        """
        pytest.mark.features(feature_id=10)(test_object)
        return test_object

    @staticmethod
    def fargate_14_tagging_support(test_object):
        """Fargate 1.4 Tagging Support

        https://feature-parity.us1.prod.dog/#/?feature=11
        """
        pytest.mark.features(feature_id=11)(test_object)
        return test_object

    @staticmethod
    def container_tagging(test_object):
        """Container tagging

        https://feature-parity.us1.prod.dog/#/?feature=12
        """
        pytest.mark.features(feature_id=12)(test_object)
        return test_object

    @staticmethod
    def b3_headers_propagation(test_object):
        """B3 headers injection and extraction

        https://feature-parity.us1.prod.dog/#/?feature=13
        """
        pytest.mark.features(feature_id=13)(test_object)
        return test_object

    @staticmethod
    def unix_domain_sockets_support_for_metrics(test_object):
        """Unix Domain Sockets support for metrics

        https://feature-parity.us1.prod.dog/#/?feature=14
        """
        pytest.mark.features(feature_id=14)(test_object)
        return test_object

    @staticmethod
    def support_ddmeasured(test_object):
        """Support _dd.measured

        https://feature-parity.us1.prod.dog/#/?feature=15
        """
        pytest.mark.features(feature_id=15)(test_object)
        return test_object

    @staticmethod
    def dd_service_mapping(test_object):
        """DD_SERVICE_MAPPING

        https://feature-parity.us1.prod.dog/#/?feature=16
        """
        pytest.mark.features(feature_id=16)(test_object)
        return test_object

    @staticmethod
    def dogstatsd_agent_connection(test_object):
        """Datadog managed Dogstatsd client

        https://feature-parity.us1.prod.dog/#/?feature=17
        """
        pytest.mark.features(feature_id=17)(test_object)
        return test_object

    @staticmethod
    def http_headers_as_tags_dd_trace_header_tags(test_object):
        """HTTP Headers as Tags (DD_TRACE_HEADER_TAGS)

        https://feature-parity.us1.prod.dog/#/?feature=18
        """
        pytest.mark.features(feature_id=18)(test_object)
        return test_object

    @staticmethod
    def dd_profiling_enabled(test_object):
        """DD_PROFILING_ENABLED

        https://feature-parity.us1.prod.dog/#/?feature=19
        """
        pytest.mark.features(feature_id=19)(test_object)
        return test_object

    @staticmethod
    def dogstatsd_unified_service_tagging(test_object):
        """Dogstatsd unified service tagging

        https://feature-parity.us1.prod.dog/#/?feature=20
        """
        pytest.mark.features(feature_id=20)(test_object)
        return test_object

    @staticmethod
    def trace_log_exporting_for_aws_lambda(test_object):
        """Trace Log Exporting for AWS Lambda

        https://feature-parity.us1.prod.dog/#/?feature=21
        """
        pytest.mark.features(feature_id=21)(test_object)
        return test_object

    @staticmethod
    def runtime_id_in_span_metadata_for_service_entry_spans(test_object):
        """Runtime-id in span metadata for service entry spans

        https://feature-parity.us1.prod.dog/#/?feature=22
        """
        pytest.mark.features(feature_id=22)(test_object)
        return test_object

    @staticmethod
    def partial_flush(test_object):
        """Partial flush

        https://feature-parity.us1.prod.dog/#/?feature=23
        """
        pytest.mark.features(feature_id=23)(test_object)
        return test_object

    @staticmethod
    def partial_flush_on_by_default(test_object):
        """Partial flush on by default

        https://feature-parity.us1.prod.dog/#/?feature=24
        """
        pytest.mark.features(feature_id=24)(test_object)
        return test_object

    @staticmethod
    def automatic_trace_id_injection_into_logs(test_object):
        """Automatic Trace-id injection into Logs

        https://feature-parity.us1.prod.dog/#/?feature=25
        """
        pytest.mark.features(feature_id=25)(test_object)
        return test_object

    @staticmethod
    def mapping_http_status_codes_to_errors(test_object):
        """Mapping HTTP status codes to errors

        https://feature-parity.us1.prod.dog/#/?feature=26
        """
        pytest.mark.features(feature_id=26)(test_object)
        return test_object

    @staticmethod
    def log_pipelines_updated_for_log_injection(test_object):
        """Log Pipelines updated for log injection

        https://feature-parity.us1.prod.dog/#/?feature=27
        """
        pytest.mark.features(feature_id=27)(test_object)
        return test_object

    @staticmethod
    def inject_service_env_version_into_logs(test_object):
        """Inject service, env, version into logs
        https://feature-parity.us1.prod.dog/#/?feature=28
        """
        pytest.mark.features(feature_id=28)(test_object)
        return test_object

    @staticmethod
    def top_level_detection_in_tracer(test_object):
        """Top-level detection in tracer

        https://feature-parity.us1.prod.dog/#/?feature=29
        """
        pytest.mark.features(feature_id=29)(test_object)
        return test_object

    @staticmethod
    def use_sampling_priorities_2_1_in_rules_based_sampler(test_object):
        """Use sampling priorities +2/-1 in rules-based sampler

        https://feature-parity.us1.prod.dog/#/?feature=30
        """
        pytest.mark.features(feature_id=30)(test_object)
        return test_object

    @staticmethod
    def trace_annotation(test_object):
        """Trace Annotation

        https://feature-parity.us1.prod.dog/#/?feature=31
        """
        pytest.mark.features(feature_id=31)(test_object)
        return test_object

    @staticmethod
    def runtime_metrics(test_object):
        """Runtime metrics

        https://feature-parity.us1.prod.dog/#/?feature=32
        """
        pytest.mark.features(feature_id=32)(test_object)
        return test_object

    @staticmethod
    def logs_throttling(test_object):
        """Logs Throttling

        https://feature-parity.us1.prod.dog/#/?feature=33
        """
        pytest.mark.features(feature_id=33)(test_object)
        return test_object

    @staticmethod
    def post_processing_traces(test_object):
        """Post-Processing Traces

        https://feature-parity.us1.prod.dog/#/?feature=34
        """
        pytest.mark.features(feature_id=34)(test_object)
        return test_object

    @staticmethod
    def span_baggage_item(test_object):
        """Span Baggage item

        https://feature-parity.us1.prod.dog/#/?feature=35
        """
        pytest.mark.features(feature_id=35)(test_object)
        return test_object

    @staticmethod
    def tracer_health_metrics(test_object):
        """Tracer Health Metrics

        https://feature-parity.us1.prod.dog/#/?feature=36
        """
        pytest.mark.features(feature_id=36)(test_object)
        return test_object

    @staticmethod
    def kafka_tracing(test_object):
        """Kafka Tracing

        https://feature-parity.us1.prod.dog/#/?feature=37
        """
        pytest.mark.features(feature_id=37)(test_object)
        return test_object

    @staticmethod
    def numeric_tags_for_trace_search_analytics_step_1(test_object):
        """Numeric tags for Trace Search/Analytics (step 1)

        https://feature-parity.us1.prod.dog/#/?feature=38
        """
        pytest.mark.features(feature_id=38)(test_object)
        return test_object

    @staticmethod
    def grpc_integration_tags(test_object):
        """GRPC integration tags

        https://feature-parity.us1.prod.dog/#/?feature=39
        """
        pytest.mark.features(feature_id=39)(test_object)
        return test_object

    @staticmethod
    def dd_trace_config_file(test_object):
        """DD_TRACE_CONFIG_FILE

        https://feature-parity.us1.prod.dog/#/?feature=40
        """
        pytest.mark.features(feature_id=40)(test_object)
        return test_object

    @staticmethod
    def dd_trace_methods(test_object):
        """DD_TRACE_METHODS

        https://feature-parity.us1.prod.dog/#/?feature=41
        """
        pytest.mark.features(feature_id=41)(test_object)
        return test_object

    @staticmethod
    def structured_log_injection(test_object):
        """DD_LOGS_INJECTION=structured

        https://feature-parity.us1.prod.dog/#/?feature=41
        """
        pytest.mark.features(feature_id=42)(test_object)
        return test_object

    @staticmethod
    def report_tracer_drop_rate_ddtracer_kr(test_object):
        """Report tracer drop rate (_dd.tracer_kr)

        https://feature-parity.us1.prod.dog/#/?feature=43
        """
        pytest.mark.features(feature_id=43)(test_object)
        return test_object

    @staticmethod
    def obfuscation_of_pii_from_web_span_resource_names(test_object):
        """Obfuscation of PII from web span resource names

        https://feature-parity.us1.prod.dog/#/?feature=44
        """
        pytest.mark.features(feature_id=44)(test_object)
        return test_object

    @staticmethod
    def windows_named_pipe_support_for_traces(test_object):
        """Windows named pipe support for traces

        https://feature-parity.us1.prod.dog/#/?feature=45
        """
        pytest.mark.features(feature_id=45)(test_object)
        return test_object

    @staticmethod
    def setting_to_rename_service_by_tag_split_by_tag(test_object):
        """Setting to rename service by tag (split-by-tag)

        https://feature-parity.us1.prod.dog/#/?feature=46
        """
        pytest.mark.features(feature_id=46)(test_object)
        return test_object

    @staticmethod
    def collect_application_version_information(test_object):
        """Collect application version information

        https://feature-parity.us1.prod.dog/#/?feature=47
        """
        pytest.mark.features(feature_id=47)(test_object)
        return test_object

    @staticmethod
    def ensure_that_sampling_is_consistent_across_languages(test_object):
        """Ensure that sampling is consistent across languages

        https://feature-parity.us1.prod.dog/#/?feature=48
        """
        pytest.mark.features(feature_id=48)(test_object)
        return test_object

    @staticmethod
    def user_troubleshooting_tool(test_object):
        """User Troubleshooting Tool

        https://feature-parity.us1.prod.dog/#/?feature=49
        """
        pytest.mark.features(feature_id=49)(test_object)
        return test_object

    @staticmethod
    def option_to_remap_apm_error_response_severity_eg_404_to_error(test_object):
        """Option to remap APM error response severity (e.g. 404 to error)

        https://feature-parity.us1.prod.dog/#/?feature=50
        """
        pytest.mark.features(feature_id=50)(test_object)
        return test_object

    @staticmethod
    def trace_query_string_obfuscation(test_object):
        """Obfuscation of http.url span tag

        https://feature-parity.us1.prod.dog/#/?feature=51
        """
        pytest.mark.features(feature_id=51)(test_object)
        return test_object

    @staticmethod
    def dd_trace_report_hostname(test_object):
        """DD_TRACE_REPORT_HOSTNAME

        https://feature-parity.us1.prod.dog/#/?feature=52
        """
        pytest.mark.features(feature_id=52)(test_object)
        return test_object

    @staticmethod
    def windows_named_pipe_support_for_metrics(test_object):
        """Windows named pipe support for metrics

        https://feature-parity.us1.prod.dog/#/?feature=53
        """
        pytest.mark.features(feature_id=53)(test_object)
        return test_object

    @staticmethod
    def ensure_consistent_http_client_integration_tags(test_object):
        """Ensure consistent HTTP client integration tags

        https://feature-parity.us1.prod.dog/#/?feature=54
        """
        pytest.mark.features(feature_id=54)(test_object)
        return test_object

    @staticmethod
    def aws_sdk_integration_tags(test_object):
        """AWS SDK Integration Tags

        https://feature-parity.us1.prod.dog/#/?feature=55
        """
        pytest.mark.features(feature_id=55)(test_object)
        return test_object

    @staticmethod
    def dont_set_username_tag_because_its_pii(test_object):
        """Don't set username tag because it's PII

        https://feature-parity.us1.prod.dog/#/?feature=56
        """
        pytest.mark.features(feature_id=56)(test_object)
        return test_object

    @staticmethod
    def trace_client_app_tagging(test_object):
        """Trace Client App Tagging

        https://feature-parity.us1.prod.dog/#/?feature=57
        """
        pytest.mark.features(feature_id=57)(test_object)
        return test_object

    @staticmethod
    def client_split_by_domain_service_host(test_object):
        """Client Split by domain/service/host

        https://feature-parity.us1.prod.dog/#/?feature=58
        """
        pytest.mark.features(feature_id=58)(test_object)
        return test_object

    @staticmethod
    def horizontal_propagation_of_x_datadog_tags_between_services(test_object):
        """Horizontal propagation of `x-datadog-tags` between services

        https://feature-parity.us1.prod.dog/#/?feature=59
        """
        pytest.mark.features(feature_id=59)(test_object)
        return test_object

    @staticmethod
    def vertical_propagation_of_x_datadog_tags_onto_each_chunk_root_span(test_object):
        """Vertical propagation of `x-datadog-tags` onto each chunk root span.

        https://feature-parity.us1.prod.dog/#/?feature=60
        """
        pytest.mark.features(feature_id=60)(test_object)
        return test_object

    @staticmethod
    def creation_and_propagation_of_ddpdm(test_object):
        """Creation and propagation of `_dd.p.dm`

        https://feature-parity.us1.prod.dog/#/?feature=61
        """
        pytest.mark.features(feature_id=61)(test_object)
        return test_object

    @staticmethod
    def client_side_stats_supported(test_object):
        """Client side stats supported

        https://feature-parity.us1.prod.dog/#/?feature=62
        """
        pytest.mark.features(feature_id=62)(test_object)
        return test_object

    @staticmethod
    def client_side_stats_on_by_default(test_object):
        """Client side stats on by default

        https://feature-parity.us1.prod.dog/#/?feature=63
        """
        pytest.mark.features(feature_id=63)(test_object)
        return test_object

    @staticmethod
    def instrumentation_telemetry_enabled_by_default(test_object):
        """Instrumentation Telemetry enabled by default

        https://feature-parity.us1.prod.dog/#/?feature=64
        """
        pytest.mark.features(feature_id=64)(test_object)
        return test_object

    @staticmethod
    def dd_instrumentation_telemetry_enabled_supported(test_object):
        """DD_INSTRUMENTATION_TELEMETRY_ENABLED supported

        https://feature-parity.us1.prod.dog/#/?feature=65
        """
        pytest.mark.features(feature_id=65)(test_object)
        return test_object

    @staticmethod
    def app_environment_collected(test_object):
        """App environment collected

        https://feature-parity.us1.prod.dog/#/?feature=66
        """
        pytest.mark.features(feature_id=66)(test_object)
        return test_object

    @staticmethod
    def dependencies_collected(test_object):
        """Dependencies collected

        https://feature-parity.us1.prod.dog/#/?feature=67
        """
        pytest.mark.features(feature_id=67)(test_object)
        return test_object

    @staticmethod
    def integrations_enabled_collected(test_object):
        """Integrations enabled collected

        https://feature-parity.us1.prod.dog/#/?feature=68
        """
        pytest.mark.features(feature_id=68)(test_object)
        return test_object

    @staticmethod
    def telemetry_configurations_collected(test_object):
        """Tracer Configurations collected

        https://feature-parity.us1.prod.dog/#/?feature=69
        """
        pytest.mark.features(feature_id=69)(test_object)
        return test_object

    @staticmethod
    def telemetry_heart_beat_collected(test_object):
        """Heart beat collected

        https://feature-parity.us1.prod.dog/#/?feature=70
        """
        pytest.mark.features(feature_id=70)(test_object)
        return test_object

    @staticmethod
    def app_close_collected(test_object):
        """App close collected

        https://feature-parity.us1.prod.dog/#/?feature=71
        """
        pytest.mark.features(feature_id=71)(test_object)
        return test_object

    @staticmethod
    def redacted_error_logs_collected(test_object):
        """Redacted Error Logs collected

        https://feature-parity.us1.prod.dog/#/?feature=72
        """
        pytest.mark.features(feature_id=72)(test_object)
        return test_object

    @staticmethod
    def telemetry_metrics_collected(test_object):
        """Metrics collected

        https://feature-parity.us1.prod.dog/#/?feature=73
        """
        pytest.mark.features(feature_id=73)(test_object)
        return test_object

    @staticmethod
    def telemetry_api_v2_implemented(test_object):
        """API V2 Implemented

        https://feature-parity.us1.prod.dog/#/?feature=74
        """
        pytest.mark.features(feature_id=74)(test_object)
        return test_object

    @staticmethod
    def app_client_configuration_change_event(test_object):
        """app-client-configuration-change event

        https://feature-parity.us1.prod.dog/#/?feature=75
        """
        pytest.mark.features(feature_id=75)(test_object)
        return test_object

    @staticmethod
    def app_product_change_event(test_object):
        """app-product-change event

        https://feature-parity.us1.prod.dog/#/?feature=76
        """
        pytest.mark.features(feature_id=76)(test_object)
        return test_object

    @staticmethod
    def app_extended_heartbeat_event(test_object):
        """app-extended-heartbeat event

        https://feature-parity.us1.prod.dog/#/?feature=77
        """
        pytest.mark.features(feature_id=77)(test_object)
        return test_object

    @staticmethod
    def telemetry_message_batch(test_object):
        """message-batch

        https://feature-parity.us1.prod.dog/#/?feature=78
        """
        pytest.mark.features(feature_id=78)(test_object)
        return test_object

    @staticmethod
    def telemetry_app_started_event(test_object):
        """app-started changes

        https://feature-parity.us1.prod.dog/#/?feature=79
        """
        pytest.mark.features(feature_id=79)(test_object)
        return test_object

    @staticmethod
    def dd_telemetry_dependency_collection_enabled_supported(test_object):
        """DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED supported

        https://feature-parity.us1.prod.dog/#/?feature=80
        """
        pytest.mark.features(feature_id=80)(test_object)
        return test_object

    @staticmethod
    def additional_http_headers_supported(test_object):
        """Additional HTTP Headers supported

        https://feature-parity.us1.prod.dog/#/?feature=81
        """
        pytest.mark.features(feature_id=81)(test_object)
        return test_object

    @staticmethod
    def remote_config_object_supported(test_object):
        """remote-config object supported

        https://feature-parity.us1.prod.dog/#/?feature=82
        """
        pytest.mark.features(feature_id=82)(test_object)
        return test_object

    @staticmethod
    def w3c_headers_injection_and_extraction(test_object):
        """W3C headers injection and extraction

        https://feature-parity.us1.prod.dog/#/?feature=83
        """
        pytest.mark.features(feature_id=83)(test_object)
        return test_object

    @staticmethod
    def otel_api(test_object):
        """OTel API

        https://feature-parity.us1.prod.dog/#/?feature=84
        """
        pytest.mark.features(feature_id=84)(test_object)
        return test_object

    @staticmethod
    def trace_id_128_bit_generation_propagation(test_object):
        """128-bit trace id generation + propagation

        https://feature-parity.us1.prod.dog/#/?feature=85
        """
        pytest.mark.features(feature_id=85)(test_object)
        return test_object

    @staticmethod
    def span_events(test_object):
        """Span Events

        https://feature-parity.us1.prod.dog/#/?feature=86
        """
        pytest.mark.features(feature_id=86)(test_object)
        return test_object

    @staticmethod
    def span_links(test_object):
        """Span Links

        https://feature-parity.us1.prod.dog/#/?feature=87
        """
        pytest.mark.features(feature_id=87)(test_object)
        return test_object

    @staticmethod
    def trace_client_ip_header(test_object):
        """Client IP adress collection (DD_TRACE_CLIENT_IP_ENABLED)

        https://feature-parity.us1.prod.dog/#/?feature=88
        """
        pytest.mark.features(feature_id=88)(test_object)
        return test_object

    @staticmethod
    def host_auto_instrumentation(test_object):
        """Host auto-instrumentation

        https://feature-parity.us1.prod.dog/#/?feature=89
        """
        pytest.mark.features(feature_id=89)(test_object)
        return test_object

    @staticmethod
    def container_auto_instrumentation(test_object):
        """Container auto-instrumentation

        https://feature-parity.us1.prod.dog/#/?feature=90
        """
        pytest.mark.features(feature_id=90)(test_object)
        return test_object

    @staticmethod
    def collect_http_post_data_and_headers(test_object):
        """Collect HTTP Post Data and Headers

        https://feature-parity.us1.prod.dog/#/?feature=94
        """
        pytest.mark.features(feature_id=94)(test_object)
        return test_object

    @staticmethod
    def weak_hash_vulnerability_detection(test_object):
        """Weak hash vulnerability detection

        https://feature-parity.us1.prod.dog/#/?feature=96
        """
        pytest.mark.features(feature_id=96)(test_object)
        return test_object

    @staticmethod
    def db_integrations(test_object):
        """DB Integrations

        https://feature-parity.us1.prod.dog/#/?feature=98
        """
        pytest.mark.features(feature_id=98)(test_object)
        return test_object

    @staticmethod
    def weak_cipher_detection(test_object):
        """Weak cipher detection

        https://feature-parity.us1.prod.dog/#/?feature=100
        """
        pytest.mark.features(feature_id=100)(test_object)
        return test_object

    @staticmethod
    def threats_alpha_preview(test_object):
        """Threats Alpha Preview

        https://feature-parity.us1.prod.dog/#/?feature=110
        """
        pytest.mark.features(feature_id=110)(test_object)
        return test_object

    @staticmethod
    def procedure_to_debug_install(test_object):
        """Procedure to debug install

        https://feature-parity.us1.prod.dog/#/?feature=113
        """
        pytest.mark.features(feature_id=113)(test_object)
        return test_object

    @staticmethod
    def security_events_metadata(test_object):
        """Security Events Metadata

        https://feature-parity.us1.prod.dog/#/?feature=124
        """
        pytest.mark.features(feature_id=124)(test_object)
        return test_object

    @staticmethod
    def appsec_rate_limiter(test_object):
        """Rate limiter

        https://feature-parity.us1.prod.dog/#/?feature=134
        """
        pytest.mark.features(feature_id=134)(test_object)
        return test_object

    @staticmethod
    def support_in_app_waf_metrics_report(test_object):
        """Support In-App WAF metrics report

        https://feature-parity.us1.prod.dog/#/?feature=140
        """
        pytest.mark.features(feature_id=140)(test_object)
        return test_object

    @staticmethod
    def user_monitoring(test_object):
        """User Monitoring

        https://feature-parity.us1.prod.dog/#/?feature=141
        """
        pytest.mark.features(feature_id=141)(test_object)
        return test_object

    @staticmethod
    def event_tracking_sdk_v2(test_object):
        """Event tracking SDK v2

        https://feature-parity.us1.prod.dog/#/?feature=372
        """
        pytest.mark.features(feature_id=372)(test_object)
        return test_object

    @staticmethod
    def appsec_service_activation_origin_metric(test_object):
        """Appsec service activation origin metric

        https://feature-parity.us1.prod.dog/#/?feature=471
        """
        pytest.mark.features(feature_id=471)(test_object)
        return test_object

    @staticmethod
    def serialize_waf_rules_without_limiting_their_sizes(test_object):
        """Serialize WAF rules without limiting their sizes

        https://feature-parity.us1.prod.dog/#/?feature=142
        """
        pytest.mark.features(feature_id=142)(test_object)
        return test_object

    @staticmethod
    def threats_configuration(test_object):
        """Threats Configuration

        https://feature-parity.us1.prod.dog/#/?feature=143
        """
        pytest.mark.features(feature_id=143)(test_object)
        return test_object

    @staticmethod
    def sensitive_data_obfuscation(test_object):
        """Sensitive Data Obfuscation

        https://feature-parity.us1.prod.dog/#/?feature=144
        """
        pytest.mark.features(feature_id=144)(test_object)
        return test_object

    @staticmethod
    def propagation_of_user_id_rfc(test_object):
        """Propagation of user Id RFC

        https://feature-parity.us1.prod.dog/#/?feature=146
        """
        pytest.mark.features(feature_id=146)(test_object)
        return test_object

    @staticmethod
    def appsec_onboarding(test_object):
        """Onboarding

        https://feature-parity.us1.prod.dog/#/?feature=154
        """
        pytest.mark.features(feature_id=154)(test_object)
        return test_object

    @staticmethod
    def changing_rules_using_rc(test_object):
        """Changing rules using RC

        https://feature-parity.us1.prod.dog/#/?feature=157
        """
        pytest.mark.features(feature_id=157)(test_object)
        return test_object

    @staticmethod
    def appsec_shell_execution_tracing(test_object):
        """Shell execution tracing

        https://feature-parity.us1.prod.dog/#/?feature=158
        """
        pytest.mark.features(feature_id=158)(test_object)
        return test_object

    @staticmethod
    def custom_business_logic_events(test_object):
        """Custom Business Logic Events

        https://feature-parity.us1.prod.dog/#/?feature=161
        """
        pytest.mark.features(feature_id=161)(test_object)
        return test_object

    @staticmethod
    def graphql_threats_detection(test_object):
        """GraphQL Threats Detection

        https://feature-parity.us1.prod.dog/#/?feature=162
        """
        pytest.mark.features(feature_id=162)(test_object)
        return test_object

    @staticmethod
    def iast_sink_sql_injection(test_object):
        """IAST Sink: SQL Injection

        https://feature-parity.us1.prod.dog/#/?feature=165
        """
        pytest.mark.features(feature_id=165)(test_object)
        return test_object

    @staticmethod
    def iast_sink_code_injection(test_object):
        """IAST Sink: Code Injection

        https://feature-parity.us1.prod.dog/#/?feature=315
        """
        pytest.mark.features(feature_id=315)(test_object)
        return test_object

    @staticmethod
    def iast_sink_command_injection(test_object):
        """IAST Sink: Command Injection

        https://feature-parity.us1.prod.dog/#/?feature=166
        """
        pytest.mark.features(feature_id=166)(test_object)
        return test_object

    @staticmethod
    def iast_sink_path_traversal(test_object):
        """IAST Sink: Path Traversal

        https://feature-parity.us1.prod.dog/#/?feature=167
        """
        pytest.mark.features(feature_id=167)(test_object)
        return test_object

    @staticmethod
    def iast_sink_ldap_injection(test_object):
        """IAST Sink: LDAP Injection

        https://feature-parity.us1.prod.dog/#/?feature=168
        """
        pytest.mark.features(feature_id=168)(test_object)
        return test_object

    @staticmethod
    def iast_sink_header_injection(test_object):
        """IAST Sink: Header Injection

        https://feature-parity.us1.prod.dog/#/?feature=203
        """
        pytest.mark.features(feature_id=203)(test_object)
        return test_object

    @staticmethod
    def iast_sink_template_injection(test_object):
        """IAST Sink: Template Injection

        https://feature-parity.us1.prod.dog/#/?feature=330
        """
        pytest.mark.features(feature_id=330)(test_object)
        return test_object

    @staticmethod
    def iast_source_request_parameter_value(test_object):
        """IAST Source: Request Parameter Value

        https://feature-parity.us1.prod.dog/#/?feature=169
        """
        pytest.mark.features(feature_id=169)(test_object)
        return test_object

    @staticmethod
    def iast_source_request_parameter_name(test_object):
        """IAST Source: Request Parameter Name

        https://feature-parity.us1.prod.dog/#/?feature=170
        """
        pytest.mark.features(feature_id=170)(test_object)
        return test_object

    @staticmethod
    def iast_source_header_value(test_object):
        """IAST Source: Header Value

        https://feature-parity.us1.prod.dog/#/?feature=171
        """
        pytest.mark.features(feature_id=171)(test_object)
        return test_object

    @staticmethod
    def iast_source_header_name(test_object):
        """IAST Source: Header Name

        https://feature-parity.us1.prod.dog/#/?feature=172
        """
        pytest.mark.features(feature_id=172)(test_object)
        return test_object

    @staticmethod
    def iast_source_cookie_value(test_object):
        """IAST Source: Cookie Value

        https://feature-parity.us1.prod.dog/#/?feature=173
        """
        pytest.mark.features(feature_id=173)(test_object)
        return test_object

    @staticmethod
    def iast_source_cookie_name(test_object):
        """IAST Source: Cookie Name

        https://feature-parity.us1.prod.dog/#/?feature=174
        """
        pytest.mark.features(feature_id=174)(test_object)
        return test_object

    @staticmethod
    def iast_source_body(test_object):
        """IAST Source: Body

        https://feature-parity.us1.prod.dog/#/?feature=175
        """
        pytest.mark.features(feature_id=175)(test_object)
        return test_object

    @staticmethod
    def iast_source_kafka_key(test_object):
        """IAST Source: Kafka message key

        https://feature-parity.us1.prod.dog/#/?feature=277
        """
        pytest.mark.features(feature_id=277)(test_object)
        return test_object

    @staticmethod
    def iast_source_kafka_value(test_object):
        """IAST Source: Kafka message value

        https://feature-parity.us1.prod.dog/#/?feature=278
        """
        pytest.mark.features(feature_id=278)(test_object)
        return test_object

    @staticmethod
    def iast_graphql_resolver_argument(test_object):
        """IAST Source: Graphql resolver argument

        https://feature-parity.us1.prod.dog/#/?feature=281
        """
        pytest.mark.features(feature_id=281)(test_object)
        return test_object

    @staticmethod
    def grpc_threats_management(test_object):
        """GRPC Threats Management

        https://feature-parity.us1.prod.dog/#/?feature=176
        """
        pytest.mark.features(feature_id=176)(test_object)
        return test_object

    @staticmethod
    def waf_telemetry(test_object):
        """WAF Telemetry

        https://feature-parity.us1.prod.dog/#/?feature=178
        """
        pytest.mark.features(feature_id=178)(test_object)
        return test_object

    @staticmethod
    def kafkaspan_creationcontext_propagation_with_dd_trace(test_object):
        """[Kafka][Span Creation][Context Propagation] with dd-trace
        https://feature-parity.us1.prod.dog/#/?feature=192
        """
        pytest.mark.features(feature_id=192)(test_object)
        return test_object

    @staticmethod
    def open_tracing_api(test_object):
        """Open Tracing API

        https://feature-parity.us1.prod.dog/#/?feature=196
        """
        pytest.mark.features(feature_id=196)(test_object)
        return test_object

    @staticmethod
    def custom_tracing_api(test_object):
        """Custom Tracing API

        https://feature-parity.us1.prod.dog/#/?feature=197
        """
        pytest.mark.features(feature_id=197)(test_object)
        return test_object

    @staticmethod
    def iast_sink_hardcoded_passwords(test_object):
        """IAST sink: Hardcoded passwords detection

        https://feature-parity.us1.prod.dog/#/?feature=290
        """
        pytest.mark.features(feature_id=290)(test_object)
        return test_object

    @staticmethod
    def iast_sink_hardcoded_secrets(test_object):
        """IAST sink: Hardcoded secrets detection

        https://feature-parity.us1.prod.dog/#/?feature=198
        """
        pytest.mark.features(feature_id=198)(test_object)
        return test_object

    @staticmethod
    def appsec_request_blocking(test_object):
        """Request Blocking

        https://feature-parity.us1.prod.dog/#/?feature=199
        """
        pytest.mark.features(feature_id=199)(test_object)
        return test_object

    @staticmethod
    def appsec_response_blocking(test_object):
        """Response Blocking

        https://feature-parity.us1.prod.dog/#/?feature=200
        """
        pytest.mark.features(feature_id=200)(test_object)
        return test_object

    @staticmethod
    def appsec_blocking_action(test_object):
        """Blocking Action

        https://feature-parity.us1.prod.dog/#/?feature=201
        """
        pytest.mark.features(feature_id=201)(test_object)
        return test_object

    @staticmethod
    def appsec_truncation_action(test_object):
        """Truncation Action

        https://feature-parity.us1.prod.dog/#/?feature=373
        """
        pytest.mark.features(feature_id=373)(test_object)
        return test_object

    @staticmethod
    def appsec_client_ip_blocking(test_object):
        """Client IP Blocking

        https://feature-parity.us1.prod.dog/#/?feature=202
        """
        pytest.mark.features(feature_id=202)(test_object)
        return test_object

    @staticmethod
    def appsec_header_injection(test_object):
        """Header Injection

        https://feature-parity.us1.prod.dog/#/?feature=203
        """
        pytest.mark.features(feature_id=203)(test_object)
        return test_object

    @staticmethod
    def api_security_schemas(test_object):
        """Schema extraction for API Security

        https://feature-parity.us1.prod.dog/#/?feature=204
        """
        pytest.mark.features(feature_id=204)(test_object)
        return test_object

    @staticmethod
    def span_links_through_datadog_api(test_object):
        """Span links (through Datadog API)

        https://feature-parity.us1.prod.dog/#/?feature=205
        """
        pytest.mark.features(feature_id=205)(test_object)
        return test_object

    @staticmethod
    def cassandra_support(test_object):
        """Cassandra support

        https://feature-parity.us1.prod.dog/#/?feature=206
        """
        pytest.mark.features(feature_id=206)(test_object)
        return test_object

    @staticmethod
    def mysql_support(test_object):
        """MySQL Support

        https://feature-parity.us1.prod.dog/#/?feature=207
        """
        pytest.mark.features(feature_id=207)(test_object)
        return test_object

    @staticmethod
    def mssql_support(test_object):
        """MySQL Support

        https://feature-parity.us1.prod.dog/#/?feature=225
        """
        pytest.mark.features(feature_id=225)(test_object)
        return test_object

    @staticmethod
    def postgres_support(test_object):
        """PostGres Support

        https://feature-parity.us1.prod.dog/#/?feature=208
        """
        pytest.mark.features(feature_id=208)(test_object)
        return test_object

    @staticmethod
    def database_monitoring_correlation(test_object):
        """Database Monitoring correlation

        https://feature-parity.us1.prod.dog/#/?feature=209
        """
        pytest.mark.features(feature_id=209)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_http(test_object):
        """DataStreams Monitoring support for Http

        https://feature-parity.us1.prod.dog/#/?feature=210
        """
        pytest.mark.features(feature_id=210)(test_object)
        return test_object

    @staticmethod
    def debugger(test_object):
        """Debugger

        https://feature-parity.us1.prod.dog/#/?feature=211
        """
        pytest.mark.features(feature_id=211)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_kafka(test_object):
        """DataStreams Monitoring support for Kafka

        https://feature-parity.us1.prod.dog/#/?feature=212
        """
        pytest.mark.features(feature_id=212)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_rabbitmq(test_object):
        """DataStreams Monitoring support for RabbitMQ

        https://feature-parity.us1.prod.dog/#/?feature=213
        """
        pytest.mark.features(feature_id=213)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_rabbitmq_fanout(test_object):
        """DataStreams Monitoring support for RabbitMQ - Fanout

        https://feature-parity.us1.prod.dog/#/?feature=214
        """
        pytest.mark.features(feature_id=214)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_rabbitmq_topicexchange(test_object):
        """DataStreams Monitoring support for RabbitMq - TopicExchange

        https://feature-parity.us1.prod.dog/#/?feature=215
        """
        pytest.mark.features(feature_id=215)(test_object)
        return test_object

    @staticmethod
    def mongo_support(test_object):
        """Mongo Support

        https://feature-parity.us1.prod.dog/#/?feature=216
        """
        pytest.mark.features(feature_id=216)(test_object)
        return test_object

    @staticmethod
    def otel_mysql_support(test_object):
        """OTEL MySql Support

        https://feature-parity.us1.prod.dog/#/?feature=217
        """
        pytest.mark.features(feature_id=217)(test_object)
        return test_object

    @staticmethod
    def otel_mssql_support(test_object):
        """OTEL MySql Support

        https://feature-parity.us1.prod.dog/#/?feature=226
        """
        pytest.mark.features(feature_id=226)(test_object)
        return test_object

    @staticmethod
    def otel_postgres_support(test_object):
        """OTEL PostGres Support

        https://feature-parity.us1.prod.dog/#/?feature=218
        """
        pytest.mark.features(feature_id=218)(test_object)
        return test_object

    @staticmethod
    def sql_support(test_object):
        """Sql support

        https://feature-parity.us1.prod.dog/#/?feature=219
        """
        pytest.mark.features(feature_id=219)(test_object)
        return test_object

    @staticmethod
    def dynamic_configuration(test_object):
        """Dynamic Configuration

        https://feature-parity.us1.prod.dog/#/?feature=220
        """
        pytest.mark.features(feature_id=220)(test_object)
        return test_object

    @staticmethod
    def datadog_headers_propagation(test_object):
        """Datadog headers propagation

        https://feature-parity.us1.prod.dog/#/?feature=221
        """
        pytest.mark.features(feature_id=221)(test_object)
        return test_object

    @staticmethod
    def single_span_sampling(test_object):
        """Single Span Sampling

        https://feature-parity.us1.prod.dog/#/?feature=222
        """
        pytest.mark.features(feature_id=222)(test_object)
        return test_object

    @staticmethod
    def tracer_flare(test_object):
        """Tracer Flare

        https://feature-parity.us1.prod.dog/#/?feature=223
        """
        pytest.mark.features(feature_id=223)(test_object)
        return test_object

    @staticmethod
    def profiling(test_object):
        """Profiling

        https://feature-parity.us1.prod.dog/#/?feature=224
        """
        pytest.mark.features(feature_id=224)(test_object)
        return test_object

    @staticmethod
    def trace_sampling(test_object):
        """Profiling

        https://feature-parity.us1.prod.dog/#/?feature=227
        """
        pytest.mark.features(feature_id=227)(test_object)
        return test_object

    @staticmethod
    def telemetry_instrumentation(test_object):
        """Instrumentation telemetry

        https://feature-parity.us1.prod.dog/#/?feature=229
        """
        pytest.mark.features(feature_id=229)(test_object)
        return test_object

    @staticmethod
    def appsec_logs(test_object):
        """Appsec Logs

        https://feature-parity.us1.prod.dog/#/?feature=230
        """
        pytest.mark.features(feature_id=230)(test_object)
        return test_object

    @staticmethod
    def appsec_miscs_internals(test_object):
        """Appsec Miscs Internals

        https://feature-parity.us1.prod.dog/#/?feature=231
        """
        pytest.mark.features(feature_id=231)(test_object)
        return test_object

    @staticmethod
    def appsec_scrubbing(test_object):
        """Appsec Scrubbing

        https://feature-parity.us1.prod.dog/#/?feature=232
        """
        pytest.mark.features(feature_id=232)(test_object)
        return test_object

    @staticmethod
    def appsec_standard_tags_client_ip(test_object):
        """Appsec Standard Tags: client IP

        https://feature-parity.us1.prod.dog/#/?feature=233
        """
        pytest.mark.features(feature_id=233)(test_object)
        return test_object

    @staticmethod
    def waf_features(test_object):
        """WAF features

        https://feature-parity.us1.prod.dog/#/?feature=234
        """
        pytest.mark.features(feature_id=234)(test_object)
        return test_object

    @staticmethod
    def waf_rules(test_object):
        """WAF rules

        https://feature-parity.us1.prod.dog/#/?feature=235
        """
        pytest.mark.features(feature_id=235)(test_object)
        return test_object

    @staticmethod
    def iast_sink_hsts_missing_header(test_object):
        """IAST Sink: HSTS missing header

        https://feature-parity.us1.prod.dog/#/?feature=236
        """
        pytest.mark.features(feature_id=236)(test_object)
        return test_object

    @staticmethod
    def iast_sink_http_only_cookie(test_object):
        """IAST Sink: HTTP only cookie

        https://feature-parity.us1.prod.dog/#/?feature=237
        """
        pytest.mark.features(feature_id=237)(test_object)
        return test_object

    @staticmethod
    def iast_sink_insecure_cookie(test_object):
        """IAST Sink: Insecure cookie

        https://feature-parity.us1.prod.dog/#/?feature=238
        """
        pytest.mark.features(feature_id=238)(test_object)
        return test_object

    @staticmethod
    def iast_sink_samesite_cookie(test_object):
        """IAST Sink: SameSite cookie

        https://feature-parity.us1.prod.dog/#/?feature=240
        """
        pytest.mark.features(feature_id=240)(test_object)
        return test_object

    @staticmethod
    def iast_sink_ssrf(test_object):
        """IAST Sink: SSRF

        https://feature-parity.us1.prod.dog/#/?feature=241
        """
        pytest.mark.features(feature_id=241)(test_object)
        return test_object

    @staticmethod
    def iast_sink_trustboundaryviolation(test_object):
        """IAST Sink: TrustBoundaryViolation

        https://feature-parity.us1.prod.dog/#/?feature=242
        """
        pytest.mark.features(feature_id=242)(test_object)
        return test_object

    @staticmethod
    def iast_sink_unvalidatedforward(test_object):
        """IAST Sink: UnvalidatedForward

        https://feature-parity.us1.prod.dog/#/?feature=243
        """
        pytest.mark.features(feature_id=243)(test_object)
        return test_object

    @staticmethod
    def iast_sink_unvalidatedheader(test_object):
        """IAST Sink: UnvalidatedHeader

        https://feature-parity.us1.prod.dog/#/?feature=244
        """
        pytest.mark.features(feature_id=244)(test_object)
        return test_object

    @staticmethod
    def iast_sink_unvalidatedredirect(test_object):
        """IAST Sink: UnvalidatedRedirect

        https://feature-parity.us1.prod.dog/#/?feature=245
        """
        pytest.mark.features(feature_id=245)(test_object)
        return test_object

    @staticmethod
    def iast_sink_weakrandomness(test_object):
        """IAST Sink: WeakRandomness

        https://feature-parity.us1.prod.dog/#/?feature=246
        """
        pytest.mark.features(feature_id=246)(test_object)
        return test_object

    @staticmethod
    def iast_sink_xcontentsniffing(test_object):
        """IAST Sink: XContentSniffing

        https://feature-parity.us1.prod.dog/#/?feature=247
        """
        pytest.mark.features(feature_id=247)(test_object)
        return test_object

    @staticmethod
    def iast_sink_xpathinjection(test_object):
        """IAST Sink: XPathInjection

        https://feature-parity.us1.prod.dog/#/?feature=248
        """
        pytest.mark.features(feature_id=248)(test_object)
        return test_object

    @staticmethod
    def iast_sink_xss(test_object):
        """IAST Sink: XSS

        https://feature-parity.us1.prod.dog/#/?feature=249
        """
        pytest.mark.features(feature_id=249)(test_object)
        return test_object

    @staticmethod
    def iast_source_multipart(test_object):
        """IAST Source: Multipart

        https://feature-parity.us1.prod.dog/#/?feature=250
        """
        pytest.mark.features(feature_id=250)(test_object)
        return test_object

    @staticmethod
    def iast_source_path(test_object):
        """IAST Source: Path

        https://feature-parity.us1.prod.dog/#/?feature=251
        """
        pytest.mark.features(feature_id=251)(test_object)
        return test_object

    @staticmethod
    def iast_source_uri(test_object):
        """IAST Source: URI

        https://feature-parity.us1.prod.dog/#/?feature=252
        """
        pytest.mark.features(feature_id=252)(test_object)
        return test_object

    @staticmethod
    def iast_sink_mongodb_injection(test_object):
        """IAST Sink: MongoDB injection

        https://feature-parity.us1.prod.dog/#/?feature=253
        """
        pytest.mark.features(feature_id=253)(test_object)
        return test_object

    @staticmethod
    def appsec_user_blocking(test_object):
        """User blocking

        https://feature-parity.us1.prod.dog/#/?feature=254
        """
        pytest.mark.features(feature_id=254)(test_object)
        return test_object

    @staticmethod
    def decisionless_extraction(test_object):
        """Sampling behavior when extracted trace context does not convey a sampling decision
        https://feature-parity.us1.prod.dog/#/?feature=261
        """
        pytest.mark.features(feature_id=261)(test_object)
        return test_object

    @staticmethod
    def semantic_core_validations(test_object):
        """Semantic Core Validations

        https://feature-parity.us1.prod.dog/#/?feature=262
        """
        pytest.mark.features(feature_id=262)(test_object)
        return test_object

    @staticmethod
    def aws_sqs_span_creationcontext_propagation_via_xray_header_with_dd_trace(
        test_object,
    ):
        """[AWS-SQS][Span Creation][Context Propagation][AWS X-Ray] with dd-trace

        https://feature-parity.us1.prod.dog/#/?feature=263
        """
        pytest.mark.features(feature_id=263)(test_object)
        return test_object

    @staticmethod
    def aws_sqs_span_creationcontext_propagation_via_message_attributes_with_dd_trace(
        test_object,
    ):
        """[AWS-SQS][Span Creation][Context Propagation][AWS Message Attributes] with dd-trace

        https://feature-parity.us1.prod.dog/#/?feature=264
        """
        pytest.mark.features(feature_id=264)(test_object)
        return test_object

    @staticmethod
    def agent_remote_configuration(test_object):
        """Agent supports remote configuration

        https://feature-parity.us1.prod.dog/#/?feature=265
        """
        pytest.mark.features(feature_id=265)(test_object)
        return test_object

    @staticmethod
    def data_integrity(test_object):
        """Data integrity

        https://feature-parity.us1.prod.dog/#/?feature=266
        """
        pytest.mark.features(feature_id=266)(test_object)
        return test_object

    @staticmethod
    def library_scrubbing(test_object):
        """Library scrubbing

        https://feature-parity.us1.prod.dog/#/?feature=267
        """
        pytest.mark.features(feature_id=267)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_sqs(test_object):
        """DataStreams Monitoring support for AWS SQS

        https://feature-parity.us1.prod.dog/#/?feature=268
        """
        pytest.mark.features(feature_id=268)(test_object)
        return test_object

    @staticmethod
    def api_security_configuration(test_object):
        """Schema extraction for API Security

        https://feature-parity.us1.prod.dog/#/?feature=269
        """
        pytest.mark.features(feature_id=269)(test_object)
        return test_object

    @staticmethod
    def rabbitmq_span_creationcontext_propagation_with_dd_trace(test_object):
        """[RabbitMQ][Span Creation][Context Propagation] with dd-trace

        https://feature-parity.us1.prod.dog/#/?feature=270
        """
        pytest.mark.features(feature_id=270)(test_object)
        return test_object

    @staticmethod
    def aws_sns_span_creationcontext_propagation_via_message_attributes_with_dd_trace(
        test_object,
    ):
        """[AWS-SNS][Span Creation][Context Propagation] with dd-trace

        https://feature-parity.us1.prod.dog/#/?feature=271
        """
        pytest.mark.features(feature_id=271)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_sns(test_object):
        """DataStreams Monitoring support for AWS SNS

        https://feature-parity.us1.prod.dog/#/?feature=273
        """
        pytest.mark.features(feature_id=273)(test_object)
        return test_object

    @staticmethod
    def iast_sink_insecure_auth_protocol(test_object):
        """IAST Sink: Insecure auth protocol

        https://feature-parity.us1.prod.dog/#/?feature=272
        """
        pytest.mark.features(feature_id=272)(test_object)
        return test_object

    @staticmethod
    def container_auto_installation_script(test_object):
        """Agent installation script should allow us to install auto-injection software for containers

        https://feature-parity.us1.prod.dog/#/?feature=274
        """
        pytest.mark.features(feature_id=274)(test_object)
        return test_object

    @staticmethod
    def host_auto_installation_script(test_object):
        """Agent installation script should allow us to install auto-injection software for hosts

        https://feature-parity.us1.prod.dog/#/?feature=275
        """
        pytest.mark.features(feature_id=275)(test_object)
        return test_object

    @staticmethod
    def host_block_list(test_object):
        """SSI block lists

        https://feature-parity.us1.prod.dog/#/?feature=276
        """
        pytest.mark.features(feature_id=276)(test_object)
        return test_object

    @staticmethod
    def aws_kinesis_span_creationcontext_propagation_via_message_attributes_with_dd_trace(
        test_object,
    ):
        """[AWS-Kinesis][Span Creation][Context Propagation] with dd-trace

        https://feature-parity.us1.prod.dog/#/?feature=280
        """
        pytest.mark.features(feature_id=280)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_base64_encoding(test_object):
        """DataStreams Monitoring support for V2 Base64 Encoding using dd-pathway-ctx/dd-pathway-ctx-base64

        https://feature-parity.us1.prod.dog/#/?feature=284
        """
        pytest.mark.features(feature_id=284)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_context_injection_base64(test_object):
        """Datastreams Monitoring support for V2 Base64 Encoding injection using dd-pathway-ctx-base64

        https://feature-parity.us1.prod.dog/#/?feature=287
        """
        pytest.mark.features(feature_id=287)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_kinesis(test_object):
        """DataStreams Monitoring support for AWS Kinesis

        https://feature-parity.us1.prod.dog/#/?feature=282
        """
        pytest.mark.features(feature_id=282)(test_object)
        return test_object

    @staticmethod
    def iast_sink_reflection_injection(test_object):
        """IAST Sink: Reflection Injection

        https://feature-parity.us1.prod.dog/#/?feature=279
        """
        pytest.mark.features(feature_id=279)(test_object)
        return test_object

    @staticmethod
    def embeded_git_reference(test_object):
        """Embedding Git references to build artifacts

        https://feature-parity.us1.prod.dog/#/?feature=286
        """
        pytest.mark.features(feature_id=286)(test_object)
        return test_object

    @staticmethod
    def k8s_admission_controller(test_object):
        """Auto inject the tracer library for k8s enviroments using admission controller

        https://feature-parity.us1.prod.dog/#/?feature=288
        """
        pytest.mark.features(feature_id=288)(test_object)
        return test_object

    @staticmethod
    def f_otel_interoperability(test_object):
        """OTel Interoperability

        https://feature-parity.us1.prod.dog/#/?feature=289
        """
        pytest.mark.features(feature_id=289)(test_object)
        return test_object

    @staticmethod
    def debugger_pii_redaction(test_object):
        """PII Redaction

        https://feature-parity.us1.prod.dog/#/?feature=291
        """
        pytest.mark.features(feature_id=291)(test_object)
        return test_object

    @staticmethod
    def installer_auto_instrumentation(test_object):
        """Installer auto-instrumentation

        https://feature-parity.us1.prod.dog/#/?feature=292
        """
        pytest.mark.features(feature_id=292)(test_object)
        return test_object

    @staticmethod
    def rasp_local_file_inclusion(test_object):
        """Appsec RASP rule : local file inclusion

        https://feature-parity.us1.prod.dog/#/?feature=293
        """
        pytest.mark.features(feature_id=293)(test_object)
        return test_object

    @staticmethod
    def rasp_server_side_request_forgery(test_object):
        """Appsec RASP rule : server-side request forgery

        https://feature-parity.us1.prod.dog/#/?feature=294
        """
        pytest.mark.features(feature_id=294)(test_object)
        return test_object

    @staticmethod
    def rasp_sql_injection(test_object):
        """Appsec RASP rule : SQL injection

        https://feature-parity.us1.prod.dog/#/?feature=295
        """
        pytest.mark.features(feature_id=295)(test_object)
        return test_object

    @staticmethod
    def database_monitoring_support(test_object):
        """DBM: Database Monitoring is supported by an integration

        https://feature-parity.us1.prod.dog/#/?feature=296
        """
        pytest.mark.features(feature_id=296)(test_object)
        return test_object

    @staticmethod
    def rasp_stack_trace(test_object):
        """Appsec RASP: Stack Trace

        https://feature-parity.us1.prod.dog/#/?feature=297
        """
        pytest.mark.features(feature_id=297)(test_object)
        return test_object

    @staticmethod
    def rasp_span_tags(test_object):
        """Appsec RASP: Span Tags

        https://feature-parity.us1.prod.dog/#/?feature=298
        """
        pytest.mark.features(feature_id=298)(test_object)
        return test_object

    @staticmethod
    def debugger_expression_language(test_object):
        """Expression Language

        https://feature-parity.us1.prod.dog/#/?feature=303
        """
        pytest.mark.features(feature_id=303)(test_object)
        return test_object

    @staticmethod
    def auto_instrumentation_profiling(test_object):
        """auto-instrumentation with profiling

        https://feature-parity.us1.prod.dog/#/?feature=302
        """
        pytest.mark.features(feature_id=302)(test_object)
        return test_object

    @staticmethod
    def appsec_standalone_experimental(test_object):
        """Experimental Appsec Standalone Billing

        https://feature-parity.us1.prod.dog/#/?feature=305
        """
        pytest.mark.features(feature_id=305)(test_object)
        return test_object

    @staticmethod
    def appsec_standalone(test_object):
        """Appsec Standalone Billing

        https://feature-parity.us1.prod.dog/#/?feature=355
        """
        pytest.mark.features(feature_id=355)(test_object)
        return test_object

    @staticmethod
    def iast_standalone_experimental(test_object):
        """Experimental Iast Standalone Billing

        https://feature-parity.us1.prod.dog/#/?feature=319
        """
        pytest.mark.features(feature_id=319)(test_object)
        return test_object

    @staticmethod
    def iast_standalone(test_object):
        """Iast Standalone Billing V2

        https://feature-parity.us1.prod.dog/#/?feature=356
        """
        pytest.mark.features(feature_id=356)(test_object)
        return test_object

    @staticmethod
    def sca_standalone_experimental(test_object):
        """Experimental SCA Standalone Billing

        https://feature-parity.us1.prod.dog/#/?feature=320
        """
        pytest.mark.features(feature_id=320)(test_object)
        return test_object

    @staticmethod
    def sca_standalone(test_object):
        """SCA Standalone Billing V2

        https://feature-parity.us1.prod.dog/#/?feature=357
        """
        pytest.mark.features(feature_id=357)(test_object)
        return test_object

    @staticmethod
    def security_events_metastruct(test_object):
        """Appsec meta struct

        https://feature-parity.us1.prod.dog/#/?feature=314
        """
        pytest.mark.features(feature_id=314)(test_object)
        return test_object

    @staticmethod
    def host_auto_installation_script_profiling(test_object):
        """Profiling works when enabled through the agent installer script in Host environments

        https://feature-parity.us1.prod.dog/#/?feature=306
        """
        pytest.mark.features(feature_id=306)(test_object)
        return test_object

    @staticmethod
    def container_auto_installation_script_profiling(test_object):
        """Profiling works when enabled through the agent installer script in Container environments

        https://feature-parity.us1.prod.dog/#/?feature=307
        """
        pytest.mark.features(feature_id=307)(test_object)
        return test_object

    @staticmethod
    def container_auto_instrumentation_profiling(test_object):
        """Profiling works when manually enabled with library injection in Container environments

        https://feature-parity.us1.prod.dog/#/?feature=310
        """
        pytest.mark.features(feature_id=310)(test_object)
        return test_object

    @staticmethod
    def host_guardrail(test_object):
        """When in SSI, bail out if our version of language is incompatible.

        https://feature-parity.us1.prod.dog/#/?feature=308
        """
        pytest.mark.features(feature_id=308)(test_object)
        return test_object

    @staticmethod
    def container_guardrail(test_object):
        """When in SSI, bail out if our version of language is incompatible or container is incompatible.

        https://feature-parity.us1.prod.dog/#/?feature=309
        """
        pytest.mark.features(feature_id=309)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_support_for_manual_checkpoints(test_object):
        """Ensure DSM Manual Checkpointing API is satisfied

        https://feature-parity.us1.prod.dog/#/?feature=327
        """
        pytest.mark.features(feature_id=327)(test_object)
        return test_object

    @staticmethod
    def suspicious_attacker_blocking(test_object):
        """Threats: request blocking on suspicious attacker

        https://feature-parity.us1.prod.dog/#/?feature=311
        """
        pytest.mark.features(feature_id=311)(test_object)
        return test_object

    @staticmethod
    def user_id_collection_modes(test_object):
        """Threats: User ID collection modes

        https://feature-parity.us1.prod.dog/#/?feature=312
        """
        pytest.mark.features(feature_id=312)(test_object)
        return test_object

    @staticmethod
    def fingerprinting(test_object):
        """Threats: Requests Fingerprinting

        https://feature-parity.us1.prod.dog/#/?feature=313
        """
        pytest.mark.features(feature_id=313)(test_object)
        return test_object

    @staticmethod
    def iast_sink_untrusted_deserialization(test_object):
        """IAST Sink: Untrusted Deserialization

        https://feature-parity.us1.prod.dog/#/?feature=316
        """
        pytest.mark.features(feature_id=316)(test_object)
        return test_object

    @staticmethod
    def crashtracking(test_object):
        """Crashtracking

        https://feature-parity.us1.prod.dog/#/?feature=317
        """
        pytest.mark.features(feature_id=317)(test_object)
        return test_object

    @staticmethod
    def rasp_shell_injection(test_object):
        """Appsec RASP rule : shell injection

        https://feature-parity.us1.prod.dog/#/?feature=318
        """
        pytest.mark.features(feature_id=318)(test_object)
        return test_object

    @staticmethod
    def rasp_command_injection(test_object):
        """Appsec RASP rule : command injection

        https://feature-parity.us1.prod.dog/#/?feature=345
        """
        pytest.mark.features(feature_id=345)(test_object)
        return test_object

    @staticmethod
    def debugger_exception_replay(test_object):
        """Exception replay

        https://feature-parity.us1.prod.dog/#/?feature=321
        """
        pytest.mark.features(feature_id=321)(test_object)
        return test_object

    @staticmethod
    def iast_source_path_parameter(test_object):
        """IAST Source: URI

        https://feature-parity.us1.prod.dog/#/?feature=324
        """
        pytest.mark.features(feature_id=324)(test_object)
        return test_object

    @staticmethod
    def iast_source_sql(test_object):
        """IAST Source: SQL

        https://feature-parity.us1.prod.dog/#/?feature=344
        """
        pytest.mark.features(feature_id=344)(test_object)
        return test_object

    @staticmethod
    def ssi_guardrails(test_object):
        """Docker ssi guardrails

        https://feature-parity.us1.prod.dog/#/?feature=322
        """
        pytest.mark.features(feature_id=322)(test_object)
        return test_object

    @staticmethod
    def ssi_crashtracking(test_object):
        """Docker ssi crashtracking

        https://feature-parity.us1.prod.dog/#/?feature=340
        """
        pytest.mark.features(feature_id=340)(test_object)
        return test_object

    @staticmethod
    def ssi_service_naming(test_object):
        """Docker ssi service naming feature

        https://feature-parity.us1.prod.dog/#/?feature=326
        """
        pytest.mark.features(feature_id=326)(test_object)
        return test_object

    @staticmethod
    def ssi_service_tracking(test_object):
        """SSI service tracking feature

        https://feature-parity.us1.prod.dog/#/?feature=327
        """
        pytest.mark.features(feature_id=327)(test_object)
        return test_object

    @staticmethod
    def serverless_span_pointers(test_object):
        """Serverless : Span Pointers are correctly incorporated in spans

        https://feature-parity.us1.prod.dog/#/?feature=328
        """
        pytest.mark.features(feature_id=328)(test_object)
        return test_object

    @staticmethod
    def aws_api_gateway_inferred_span_creation(test_object):
        """AWS Api Gateway: Tests that API Gateway inferred span creation works as expected

        https://feature-parity.us1.prod.dog/#/?feature=341
        """
        pytest.mark.features(feature_id=341)(test_object)

        return test_object

    @staticmethod
    def parametric_endpoint_parity(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=339
        """
        pytest.mark.features(feature_id=339)(test_object)
        return test_object

    @staticmethod
    def iast_stack_trace(test_object):
        """IAST: Stack Trace

        https://feature-parity.us1.prod.dog/#/?feature=329
        """
        pytest.mark.features(feature_id=329)(test_object)
        return test_object

    @staticmethod
    def iast_extended_location(test_object):
        """IAST: Extended location data

        https://feature-parity.us1.prod.dog/#/?feature=364
        """
        pytest.mark.features(feature_id=364)(test_object)
        return test_object

    @staticmethod
    def djm_ssi_k8s(test_object):
        """Data Jobs Monitoring: Java lib auto instrumentation for Spark applications on K8s.

        https://feature-parity.us1.prod.dog/#/?feature=342
        """
        pytest.mark.features(feature_id=342)(test_object)
        return test_object

    @staticmethod
    def adaptive_sampling(test_object):
        """Adaptive sampling rules + RC

        https://feature-parity.us1.prod.dog/#/?feature=346
        """
        pytest.mark.features(feature_id=346)(test_object)
        return test_object

    @staticmethod
    def agent_host_ipv6(test_object):
        """DD_AGENT_HOST supports an IPv6 address

        https://feature-parity.us1.prod.dog/#/?feature=347
        """
        pytest.mark.features(feature_id=347)(test_object)
        return test_object

    @staticmethod
    def datadog_baggage_headers(test_object):
        """Baggage support

        https://feature-parity.us1.prod.dog/#/?feature=389
        """
        pytest.mark.features(feature_id=389)(test_object)
        return test_object

    @staticmethod
    def iast_security_controls(test_object):
        """IAST: Security Controls

        https://feature-parity.us1.prod.dog/#/?feature=343
        """
        pytest.mark.features(feature_id=343)(test_object)
        return test_object

    @staticmethod
    def graphql_query_error_reporting(test_object):
        """GraphQL query error reporting

        https://feature-parity.us1.prod.dog/#/?feature=354
        """
        pytest.mark.features(feature_id=354)(test_object)
        return test_object

    @staticmethod
    def envoy_external_processing(test_object):
        """Support for Envoy External Processing

        https://feature-parity.us1.prod.dog/#/?feature=350
        """
        pytest.mark.features(feature_id=350)(test_object)
        return test_object

    @staticmethod
    def context_propagation_extract_behavior(test_object):
        """Context Propagation: Extraction behavior can be configured at the service level

        https://feature-parity.us1.prod.dog/#/?feature=353
        """
        pytest.mark.features(feature_id=353)(test_object)
        return test_object

    @staticmethod
    def iast_sink_email_html_injection(test_object):
        """IAST Sink: Email HTML injection

        https://feature-parity.us1.prod.dog/#/?feature=358
        """
        pytest.mark.features(feature_id=358)(test_object)
        return test_object

    @staticmethod
    def language_specifics(test_object):
        """Language specific tests

        https://feature-parity.us1.prod.dog/#/?feature=359
        """
        pytest.mark.features(feature_id=359)(test_object)
        return test_object

    @staticmethod
    def debugger_code_origins(test_object):
        """Code Origins

        https://feature-parity.us1.prod.dog/#/?feature=360
        """
        pytest.mark.features(feature_id=360)(test_object)
        return test_object

    @staticmethod
    def debugger_probe_budgets(test_object):
        """Probe Budgets

        https://feature-parity.us1.prod.dog/#/?feature=368
        """
        pytest.mark.features(feature_id=368)(test_object)
        return test_object

    @staticmethod
    def debugger_method_probe(test_object):
        """Method-level Probes

        https://feature-parity.us1.prod.dog/#/?feature=392
        """
        pytest.mark.features(feature_id=392)(test_object)
        return test_object

    @staticmethod
    def debugger_line_probe(test_object):
        """Line-level Probes

        https://feature-parity.us1.prod.dog/#/?feature=393
        """
        pytest.mark.features(feature_id=393)(test_object)
        return test_object

    @staticmethod
    def debugger_symdb(test_object):
        """Probe Budgets

        https://feature-parity.us1.prod.dog/#/?feature=370
        """
        pytest.mark.features(feature_id=370)(test_object)
        return test_object

    @staticmethod
    def otel_propagators_api(test_object):
        """OpenTelemetry Propagators API

        https://feature-parity.us1.prod.dog/#/?feature=361
        """
        pytest.mark.features(feature_id=361)(test_object)
        return test_object

    @staticmethod
    def stable_configuration_support(test_object):
        """Enforces that basic stable configuration support exists

        https://feature-parity.us1.prod.dog/#/?feature=365
        """
        pytest.mark.features(feature_id=365)(test_object)
        return test_object

    @staticmethod
    def single_span_ingestion_control(test_object):
        """Enforces that basic stable configuration support exists

        https://feature-parity.us1.prod.dog/#/?feature=366
        """
        pytest.mark.features(feature_id=366)(test_object)
        return test_object

    @staticmethod
    def process_discovery(test_object):
        """Process Disocvery

        https://feature-parity.us1.prod.dog/#/?feature=367
        """
        pytest.mark.features(feature_id=367)(test_object)
        return test_object

    @staticmethod
    def debugger_inproduct_enablement(test_object):
        """Dynamically enable debugger products

        https://feature-parity.us1.prod.dog/#/?feature=369
        """
        pytest.mark.features(feature_id=369)(test_object)
        return test_object

    @staticmethod
    def datastreams_monitoring_protobuf_schema_tracking(test_object):
        """Dynamically enable debugger products

        https://feature-parity.us1.prod.dog/#/?feature=371
        """
        pytest.mark.features(feature_id=371)(test_object)
        return test_object

    @staticmethod
    def trace_enablement(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=374
        """
        pytest.mark.features(feature_id=374)(test_object)
        return test_object

    @staticmethod
    def trace_log_directory(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=375
        """
        pytest.mark.features(feature_id=375)(test_object)
        return test_object

    @staticmethod
    def trace_experimental_features(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=376
        """
        pytest.mark.features(feature_id=376)(test_object)
        return test_object

    @staticmethod
    def trace_rate_limiting(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=377
        """
        pytest.mark.features(feature_id=377)(test_object)
        return test_object

    @staticmethod
    def trace_http_server_error_statuses(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=378
        """
        pytest.mark.features(feature_id=379)(test_object)
        return test_object

    @staticmethod
    def trace_http_client_error_statuses(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=381
        """
        pytest.mark.features(feature_id=381)(test_object)
        return test_object

    @staticmethod
    def trace_http_client_tag_query_string(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=382
        """
        pytest.mark.features(feature_id=382)(test_object)
        return test_object

    @staticmethod
    def unified_service_tagging(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=384
        """
        pytest.mark.features(feature_id=384)(test_object)
        return test_object

    @staticmethod
    def integration_enablement(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=385
        """
        pytest.mark.features(feature_id=385)(test_object)
        return test_object

    @staticmethod
    def log_injection_128bit_traceid(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=387
        """
        pytest.mark.features(feature_id=387)(test_object)
        return test_object

    @staticmethod
    def iast_schema(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=394
        """
        pytest.mark.features(feature_id=394)(test_object)
        return test_object

    @staticmethod
    def iast_vuln_sampling_route_method_count_algorithm(test_object):
        """Vulnerability sampling algorithm by route, method and counts for IAST.

        https://feature-parity.us1.prod.dog/#/?feature=395
        """
        pytest.mark.features(feature_id=395)(test_object)
        return test_object

    @staticmethod
    def appsec_collect_all_headers(test_object):
        """Appsec collects all headers

        https://feature-parity.us1.prod.dog/#/?feature=390
        """
        pytest.mark.features(feature_id=390)(test_object)
        return test_object

    @staticmethod
    def appsec_collect_request_body(test_object):
        """Appsec collects request body

        https://feature-parity.us1.prod.dog/#/?feature=391
        """
        pytest.mark.features(feature_id=391)(test_object)
        return test_object

    @staticmethod
    def referrer_hostname(test_object):
        """Enforces standardized behaviors for configurations across the tracing libraries.

        https://feature-parity.us1.prod.dog/#/?feature=396
        """
        pytest.mark.features(feature_id=396)(test_object)
        return test_object

    @staticmethod
    def baggage_span_tags(test_object):
        """Automatically add baggage to span tags

        https://feature-parity.us1.prod.dog/#/?feature=470
        """
        pytest.mark.features(feature_id=470)(test_object)
        return test_object

    @staticmethod
    def remote_config_semantic_versioning(test_object):
        """Semantic version 2 is reported in remote config

        https://feature-parity.us1.prod.dog/#/?feature=472
        """
        pytest.mark.features(feature_id=472)(test_object)
        return test_object

    @staticmethod
    def process_tags(test_object):
        """Process tags

        https://feature-parity.us1.prod.dog/#/?feature=475
        """
        pytest.mark.features(feature_id=475)(test_object)
        return test_object

    @staticmethod
    def appsec_rc_asm_dd_multiconfig(test_object):
        """Appsec supports multiple configurations through ASM_DD

        https://feature-parity.us1.prod.dog/#/?feature=473
        """
        pytest.mark.features(feature_id=473)(test_object)
        return test_object

    @staticmethod
    def appsec_trace_tagging_rules(test_object):
        """Appsec supports trace-tagging rules

        https://feature-parity.us1.prod.dog/#/?feature=474
        """
        pytest.mark.features(feature_id=474)(test_object)
        return test_object

    @staticmethod
    def unstructured_log_injection(test_object):
        """DD_LOGS_INJECTION_FORCED=true

        https://feature-parity.us1.prod.dog/#/?feature=477
        """
        pytest.mark.features(feature_id=477)(test_object)
        return test_object

    @staticmethod
    def auto_instrumentation_appsec(test_object):
        """Appsec works when manually enabled with library injection in Host environments

        https://feature-parity.us1.prod.dog/#/?feature=478
        """
        pytest.mark.features(feature_id=478)(test_object)
        return test_object

    @staticmethod
    def host_auto_installation_script_appsec(test_object):
        """Appsec works when enabled through the agent installer script in Host environments

        https://feature-parity.us1.prod.dog/#/?feature=479
        """
        pytest.mark.features(feature_id=479)(test_object)
        return test_object

    @staticmethod
    def container_auto_installation_script_appsec(test_object):
        """Appsec works when enabled through the agent installer script in Container environments

        https://feature-parity.us1.prod.dog/#/?feature=480
        """
        pytest.mark.features(feature_id=480)(test_object)
        return test_object

    @staticmethod
    def ssi_injection_metadata(test_object):
        """Appsec supports trace-tagging rules

        https://feature-parity.us1.prod.dog/#/?feature=481
        """
        pytest.mark.features(feature_id=481)(test_object)
        return test_object


features = _Features()

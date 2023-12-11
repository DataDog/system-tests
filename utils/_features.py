import pytest
import requests


def _feature(feature_id: int):
    def decorate(test_object):
        pytest.mark.features(feature_id=feature_id)(test_object)
        return test_object

    return staticmethod(decorate)


class features:
    """https://dd-feature-parity.azurewebsites.net/Import/Features"""

    add_metadata_globally_to_all_spans_dd_tags = _feature(1)
    change_agent_hostname_dd_agent_host = _feature(2)
    add_metadata_to_spans_via_tags_dd_trace_analytics_enabled = _feature(3)
    trace_search_automatic_config = _feature(4)
    manual_trace_id_injection_into_logs = _feature(5)
    unix_domain_sockets_support_for_traces = _feature(6)
    unix_domain_sockets_automatic_detection = _feature(7)
    twl_customer_controls_ingestion_dd_trace_sampling_rules = _feature(8)
    synthetic_apm_http_header_span_tag_x_datadog_origin = _feature(9)
    log_tracer_status_at_startup = _feature(10)
    fargate_14_tagging_support = _feature(11)
    container_tagging = _feature(12)
    b3_headers_injection_and_extraction = _feature(13)
    unix_domain_sockets_support_for_metrics = _feature(14)
    support_ddmeasured = _feature(15)
    dd_service_mapping = _feature(16)
    datadog_managed_dogstatsd_client = _feature(17)
    http_headers_as_tags_dd_trace_header_tags = _feature(18)
    dd_profiling_enabled = _feature(19)
    dogstatsd_unified_service_tagging = _feature(20)
    trace_log_exporting_for_aws_lambda = _feature(21)
    runtime_id_in_span_metadata_for_service_entry_spans = _feature(22)
    partial_flush = _feature(23)
    partial_flush_on_by_default = _feature(24)
    automatic_trace_id_injection_into_logs = _feature(25)
    mapping_http_status_codes_to_errors = _feature(26)
    log_pipelines_updated_for_log_injection = _feature(27)
    inject_service_env_version_into_logs = _feature(28)
    top_level_detection_in_tracer = _feature(29)
    use_sampling_priorities_2_1_in_rules_based_sampler = _feature(30)
    trace_annotation = _feature(31)
    runtime_metrics = _feature(32)
    logs_throttling = _feature(33)
    post_processing_traces = _feature(34)
    span_baggage_item = _feature(35)
    tracer_health_metrics = _feature(36)
    kafka_tracing = _feature(37)
    numeric_tags_for_trace_search_analytics_step_1 = _feature(38)
    grpc_integration_tags = _feature(39)
    dd_trace_config_file = _feature(40)
    dd_trace_methods = _feature(41)
    dd_tags_space_separated_tags = _feature(42)
    report_tracer_drop_rate_ddtracer_kr = _feature(43)
    obfuscation_of_pii_from_web_span_resource_names = _feature(44)
    windows_named_pipe_support_for_traces = _feature(45)
    setting_to_rename_service_by_tag_split_by_tag = _feature(46)
    collect_application_version_information = _feature(47)
    ensure_that_sampling_is_consistent_across_languages = _feature(48)
    user_troubleshooting_tool = _feature(49)
    option_to_remap_apm_error_response_severity_eg_404_to_error = _feature(50)
    obfuscation_of_httpurl_span_tag = _feature(51)
    dd_trace_report_hostname = _feature(52)
    windows_named_pipe_support_for_metrics = _feature(53)
    ensure_consistent_http_client_integration_tags = _feature(54)
    aws_sdk_integration_tags = _feature(55)
    dont_set_username_tag_because_its_pii = _feature(56)
    trace_client_app_tagging = _feature(57)
    client_split_by_domain_service_host = _feature(58)
    horizontal_propagation_of_x_datadog_tags_between_services = _feature(59)
    vertical_propagation_of_x_datadog_tags_onto_each_chunk_root_span = _feature(60)
    creation_and_propagation_of_ddpdm = _feature(61)
    client_side_stats_supported = _feature(62)
    client_side_stats_on_by_default = _feature(63)
    instrumentation_telemetry_enabled_by_default = _feature(64)
    dd_instrumentation_telemetry_enabled_supported = _feature(65)
    app_environment_collected = _feature(66)
    dependencies_collected = _feature(67)
    integrations_enabled_collected = _feature(68)
    tracer_configurations_collected = _feature(69)
    heart_beat_collected = _feature(70)
    app_close_collected = _feature(71)
    logs_collected = _feature(72)
    metrics_collected = _feature(73)
    api_v2_implemented = _feature(74)
    app_client_configuration_change_event = _feature(75)
    app_product_change_event = _feature(76)
    app_extended_heartbeat_event = _feature(77)
    message_batch = _feature(78)
    app_started_changes = _feature(79)
    dd_telemetry_dependency_collection_enabled_supported = _feature(80)
    additional_http_headers_supported = _feature(81)
    remote_config_object_supported = _feature(82)
    w3c_headers_injection_and_extraction = _feature(83)
    otel_api = _feature(84)
    trace_id_generation_propagation_128_bit = _feature(85)
    span_events = _feature(86)
    span_links = _feature(87)
    client_ip_adress_collection_dd_trace_client_ip_enabled = _feature(88)
    host_auto_instrumentation = _feature(89)
    container_auto_instrumentation = _feature(90)
    collect_http_post_data_and_headers = _feature(94)
    weak_hash_vulnerability_detection = _feature(96)
    db_integrations = _feature(98)
    http_threats_management = _feature(99)
    weak_cipher_detection = _feature(100)
    threats_alpha_preview = _feature(110)
    procedure_to_debug_install = _feature(113)
    security_events_metadata = _feature(124)
    rate_limiter = _feature(134)
    support_in_app_waf_metrics_report = _feature(140)
    user_monitoring = _feature(141)
    serialize_waf_rules_without_limiting_their_sizes = _feature(142)
    threats_configuration = _feature(143)
    sensitive_data_obfuscation = _feature(144)
    propagation_of_user_id_rfc = _feature(146)
    onboarding = _feature(154)
    deactivate_rules_using_rc = _feature(157)
    shell_execution_tracing = _feature(158)
    appsec_userid_blocking = _feature(160)
    custom_business_logic_events = _feature(161)
    graphql_threats_detection = _feature(162)
    iast_sink_sql_injection = _feature(165)
    iast_sink_command_injection = _feature(166)
    iast_sink_path_traversal = _feature(167)
    iast_sink_ldap_injection = _feature(168)
    iast_source_request_parameter_value = _feature(169)
    iast_source_request_parameter_name = _feature(170)
    iast_source_header_value = _feature(171)
    iast_source_header_name = _feature(172)
    iast_source_cookie_value = _feature(173)
    iast_source_cookie_name = _feature(174)
    iast_source_body = _feature(175)
    grpc_threats_management = _feature(176)
    telemetry = _feature(178)
    kafkaspan_creationcontext_propagation_with_dd_trace_py = _feature(192)


def _main():
    """Display missing features"""

    existing_features = set()
    for attr in dir(features):
        if attr.startswith("__"):
            continue

        decorator = getattr(features, attr)

        def obj():
            pass

        obj = decorator(obj)

        existing_features.add(obj.pytestmark[0].kwargs["feature_id"])

    data = requests.get("https://dd-feature-parity.azurewebsites.net/Import/Features", timeout=10).json()
    for feature in data:
        feature_id = feature["id"]
        if feature_id not in existing_features:
            print(f"    {feature['codeSafeName'].lower()} = _feature({feature_id})")


if __name__ == "__main__":
    _main()

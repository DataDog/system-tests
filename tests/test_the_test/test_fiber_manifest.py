import pytest

from utils import features, scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest, SkipDeclaration


DEBUGGER_NODEIDS = [
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Line_Probe_Snaphots::test_log_line_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Line_Probe_Snaphots_With_SCM::test_log_line_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Method_Probe_Snaphots::test_log_method_snapshot",
    "tests/debugger/test_debugger_probe_snapshot.py::Test_Debugger_Method_Probe_Snaphots_With_SCM::test_log_method_snapshot",
    "tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses::test_log_method_status",
]


# These tests passed in the Fiber matrix, so Fiber must not disable them.
# They check the tracer, the AppSec SDK, remote-configuration capabilities,
# telemetry, or gRPC. Some are negative checks (for example "no event" or "not
# blocked"); these pass now because Fiber HTTP AppSec is absent, and they will
# catch regressions when it is added. The agentic-onboarding tests ran only on
# the main tracer; the Go-wide version gate still applies to 2.10.1.
FIBER_ENABLED_APPSEC_NODEIDS = [
    "tests/appsec/api_security/test_custom_data_classification.py::Test_API_Security_Custom_Data_Classification_Capabilities::test_capabilities_check",
    "tests/appsec/rasp/test_api10.py::Test_API10_without_downstream_body_analysis_using_max::test_api10_res_body",
    "tests/appsec/rasp/test_api10.py::Test_API10_without_downstream_body_analysis_using_sample_rate::test_api10_res_body",
    "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Rules_Version::test_min_version",
    "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Waf_Version::test_min_version",
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_Capability::test_sqli_capability",
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_Rules_Version::test_min_version",
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_Waf_Version::test_min_version",
    "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Capability::test_ssrf_capability",
    "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Rules_Version::test_min_version",
    "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Waf_Version::test_min_version",
    "tests/appsec/smoke_tests/test_apm_standalone.py::Test_AppSecAPMStandalone_Telemetry::test_telemetry_smoke",
    "tests/appsec/smoke_tests/test_apm_standalone.py::Test_AppSecStandaloneAPMStandalone_Telemetry::test_telemetry_smoke",
    "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_verbatim",
    "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_verbatim_appsec_disabled",
    "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_when_unset",
    "tests/appsec/test_blocking_addresses.py::Test_Blocking_request_query::test_non_blocking_case_sensitive",
    "tests/appsec/test_client_ip.py::Test_StandardTagsClientIp::test_not_reported",
    "tests/appsec/test_conf.py::Test_ConfigurationVariables::test_disabled",
    "tests/appsec/test_conf.py::Test_ConfigurationVariables::test_waf_timeout",
    "tests/appsec/test_customconf.py::Test_ConfRuleSet::test_log",
    "tests/appsec/test_customconf.py::Test_CorruptedRules::test_c05",
    "tests/appsec/test_customconf.py::Test_MissingRules::test_c04",
    "tests/appsec/test_event_tracking_v2.py::Test_UserLoginFailureEventV2_HeaderCollection_AppsecDisabled::test_user_login_failure_header_collection",
    "tests/appsec/test_event_tracking_v2.py::Test_UserLoginSuccessEventV2_HeaderCollection_AppsecDisabled::test_user_login_success_header_collection",
    "tests/appsec/test_extended_data_collection.py::Test_ExtendedRequestBodyCollection::test_no_extended_request_body_collection_without_event",
    "tests/appsec/test_fingerprinting.py::Test_Fingerprinting_Endpoint_Capability::test_fingerprinting_endpoint_capability",
    "tests/appsec/test_fingerprinting.py::Test_Fingerprinting_Header_Capability::test_fingerprinting_endpoint_capability",
    "tests/appsec/test_fingerprinting.py::Test_Fingerprinting_Network_Capability::test_fingerprinting_endpoint_capability",
    "tests/appsec/test_fingerprinting.py::Test_Fingerprinting_Session_Capability::test_fingerprinting_endpoint_capability",
    "tests/appsec/test_identify.py::Test_Basic::test_identify_tags_with_attack",
    "tests/appsec/test_remote_config_rule_changes.py::Test_AsmDdMultiConfiguration::test_asm_dd_multiconfig_capability",
    "tests/appsec/test_runtime_activation.py::Test_RuntimeActivationCapabilities::test_capabilities",
    "tests/appsec/test_runtime_activation.py::Test_RuntimeActivationCapabilitiesCleared::test_capabilities",
    "tests/appsec/test_trace_tagging.py::Test_TraceTaggingRulesRcCapability::test_trace_tagging_rules_capability",
    "tests/appsec/test_traces.py::Test_AppSecEventSpanTags::test_root_span_coherence",
    "tests/appsec/test_user_blocking_full_denylist.py::Test_UserBlocking_FullDenylist::test_nonblocking_test",
    "tests/appsec/test_versions.py::Test_Events::test_appsec_in_traces",
    "tests/appsec/waf/test_addresses.py::Test_GrpcServerMethod::test_grpc_server_method_rule",
    "tests/appsec/waf/test_addresses.py::Test_GrpcServerMethod::test_streaming_grpc_server_method_rule",
    "tests/appsec/waf/test_addresses.py::Test_gRPC::test_basic",
    "tests/appsec/waf/test_telemetry.py::Test_TelemetryMetrics::test_headers_are_correct",
    "tests/appsec/waf/test_telemetry.py::Test_TelemetryMetrics::test_metric_waf_init",
    "tests/test_library_conf.py::Test_HeaderTags_Colon_Leading::test_trace_header_tags",
    "tests/test_library_conf.py::Test_HeaderTags_Colon_Trailing::test_trace_header_tags",
]

# These tests need Fiber HTTP AppSec protection and failed in the same matrix.
FIBER_DISABLED_APPSEC_NODEIDS = [
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_UrlQuery::test_sqli_get",
    "tests/appsec/test_blocking_addresses.py::Test_Blocking_request_query::test_blocking",
    "tests/appsec/test_conf.py::Test_ConfigurationVariables::test_enabled",
    "tests/appsec/test_customconf.py::Test_ConfRuleSet::test_requests",
    "tests/appsec/waf/test_addresses.py::Test_UrlQuery::test_query_argument",
    "tests/appsec/waf/test_blocking.py::Test_Blocking::test_no_accept",
    "tests/appsec/waf/test_telemetry.py::Test_TelemetryMetrics::test_metric_waf_requests",
]


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    ("agent_version", "has_bug"),
    [
        ("7.78.0", False),
        ("7.79.0-dev", False),
        ("7.79.0-devel", True),
        ("7.79.0-rc.1", True),
        ("7.79.0", True),
        ("7.83.2", True),
    ],
)
def test_fiber_debugger_bug_is_version_scoped(agent_version: str, *, has_bug: bool) -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev"), "agent": Version(agent_version)}, "fiber-v2-orchestrion")
    expected = [SkipDeclaration("bug", "DEBUG-5421")] if has_bug else []
    for nodeid in DEBUGGER_NODEIDS:
        assert manifest.get_declarations(nodeid) == expected, nodeid

    # Do not disable the whole class or add the Agent bug to unrelated probe types.
    assert (
        manifest.get_declarations("tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses")
        == []
    )
    assert manifest.get_declarations(
        "tests/debugger/test_debugger_probe_status.py::Test_Debugger_Method_Probe_Statuses::test_metric_status"
    ) == [SkipDeclaration("missing_feature", "Not yet implemented")]


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("weblog", ["fiber-v2-orchestrion", "net-http-orchestrion", "gin"])
@pytest.mark.parametrize(
    "test_name", ["test_new_traceid", "test_incoming_64bit_traceid", "test_incoming_128bit_traceid"]
)
def test_fiber_inherits_only_the_automatic_log_injection_bug(weblog: str, test_name: str) -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev")}, weblog)
    expected = [] if weblog == "gin" else [SkipDeclaration("bug", "APMLP-659")]
    assert (
        manifest.get_declarations(
            f"tests/test_config_consistency.py::Test_Config_LogInjection_128Bit_TraceId_Disabled::{test_name}"
        )
        == expected
    )


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("library_version", ["1.72.0", "1.73.0-dev", "2.10.1", "2.12.0-dev.3"])
@pytest.mark.parametrize("weblog", ["fiber-v2-orchestrion", "net-http-orchestrion", "gin"])
def test_fiber_standalone_requires_http_appsec_support(library_version: str, weblog: str) -> None:
    manifest = Manifest({"golang": Version(library_version)}, weblog)
    if weblog == "fiber-v2-orchestrion":
        expected = [SkipDeclaration("missing_feature", "Fiber HTTP AppSec support is not released")]
    elif Version(library_version) < Version("1.73.0-dev"):
        expected = [SkipDeclaration("missing_feature", "declared version for golang is v1.73.0-dev")]
    else:
        expected = []
    nodeid = "tests/appsec/test_asm_standalone.py::Test_AppSecStandalone_UpstreamPropagation_V2"
    assert manifest.get_declarations(nodeid) == expected
    assert (
        manifest.get_declarations(f"{nodeid}::test_no_appsec_upstream__no_asm_event__is_kept_with_priority_1__from_0")
        == expected
    )


@features.not_reported
@scenarios.test_the_test
def test_fiber_otlp_remains_enabled() -> None:
    manifest = Manifest({"golang": Version("2.12.0-dev"), "agent": Version("7.83.2")}, "fiber-v2-orchestrion")
    for nodeid in (
        "Test_Otel_Tracing_OTLP::test_single_server_trace",
        "Test_Otel_Tracing_OTLP::test_unsampled_trace",
        "Test_Otel_Tracing_OTLP::test_128bit_trace_id_consistent_across_spans",
        "Test_Otlp_Carries_Ot::test_otlp_carries_ot",
        "Test_Otlp_Forwards_Inherited_Ot::test_otlp_forwards_inherited_ot",
    ):
        assert manifest.get_declarations(f"tests/otel/test_tracing_otlp.py::{nodeid}") == []


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("library_version", ["2.10.1", "2.12.0-dev.3"])
@pytest.mark.parametrize("nodeid", FIBER_ENABLED_APPSEC_NODEIDS)
def test_fiber_keeps_passing_appsec_checks_enabled(library_version: str, nodeid: str) -> None:
    manifest = Manifest({"golang": Version(library_version)}, "fiber-v2-orchestrion")
    expected = []
    if library_version == "2.10.1" and "test_agentic_onboarding.py" in nodeid:
        # The Go-wide version gate, not a Fiber declaration.
        expected = [SkipDeclaration("missing_feature", "declared version for golang is v2.11.0-dev")]
    assert manifest.get_declarations(nodeid) == expected


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize(
    "nodeid",
    [
        "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_verbatim",
        "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_verbatim_appsec_disabled",
        "tests/appsec/test_agentic_onboarding.py::Test_AppsecAgenticOnboarding::test_reported_when_unset",
        "tests/appsec/test_identify.py::Test_Basic::test_identify_tags_with_attack",
    ],
)
def test_fiber_enables_tracer_level_appsec_checks(nodeid: str) -> None:
    # Only the Go-wide version gate applies. It is satisfied on the main tracer.
    manifest = Manifest({"golang": Version("2.12.0-dev.3")}, "fiber-v2-orchestrion")
    assert manifest.get_declarations(nodeid) == []


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("library_version", ["2.10.1", "2.12.0-dev.3"])
@pytest.mark.parametrize("nodeid", FIBER_DISABLED_APPSEC_NODEIDS)
def test_fiber_still_disables_http_appsec_checks(library_version: str, nodeid: str) -> None:
    fiber = Manifest({"golang": Version(library_version)}, "fiber-v2-orchestrion")
    assert SkipDeclaration("missing_feature", "Fiber v2 has no HTTP AppSec integration") in fiber.get_declarations(
        nodeid
    )
    # The Fiber declaration must not change the reference weblogs.
    for weblog in ("gin", "net-http-orchestrion"):
        declarations = Manifest({"golang": Version(library_version)}, weblog).get_declarations(nodeid)
        assert not [d for d in declarations if (d.details or "").startswith("Fiber")]

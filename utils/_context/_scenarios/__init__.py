"""Every scenario, instantiated once. Each one is defined in a module of this package: nothing is set here, so that
modifying a scenario only runs this scenario in CI.
"""

import json

from utils.tools import update_environ_with_local_env

from ._core import DockerScenario, Scenario, scenario_groups, EndToEndScenario
from .ai_guard import (
    AiGuard,
    AiGuardRedactionDisabled,
    AiGuardRedactionTelemetry,
    AiGuardStandalone,
    AiGuardTelemetry,
)
from .apm_tracing import (
    ApmTracingE2eOtel,
    ApmTracingE2eSingleSpan,
    ApmTracingEfficientPayload,
    ApmTracingOtlp,
)
from .appsec import (
    AppsecCorruptedRules,
    AppsecCustomObfuscation,
    AppsecCustomRules,
    AppsecLowWafTimeout,
    AppsecMetaStructDisabled,
    AppsecMissingRules,
    AppsecRateLimiter,
    AppsecRulesMonitoringWithErrors,
    AppsecRuntimeActivation,
    AppsecWafTelemetry,
    EverythingDisabled,
    IastDeduplication,
    RuntimeScaReachability,
)
from .appsec_api_security import (
    AppsecApiSecurity,
    AppsecApiSecurityNoResponseBody,
    AppsecApiSecurityRc,
    AppsecApiSecurityWithSampling,
)
from .appsec_auto_events import (
    AppsecAtoSdk,
    AppsecAutoEventsExtended,
    AppsecAutoEventsRc,
)
from .appsec_blocking import (
    AppsecBlocking,
    AppsecBlockingFullDenylist,
)
from .aws_lambda import (
    AppsecLambdaApiSecurity,
    AppsecLambdaBlocking,
    AppsecLambdaDefault,
    AppsecLambdaInferredSpans,
    AppsecLambdaRasp,
)
from .appsec_rasp import (
    AppsecRasp,
    AppsecRaspNonBlocking,
    AppsecRaspWithoutDownstreamBodyAnalysisUsingMax,
    AppsecRaspWithoutDownstreamBodyAnalysisUsingSampleRate,
    AppsecStandaloneRasp,
)
from .appsec_standalone import (
    AppsecApmStandalone,
    AppsecStandalone,
    AppsecStandaloneApiSecurity,
    AppsecStandaloneApmStandalone,
    IastStandalone,
    ScaStandalone,
)
from .auto_injection import (
    ChaosInstallerAutoInjection,
    ContainerAutoInjectionInstallScript,
    ContainerAutoInjectionInstallScriptAppsec,
    ContainerAutoInjectionInstallScriptProfiling,
    HostAutoInjectionInstallScript,
    HostAutoInjectionInstallScriptAppsec,
    HostAutoInjectionInstallScriptProfiling,
    InstallerAutoInjection,
    InstallerNotSupportedAutoInjection,
    LocalAutoInjectionInstallScript,
    MultiInstallerAutoInjection,
    SimpleAutoInjectionAppsec,
    SimpleAutoInjectionProfiling,
    SimpleInstallerAutoInjection,
)
from .debugger import (
    DebuggerCaptureTimeout,
    DebuggerEvaluationTimeout,
    DebuggerExceptionReplay,
    DebuggerExpressionLanguage,
    DebuggerInproductEnablement,
    DebuggerPiiRedaction,
    DebuggerProbesSnapshot,
    DebuggerProbesSnapshotWithScm,
    DebuggerSymdb,
    DebuggerTelemetry,
)
from .default import (
    DefaultScenario,
)
from .docker_ssi import (
    DockerSsi,
    DockerSsiAppsec,
    DockerSsiCrashtracking,
    DockerSsiServicenaming,
)
from .agentless_endtoend import (
    FeatureFlaggingAndExperimentationAgentless,
    FeatureFlaggingAndExperimentationAgentlessDirect,
    FeatureFlaggingAndExperimentationAgentlessServerless,
)
from .test_the_test import (
    Fuzzer,
    MockTheTest,
    MockTheTest2,
    TestTheTest,
    Todo,
)
from .feature_flagging import (
    FeatureFlaggingAndExperimentation,
    FeatureFlaggingEvpStress,
    FeatureFlaggingEvaluationTelemetryOptOut,
    FeatureFlaggingEvaluationTelemetryOptOutDisabled,
)
from .graphql import (
    GraphqlAppsec,
    GraphqlErrorTracking,
)
from .integration_frameworks import (
    IntegrationFrameworksScenario,
)
from .integrations import (
    CrossedTracingLibraryScenario,
    DbmDynamicServiceScenario,
    Integrations,
    AWSIntegrationsScenario,
)
from .ipv6 import (
    IPV6Scenario,
)
from .k8s_injector_dev import (
    K8sInjectorDevSingleService,
)
from .k8s_lib_injection import (
    K8sLibInjection,
    K8sLibInjectionAppsecDisabled,
    K8sLibInjectionAppsecEnabled,
    K8sLibInjectionNoAc,
    K8sLibInjectionNoAcUds,
    K8sLibInjectionOperator,
    K8sLibInjectionProfilingDisabled,
    K8sLibInjectionProfilingEnabled,
    K8sLibInjectionProfilingOverride,
    K8sLibInjectionSparkDjm,
    K8sLibInjectionUds,
)
from .otel_collector import (
    OtelCollectorScenario,
)
from .open_telemetry import (
    OtelIntegrations,
    OtelLogE2e,
    OtelMetricE2e,
    OtelTracingE2e,
)
from .otel_semantics import (
    OtelSemanticsOtlp,
    OtelSemanticsOtlpCustomErrorStatuses,
    OtelSemanticsOtlpSamplingRules,
    OtelSemanticsOtlpTraceMetrics,
    OtelStartupLogs,
)
from .parametric import (
    ParametricScenario,
)
from .profiling import (
    ProfilingScenario,
)
from .remote_config import (
    RemoteConfigMockedBackendAsmDd,
    RemoteConfigMockedBackendAsmFeatures,
    RemoteConfigMockedBackendAsmFeaturesNocache,
    RemoteConfigMockedBackendLiveDebugging,
)
from .runtime_metrics import (
    OtlpRuntimeMetrics,
    RuntimeMetricsEnabled,
)
from .sampling import (
    Sampling,
    SamplingRateCapping,
    SamplingRulesAgentRate,
)
from .span_events import (
    AgentNotSupportingSpanEvents,
    AgentSupportingSpanEvents,
)
from .telemetry import (
    TelemetryAppStartedProductsDisabled,
    TelemetryDependencyLoadedTestForDependencyCollectionDisabled,
    TelemetryEnhancedConfigReporting,
    TelemetryExtendedHeartbeat,
    TelemetryLogGenerationDisabled,
    TelemetryMetricGenerationDisabled,
)
from .thread_context_sharing import (
    ThreadContextSharingScenario,
)
from .trace_stats import (
    TraceStatsComputation,
    TraceStatsComputationClientDropP0sFalse,
    TraceStatsComputationErrorSampler,
    TraceStatsComputationFutureObfuscationVersion,
    TraceStatsComputationMissingObfuscationVersion,
    TraceStatsComputationObfuscationDisabled,
    TraceStatsComputationObfuscationVersionZero,
)
from .tracing_config import (
    LibraryConfCustomHeaderTags,
    LibraryConfCustomHeaderTagsInvalid,
    TracePropagationStyleW3c,
    TracingConfigEmpty,
    TracingConfigNondefault,
    TracingConfigNondefault2,
    TracingConfigNondefault3,
    TracingConfigNondefault4,
)

__all__ = [
    "DockerScenario",
    "EndToEndScenario",
    "Scenario",
    "get_all_scenarios",
    "scenario_groups",
    "scenarios",
]

update_environ_with_local_env()


class _Scenarios:
    todo = Todo()
    test_the_test = TestTheTest()
    mock_the_test = MockTheTest()
    mock_the_test_2 = MockTheTest2()
    default = DefaultScenario()
    integrations = Integrations()
    integrations_aws = AWSIntegrationsScenario()
    dbm_dynamic_service = DbmDynamicServiceScenario()
    crossed_tracing_libraries = CrossedTracingLibraryScenario()
    otel_integrations = OtelIntegrations()
    profiling = ProfilingScenario()
    trace_stats_computation = TraceStatsComputation()
    trace_stats_computation_client_drop_p0s_false = TraceStatsComputationClientDropP0sFalse()
    trace_stats_computation_future_obfuscation_version = TraceStatsComputationFutureObfuscationVersion()
    trace_stats_computation_missing_obfuscation_version = TraceStatsComputationMissingObfuscationVersion()
    trace_stats_computation_obfuscation_version_zero = TraceStatsComputationObfuscationVersionZero()
    trace_stats_computation_obfuscation_disabled = TraceStatsComputationObfuscationDisabled()
    trace_stats_computation_error_sampler = TraceStatsComputationErrorSampler()
    sampling = Sampling()
    sampling_rate_capping = SamplingRateCapping()
    sampling_rules_agent_rate = SamplingRulesAgentRate()
    trace_propagation_style_w3c = TracePropagationStyleW3c()
    otel_startup_logs = OtelStartupLogs()
    otel_semantics_otlp = OtelSemanticsOtlp()
    otel_semantics_otlp_custom_error_statuses = OtelSemanticsOtlpCustomErrorStatuses()
    otel_semantics_otlp_trace_metrics = OtelSemanticsOtlpTraceMetrics()
    otel_semantics_otlp_sampling_rules = OtelSemanticsOtlpSamplingRules()
    # Telemetry scenarios
    telemetry_dependency_loaded_test_for_dependency_collection_disabled = (
        TelemetryDependencyLoadedTestForDependencyCollectionDisabled()
    )
    telemetry_app_started_products_disabled = TelemetryAppStartedProductsDisabled()
    telemetry_enhanced_config_reporting = TelemetryEnhancedConfigReporting()
    telemetry_log_generation_disabled = TelemetryLogGenerationDisabled()
    telemetry_metric_generation_disabled = TelemetryMetricGenerationDisabled()
    telemetry_extended_heartbeat = TelemetryExtendedHeartbeat()
    # ASM scenarios
    appsec_missing_rules = AppsecMissingRules()
    appsec_corrupted_rules = AppsecCorruptedRules()
    appsec_custom_rules = AppsecCustomRules()
    appsec_blocking = AppsecBlocking()
    # This GraphQL scenario can be used for any GraphQL testing, not just AppSec
    graphql_appsec = GraphqlAppsec()
    # This GraphQL scenario can be used for any GraphQL testing, not just AppSec
    graphql_error_tracking = GraphqlErrorTracking()
    appsec_rules_monitoring_with_errors = AppsecRulesMonitoringWithErrors()
    everything_disabled = EverythingDisabled()
    appsec_low_waf_timeout = AppsecLowWafTimeout()
    appsec_custom_obfuscation = AppsecCustomObfuscation()
    appsec_rate_limiter = AppsecRateLimiter()
    appsec_waf_telemetry = AppsecWafTelemetry()
    appsec_blocking_full_denylist = AppsecBlockingFullDenylist()
    appsec_runtime_activation = AppsecRuntimeActivation()
    appsec_api_security = AppsecApiSecurity()
    appsec_api_security_rc = AppsecApiSecurityRc()
    appsec_api_security_no_response_body = AppsecApiSecurityNoResponseBody()
    appsec_api_security_with_sampling = AppsecApiSecurityWithSampling()
    appsec_auto_events_extended = AppsecAutoEventsExtended()
    appsec_auto_events_rc = AppsecAutoEventsRc()
    runtime_sca_reachability = RuntimeScaReachability()
    appsec_standalone = AppsecStandalone()
    appsec_apm_standalone = AppsecApmStandalone()
    appsec_standalone_apm_standalone = AppsecStandaloneApmStandalone()
    # Combined scenario for API Security in standalone mode
    appsec_standalone_api_security = AppsecStandaloneApiSecurity()
    iast_standalone = IastStandalone()
    sca_standalone = ScaStandalone()
    iast_deduplication = IastDeduplication()
    appsec_meta_struct_disabled = AppsecMetaStructDisabled()
    remote_config_mocked_backend_asm_features = RemoteConfigMockedBackendAsmFeatures()
    remote_config_mocked_backend_live_debugging = RemoteConfigMockedBackendLiveDebugging()
    remote_config_mocked_backend_asm_dd = RemoteConfigMockedBackendAsmDd()
    feature_flagging_and_experimentation = FeatureFlaggingAndExperimentation()
    feature_flagging_and_experimentation_agentless = FeatureFlaggingAndExperimentationAgentless()
    feature_flagging_and_experimentation_agentless_direct = FeatureFlaggingAndExperimentationAgentlessDirect()
    feature_flagging_and_experimentation_agentless_serverless = FeatureFlaggingAndExperimentationAgentlessServerless()
    feature_flagging_evaluation_telemetry_opt_out = FeatureFlaggingEvaluationTelemetryOptOut()
    feature_flagging_evaluation_telemetry_opt_out_disabled = FeatureFlaggingEvaluationTelemetryOptOutDisabled()
    feature_flagging_evp_stress = FeatureFlaggingEvpStress()
    remote_config_mocked_backend_asm_features_nocache = RemoteConfigMockedBackendAsmFeaturesNocache()
    # APM tracing end-to-end scenarios
    apm_tracing_e2e_otel = ApmTracingE2eOtel()
    apm_tracing_e2e_single_span = ApmTracingE2eSingleSpan()
    apm_tracing_otlp = ApmTracingOtlp()
    apm_tracing_efficient_payload = ApmTracingEfficientPayload()
    otel_tracing_e2e = OtelTracingE2e()
    otel_metric_e2e = OtelMetricE2e()
    otel_log_e2e = OtelLogE2e()
    library_conf_custom_header_tags = LibraryConfCustomHeaderTags()
    library_conf_custom_header_tags_invalid = LibraryConfCustomHeaderTagsInvalid()
    tracing_config_empty = TracingConfigEmpty()
    tracing_config_nondefault = TracingConfigNondefault()
    tracing_config_nondefault_2 = TracingConfigNondefault2()
    tracing_config_nondefault_3 = TracingConfigNondefault3()
    tracing_config_nondefault_4 = TracingConfigNondefault4()
    parametric = ParametricScenario()
    debugger_probes_snapshot = DebuggerProbesSnapshot()
    debugger_capture_timeout = DebuggerCaptureTimeout()
    debugger_evaluation_timeout = DebuggerEvaluationTimeout()
    debugger_probes_snapshot_with_scm = DebuggerProbesSnapshotWithScm()
    debugger_pii_redaction = DebuggerPiiRedaction()
    debugger_expression_language = DebuggerExpressionLanguage()
    debugger_exception_replay = DebuggerExceptionReplay()
    debugger_symdb = DebuggerSymdb()
    thread_context_sharing = ThreadContextSharingScenario()
    debugger_inproduct_enablement = DebuggerInproductEnablement()
    debugger_telemetry = DebuggerTelemetry()
    fuzzer = Fuzzer()
    # Single Step Instrumentation scenarios (HOST and CONTAINER)
    simple_installer_auto_injection = SimpleInstallerAutoInjection()
    multi_installer_auto_injection = MultiInstallerAutoInjection()
    installer_auto_injection = InstallerAutoInjection()
    installer_not_supported_auto_injection = InstallerNotSupportedAutoInjection()
    chaos_installer_auto_injection = ChaosInstallerAutoInjection()
    simple_auto_injection_profiling = SimpleAutoInjectionProfiling()
    host_auto_injection_install_script_profiling = HostAutoInjectionInstallScriptProfiling()
    container_auto_injection_install_script_profiling = ContainerAutoInjectionInstallScriptProfiling()
    simple_auto_injection_appsec = SimpleAutoInjectionAppsec()
    host_auto_injection_install_script_appsec = HostAutoInjectionInstallScriptAppsec()
    container_auto_injection_install_script_appsec = ContainerAutoInjectionInstallScriptAppsec()
    host_auto_injection_install_script = HostAutoInjectionInstallScript()
    container_auto_injection_install_script = ContainerAutoInjectionInstallScript()
    local_auto_injection_install_script = LocalAutoInjectionInstallScript()
    k8s_lib_injection = K8sLibInjection()
    k8s_lib_injection_operator = K8sLibInjectionOperator()
    k8s_lib_injection_uds = K8sLibInjectionUds()
    k8s_lib_injection_no_ac = K8sLibInjectionNoAc()
    k8s_lib_injection_no_ac_uds = K8sLibInjectionNoAcUds()
    k8s_lib_injection_profiling_disabled = K8sLibInjectionProfilingDisabled()
    k8s_lib_injection_profiling_enabled = K8sLibInjectionProfilingEnabled()
    k8s_lib_injection_profiling_override = K8sLibInjectionProfilingOverride()
    k8s_lib_injection_appsec_disabled = K8sLibInjectionAppsecDisabled()
    k8s_lib_injection_appsec_enabled = K8sLibInjectionAppsecEnabled()
    k8s_lib_injection_spark_djm = K8sLibInjectionSparkDjm()
    # K8s Injector dev scenarios
    k8s_injector_dev_single_service = K8sInjectorDevSingleService()
    docker_ssi = DockerSsi()
    docker_ssi_servicenaming = DockerSsiServicenaming()
    docker_ssi_appsec = DockerSsiAppsec()
    docker_ssi_crashtracking = DockerSsiCrashtracking()
    appsec_rasp = AppsecRasp()
    appsec_rasp_without_downstream_body_analysis_using_sample_rate = (
        AppsecRaspWithoutDownstreamBodyAnalysisUsingSampleRate()
    )
    appsec_rasp_without_downstream_body_analysis_using_max = AppsecRaspWithoutDownstreamBodyAnalysisUsingMax()
    appsec_standalone_rasp = AppsecStandaloneRasp()
    appsec_rasp_non_blocking = AppsecRaspNonBlocking()
    appsec_ato_sdk = AppsecAtoSdk()
    agent_supporting_span_events = AgentSupportingSpanEvents()
    agent_not_supporting_span_events = AgentNotSupportingSpanEvents()
    ipv6 = IPV6Scenario()
    runtime_metrics_enabled = RuntimeMetricsEnabled()
    otlp_runtime_metrics = OtlpRuntimeMetrics()
    # Appsec Lambda Scenarios
    appsec_lambda_default = AppsecLambdaDefault()
    appsec_lambda_blocking = AppsecLambdaBlocking()
    appsec_lambda_api_security = AppsecLambdaApiSecurity()
    appsec_lambda_rasp = AppsecLambdaRasp()
    appsec_lambda_inferred_spans = AppsecLambdaInferredSpans()
    otel_collector = OtelCollectorScenario()
    integration_frameworks = IntegrationFrameworksScenario()
    ai_guard = AiGuard()
    ai_guard_standalone = AiGuardStandalone()
    ai_guard_telemetry = AiGuardTelemetry()
    ai_guard_redaction_telemetry = AiGuardRedactionTelemetry()
    ai_guard_redaction_disabled = AiGuardRedactionDisabled()


scenarios = _Scenarios()


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

    print(json.dumps(data, indent=2))  # noqa: T201


if __name__ == "__main__":
    _main()

# right now, no rules are defined for groups
# it means that we cannot b y design make some group part of another group
# waiting for a clean solution to this problem, let's just test it

from utils import scenarios, scenario_groups
from utils._context._scenarios import get_all_scenarios


@scenarios.test_the_test
def test_appsec():
    for scenario in get_all_scenarios():
        if scenario_groups.appsec_rasp in scenario.scenario_groups:
            assert scenario_groups.appsec_rasp in scenario.scenario_groups


@scenarios.test_the_test
def test_tracer_release():
    # make an exclusion list

    dormant_agentless_scenarios = [
        scenarios.feature_flagging_and_experimentation_agentless,
        scenarios.feature_flagging_and_experimentation_agentless_sidecar,
        scenarios.feature_flagging_and_experimentation_agentless_direct_fallback,
    ]
    for dormant_agentless_scenario in dormant_agentless_scenarios:
        assert dormant_agentless_scenario.include_agent is False
        assert scenario_groups.ffe in dormant_agentless_scenario.scenario_groups
        assert scenario_groups.all not in dormant_agentless_scenario.scenario_groups
        assert scenario_groups.end_to_end not in dormant_agentless_scenario.scenario_groups
        assert scenario_groups.tracer_release not in dormant_agentless_scenario.scenario_groups

    assert scenarios.feature_flagging_and_experimentation_agentless.use_proxy is False
    assert scenarios.feature_flagging_and_experimentation_agentless._flush_weblog_on_stop is False  # noqa: SLF001
    assert scenarios.feature_flagging_and_experimentation_agentless_sidecar.use_proxy is True
    assert scenarios.feature_flagging_and_experimentation_agentless_direct_fallback.use_proxy is True

    not_in_tracer_release_group = [
        # list of scenario that will never be part of tracer release
        scenarios.fuzzer,
        *dormant_agentless_scenarios,
        scenarios.mock_the_test,
        scenarios.mock_the_test_2,
        scenarios.test_the_test,
        scenarios.todo,
        # targetting OTEL
        scenarios.otel_integrations,
        scenarios.otel_log_e2e,
        scenarios.otel_metric_e2e,
        scenarios.otel_tracing_e2e,
        scenarios.otel_collector,
        # to be added once stability is proven
        scenarios.chaos_installer_auto_injection,
        scenarios.container_auto_injection_install_script_appsec,
        scenarios.container_auto_injection_install_script_profiling,
        scenarios.container_auto_injection_install_script,
        scenarios.docker_ssi,
        scenarios.docker_ssi_appsec,
        scenarios.docker_ssi_crashtracking,
        scenarios.docker_ssi_servicenaming,
        scenarios.host_auto_injection_install_script_appsec,
        scenarios.host_auto_injection_install_script_profiling,
        scenarios.host_auto_injection_install_script,
        scenarios.installer_auto_injection,
        scenarios.installer_not_supported_auto_injection,
        scenarios.k8s_lib_injection_no_ac_uds,
        scenarios.k8s_lib_injection_no_ac,
        scenarios.k8s_lib_injection_operator,
        scenarios.k8s_lib_injection_appsec_disabled,
        scenarios.k8s_lib_injection_appsec_enabled,
        scenarios.k8s_lib_injection_profiling_disabled,
        scenarios.k8s_lib_injection_profiling_enabled,
        scenarios.k8s_lib_injection_profiling_override,
        scenarios.k8s_lib_injection_spark_djm,
        scenarios.k8s_lib_injection_uds,
        scenarios.k8s_lib_injection,
        scenarios.k8s_injector_dev_single_service,
        scenarios.local_auto_injection_install_script,
        scenarios.simple_auto_injection_appsec,
        scenarios.simple_auto_injection_profiling,
        scenarios.simple_installer_auto_injection,
        scenarios.multi_installer_auto_injection,
        scenarios.otel_collector_e2e,
    ]

    for scenario in get_all_scenarios():
        if scenario in not_in_tracer_release_group:
            assert scenario_groups.tracer_release not in scenario.scenario_groups, (
                f"Scenario {scenario} should not be part of {scenario_groups.tracer_release}"
            )

        if scenario_groups.tracer_release not in scenario.scenario_groups:
            assert scenario in not_in_tracer_release_group, (
                f"Scenario {scenario.name} is not part of {scenario_groups.tracer_release.name} group"
            )

            if scenario in not_in_tracer_release_group:
                assert scenario_groups.tracer_release not in scenario.scenario_groups

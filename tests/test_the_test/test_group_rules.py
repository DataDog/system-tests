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

    not_in_tracer_release_group = [
        # list of scenario that will never be part of tracer release
        scenarios.everything_disabled,
        scenarios.fuzzer,
        scenarios.mock_the_test,
        scenarios.test_the_test,
        scenarios.todo,
        # Is it targeting tracers ?
        scenarios.otel_integrations,
        scenarios.otel_log_e2e,
        scenarios.otel_metric_e2e,
        scenarios.otel_tracing_e2e,
        # to be added once stability is proven
        scenarios.chaos_installer_auto_injection,
        scenarios.container_auto_injection_install_script_appsec,
        scenarios.container_auto_injection_install_script_profiling,
        scenarios.container_auto_injection_install_script,
        scenarios.docker_ssi,
        scenarios.docker_ssi_crashtracking,
        scenarios.docker_ssi_servicenaming,
        scenarios.external_processing_blocking,  # need to declare a white list of library in get-workflow-parameters
        scenarios.external_processing,  # need to declare a white list of library in get-workflow-parameters
        scenarios.host_auto_injection_install_script_appsec,
        scenarios.host_auto_injection_install_script_profiling,
        scenarios.host_auto_injection_install_script,
        scenarios.installer_auto_injection,
        scenarios.installer_not_supported_auto_injection,
        scenarios.k8s_lib_injection_no_ac_uds,
        scenarios.k8s_lib_injection_no_ac,
        scenarios.k8s_lib_injection_operator,
        scenarios.k8s_lib_injection_profiling_disabled,
        scenarios.k8s_lib_injection_profiling_enabled,
        scenarios.k8s_lib_injection_profiling_override,
        scenarios.k8s_lib_injection_spark_djm,
        scenarios.k8s_lib_injection_uds,
        scenarios.k8s_lib_injection,
        scenarios.lib_injection_validation_unsupported_lang,
        scenarios.lib_injection_validation,
        scenarios.local_auto_injection_install_script,
        scenarios.simple_auto_injection_appsec,
        scenarios.simple_auto_injection_profiling,
        scenarios.simple_installer_auto_injection,
        scenarios.multi_installer_auto_injection,
        scenarios.demo_aws,
        scenarios.appsec_lambda_blocking,
    ]

    for scenario in get_all_scenarios():
        if scenario_groups.tracer_release not in scenario.scenario_groups:
            assert (
                scenario in not_in_tracer_release_group
            ), f"Scenario {scenario} is not part of {scenario_groups.tracer_release}"

            if scenario in not_in_tracer_release_group:
                assert scenario_groups.tracer_release not in scenario.scenario_groups

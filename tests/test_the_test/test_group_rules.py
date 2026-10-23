# right now, no rules are defined for groups
# it means that we cannot b y design make some group part of another group
# waiting for a clean solution to this problem, let's just test it

import json
from pathlib import Path

import yaml

from utils import pytest, scenarios, scenario_groups
from utils._context._scenarios import get_all_scenarios


@scenarios.test_the_test
def test_appsec():
    for scenario in get_all_scenarios():
        if scenario_groups.appsec_rasp in scenario.scenario_groups:
            assert scenario_groups.appsec_rasp in scenario.scenario_groups


@scenarios.test_the_test
def test_tracer_release():
    # make an exclusion list

    provisional_opt_out_scenarios = [
        scenarios.feature_flagging_evaluation_telemetry_opt_out,
        scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled,
        scenarios.feature_flagging_experimentation_opt_out_disabled,
        scenarios.feature_flagging_experimentation_opt_out_immediate,
        scenarios.feature_flagging_experimentation_opt_out_future,
    ]
    for opt_out_scenario in provisional_opt_out_scenarios:
        assert opt_out_scenario.github_workflow == "endtoend"
        assert scenario_groups.ffe in opt_out_scenario.scenario_groups
        assert opt_out_scenario in scenario_groups.ffe.scenarios
        for group in (scenario_groups.all, scenario_groups.end_to_end, scenario_groups.tracer_release):
            assert group not in opt_out_scenario.scenario_groups
            assert opt_out_scenario not in group.scenarios

    dormant_agentless_scenario = scenarios.feature_flagging_and_experimentation_agentless
    assert dormant_agentless_scenario.include_agent is False
    assert dormant_agentless_scenario.use_proxy is False
    assert scenario_groups.ffe in dormant_agentless_scenario.scenario_groups
    assert scenario_groups.all not in dormant_agentless_scenario.scenario_groups
    assert scenario_groups.end_to_end not in dormant_agentless_scenario.scenario_groups
    assert scenario_groups.tracer_release not in dormant_agentless_scenario.scenario_groups

    agentless_exposure_scenarios = [
        scenarios.feature_flagging_and_experimentation_agentless_direct,
        scenarios.feature_flagging_and_experimentation_agentless_serverless,
    ]
    for exposure_scenario in agentless_exposure_scenarios:
        assert exposure_scenario.include_agent is False
        assert exposure_scenario.use_proxy is True
        assert scenario_groups.ffe in exposure_scenario.scenario_groups
        assert scenario_groups.all not in exposure_scenario.scenario_groups
        assert scenario_groups.end_to_end not in exposure_scenario.scenario_groups
        assert scenario_groups.tracer_release not in exposure_scenario.scenario_groups

    not_in_tracer_release_group = [
        # list of scenario that will never be part of tracer release
        scenarios.fuzzer,
        dormant_agentless_scenario,
        *agentless_exposure_scenarios,
        scenarios.mock_the_test,
        scenarios.mock_the_test_2,
        scenarios.test_the_test,
        *provisional_opt_out_scenarios,
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


@scenarios.test_the_test
@pytest.mark.parametrize(
    "scenario_name",
    [
        "FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT",
        "FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT_DISABLED",
        "FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_DISABLED",
        "FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_IMMEDIATE",
        "FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_FUTURE",
    ],
)
def test_opt_out_workflow_selection(scenario_name: str) -> None:
    workflow = yaml.safe_load(Path(".github/workflows/run-end-to-end.yml").read_text())
    matching_steps = [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if step.get("run") == f"./run.sh {scenario_name}"
    ]
    assert len(matching_steps) == 1, f"Expected one workflow step for {scenario_name}"
    # Match the quoted JSON name, not a prefix shared with another scenario.
    expected_guard = (
        f"steps.build.outcome == 'success' && !cancelled() && contains(inputs.scenarios, '{json.dumps(scenario_name)}')"
    )
    assert matching_steps[0]["if"] == expected_guard

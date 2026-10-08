from functools import lru_cache
from pathlib import Path

from utils import scenarios
from utils.const import COMPONENT_GROUPS
from utils._context.constants import WeblogBuildMode
from utils._context.weblog_metadata import WeblogMetaData
from utils._context._scenarios import get_all_scenarios, Scenario
from utils.scripts.ci_orchestrators.workflow_data import (
    Job,
    _get_duration_metrics,
    _get_endtoend_weblogs,
    _get_scheduling_metrics,
    _split_jobs_for_parallel_execution,
    _split_scenarios_for_parallel_execution,
    get_endtoend_definitions,
)


@lru_cache
def get_weblogs(library: str) -> dict[str, WeblogMetaData]:
    return {w.name: w for w in WeblogMetaData.load(library)}


def get_weblog(library: str, weblog: str) -> WeblogMetaData:
    return get_weblogs(library)[weblog]


@scenarios.test_the_test
def test_get_endtoend_definitions():
    scenario_map = {
        "endtoend": [
            scenarios.default,
            scenarios.graphql_appsec,
        ],
    }

    defs = get_endtoend_definitions("ruby", scenario_map, [], "dev", 200000, 256, "123", "")
    weblog_count = len(defs["endtoend_defs"]["parallel_weblogs"])

    # if there is an issue, ruby weblog count will be 0 or 1 or 2 ...
    assert weblog_count > 5

    # default scenario is executed on rails, sinatra and rack weblogs
    # graphql_appsec is executed on  graphql23 weblog
    # so the job should be equals to weblog count
    assert len(defs["endtoend_defs"]["parallel_jobs"]) == weblog_count


@scenarios.test_the_test
def test_parallel_scheduling_metrics() -> None:
    weblog = WeblogMetaData(
        name="test-weblog",
        library="ruby",
        build_mode=WeblogBuildMode.prebuild,
    )
    source_job = Job(
        library="ruby",
        weblog=weblog,
        weblog_instance=1,
        scenarios_times={"SCENARIO_A": 40.0, "SCENARIO_B": 30.0},
        build_time=10.0,
    )

    emitted_jobs, jobs_before_limit = _split_jobs_for_parallel_execution([source_job], 60.0, 1)
    metrics = _get_scheduling_metrics([source_job], jobs_before_limit, emitted_jobs, 60.0, 1)

    assert len(emitted_jobs) == 1
    assert set(emitted_jobs[0].scenarios) == {"SCENARIO_A", "SCENARIO_B"}
    assert metrics["scenario_assignments"] == 2
    assert metrics["jobs_before_limit"] == 2
    assert metrics["jobs_after_limit"] == 1
    assert metrics["limit_applied"] is True
    assert metrics["jobs_over_target"] == 1
    assert metrics["weblogs_with_impossible_budget"] == 0
    assert metrics["scenarios_exceeding_run_budget"] == 0
    assert metrics["predicted_run_time_seconds"]["maximum"] == 70.0
    assert metrics["predicted_critical_path_seconds"]["maximum"] == 80.0
    assert metrics["weblogs"] == [
        {
            "weblog": "test-weblog",
            "scenario_assignments": 2,
            "build_time": 10.0,
            "available_run_time": 50.0,
            "budget_status": "within_target",
            "build_exceeds_target": False,
            "scenarios_exceeding_run_budget": 0,
            "jobs_before_limit": 2,
            "jobs_after_limit": 1,
            "jobs_over_target": 1,
            "predicted_run_time_seconds": {
                "minimum": 70.0,
                "median": 70.0,
                "p95": 70.0,
                "maximum": 70.0,
            },
            "predicted_critical_path_seconds": {
                "minimum": 80.0,
                "median": 80.0,
                "p95": 80.0,
                "maximum": 80.0,
            },
        }
    ]


@scenarios.test_the_test
def test_duration_metrics_use_nearest_rank_percentiles() -> None:
    assert _get_duration_metrics([5.0, 1.0, 4.0, 2.0, 3.0]) == {
        "minimum": 1.0,
        "median": 3.0,
        "p95": 5.0,
        "maximum": 5.0,
    }
    assert _get_duration_metrics([]) == {
        "minimum": 0.0,
        "median": 0.0,
        "p95": 0.0,
        "maximum": 0.0,
    }


@scenarios.test_the_test
def test_build_time_over_target_uses_explicit_zero_run_budget() -> None:
    weblog = WeblogMetaData(
        name="test-weblog",
        library="ruby",
        build_mode=WeblogBuildMode.prebuild,
    )
    source_job = Job(
        library="ruby",
        weblog=weblog,
        weblog_instance=1,
        scenarios_times={"SCENARIO_A": 20.0, "SCENARIO_B": 10.0},
        build_time=75.0,
    )

    emitted_jobs, jobs_before_limit = _split_jobs_for_parallel_execution([source_job], 60.0, 2)
    metrics = _get_scheduling_metrics([source_job], jobs_before_limit, emitted_jobs, 60.0, 2)

    assert source_job.available_run_time(60.0) == 0.0
    assert [job.scenarios for job in emitted_jobs] == [("SCENARIO_A",), ("SCENARIO_B",)]
    assert metrics["weblogs_with_impossible_budget"] == 1
    assert metrics["scenarios_exceeding_run_budget"] == 2
    assert metrics["weblogs"][0]["available_run_time"] == 0.0
    assert metrics["weblogs"][0]["budget_status"] == "build_exceeds_target"


@scenarios.test_the_test
def test_scenario_over_run_budget_is_isolated_without_losing_scenarios() -> None:
    split = _split_scenarios_for_parallel_execution(
        {
            "TOO_LONG": 70.0,
            "SCENARIO_A": 20.0,
            "SCENARIO_B": 20.0,
        },
        50.0,
    )

    assert split == [["TOO_LONG"], ["SCENARIO_A", "SCENARIO_B"]]
    assert sorted(scenario for scenarios in split for scenario in scenarios) == [
        "SCENARIO_A",
        "SCENARIO_B",
        "TOO_LONG",
    ]


@scenarios.test_the_test
def test_ipv6_is_not_supported_for_uds_weblogs():
    def _is_supported(weblog: WeblogMetaData, scenario: Scenario) -> bool:
        return weblog.support_scenario(scenario.name, scenario.weblog_categories)

    assert not _is_supported(get_weblog("dotnet", "uds"), scenarios.ipv6)
    assert not _is_supported(get_weblog("python", "uds-flask"), scenarios.ipv6)
    assert _is_supported(get_weblog("python", "flask-poc"), scenarios.ipv6)


@scenarios.test_the_test
def test_fiber_v2_orchestrion_weblog() -> None:
    weblog = get_weblog("golang", "fiber-v2-orchestrion")
    for scenario in (scenarios.default, scenarios.sampling, scenarios.ipv6):
        assert weblog.support_scenario(scenario.name, scenario.weblog_categories)
    assert not weblog.support_scenario(scenarios.graphql_appsec.name, scenarios.graphql_appsec.weblog_categories)

    definitions = get_endtoend_definitions(
        "golang", {"endtoend": [scenarios.default]}, [weblog.name], "dev", 200000, 256, "123", ""
    )
    jobs = definitions["endtoend_defs"]["parallel_jobs"]
    assert len(jobs) == 1
    assert jobs[0]["weblog"] == weblog.name
    assert jobs[0]["weblog_build_required"]
    assert jobs[0]["scenarios"] == ["DEFAULT"]


@scenarios.test_the_test
def test_get_endtoend_definitions_empty_scenario_map():
    # Regression: previously raised KeyError when "endtoend" or "parametric" keys were absent
    defs = get_endtoend_definitions("ruby", {}, [], "dev", 200000, 256, "123", "")
    assert isinstance(defs["endtoend_defs"]["parallel_jobs"], list)


@scenarios.test_the_test
def test_get_endtoend_definitions_missing_endtoend_key():
    defs = get_endtoend_definitions("ruby", {"other": ["X"]}, [], "dev", 200000, 256, "123", "")
    assert defs["endtoend_defs"]["parallel_jobs"] == []


@scenarios.test_the_test
def test_nodejs_weblogs_dont_require_prebuild():
    scenario_map = {"endtoend": [scenarios.default]}
    defs = get_endtoend_definitions("nodejs", scenario_map, [], "dev", 200000, 256, "123", "")
    # Node.js weblogs use build_mode="local": no dedicated build_end_to_end job
    # (parallel_weblogs lists only "prebuild" weblogs, so it is empty), but the
    # run_end_to_end jobs still build the weblog in-line (weblog_build_required=True).
    parallel_jobs = defs["endtoend_defs"]["parallel_jobs"]
    assert defs["endtoend_defs"]["parallel_weblogs"] == []
    assert len(parallel_jobs) > 0
    assert all(job["weblog_build_required"] for job in parallel_jobs)


@scenarios.test_the_test
def test_weblog_build_mode_is_resolved_from_metadata():
    # build_mode is the single source of build requirement for every weblog, declared
    # in each library's build.yml:
    #   - weblog not listed in build.yml → "prebuild" (dedicated build job + local build)
    #   - listed with a build_mode       → as declared
    build_modes = {w.name: w.build_mode for w in _get_endtoend_weblogs("python", [], "123", "dev", "shared")}

    # Dockerfile weblog absent from build.yml defaults to prebuild
    assert build_modes["flask-poc"] == "prebuild"
    # Node.js weblogs opt into local-only builds via build.yml
    nodejs_modes = {w.name: w.build_mode for w in _get_endtoend_weblogs("nodejs", [], "123", "dev", "shared")}
    assert nodejs_modes["express4"] == "local"
    # integration-framework weblogs fan out per version and need no build
    assert build_modes["openai-py@2.0.0"] == "none"


@scenarios.test_the_test
def test_otel_collector():
    scenario_map = {"endtoend": [scenarios.otel_collector]}
    defs = get_endtoend_definitions("otel_collector", scenario_map, [], "prod", 200000, 256, "123", "")

    assert defs["endtoend_defs"]["parallel_jobs"] == [
        {
            "binaries_artifact": "",
            "expected_build_time": 0.0,
            "expected_job_time": 74.34217318962216,
            "expected_run_time": 74.34217318962216,
            "library": "otel_collector",
            "runs_on": "ubuntu-latest",
            "scenarios": ["OTEL_COLLECTOR"],
            "weblog": "otel_collector",
            "weblog_build_required": False,
            "weblog_instance": 1,
        }
    ]


@scenarios.test_the_test
def test_weblog_metadata_scenario_names_are_valid():
    valid_names = {scenario.name for scenario in get_all_scenarios()}

    for library in sorted(COMPONENT_GROUPS.all):
        for weblog in WeblogMetaData.load(library):
            for scenario_name in weblog.supported_scenarios + weblog.excluded_scenarios:
                assert scenario_name in valid_names, (
                    f"{library}/{weblog.name}: '{scenario_name}' is not a known scenario name "
                    f"(check utils/build/docker/{library}/weblog_metadata.yml)"
                )


@scenarios.test_the_test
def test_all_weblog_has_metadata():
    for library in sorted(COMPONENT_GROUPS.all):
        folder = Path(f"utils/build/docker/{library}")
        if folder.exists():  # some lib does not have any weblog
            names = [
                f.name.replace(".Dockerfile", "")
                for f in folder.iterdir()
                if f.suffix == ".Dockerfile" and ".base." not in f.name and f.is_file()
            ]

            known_weblog_names = {w.name.split("@")[0] for w in WeblogMetaData.load(library)}

            for name in names:
                assert name in known_weblog_names, (
                    f"Please add {name} in utils/build/docker/{library}/weblog_metadata.yml"
                )

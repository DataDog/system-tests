from utils import scenarios

from utils.scripts.ci_orchestrators.workflow_data import (
    _get_endtoend_weblogs,
    _is_supported,
    get_endtoend_definitions,
)


@scenarios.test_the_test
def test_get_endtoend_definitions():
    scenario_map = {
        "endtoend": [
            "DEFAULT",
            "GRAPHQL_APPSEC",
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
def test_ipv6_is_not_supported_for_uds_weblogs():
    assert not _is_supported("dotnet", "uds", "IPV6", "dev")
    assert not _is_supported("python", "uds-flask", "IPV6", "dev")
    assert _is_supported("python", "flask-poc", "IPV6", "dev")


@scenarios.test_the_test
def test_get_endtoend_definitions_empty_scenario_map():
    # Regression: previously raised KeyError when "endtoend" or "parametric" keys were absent
    defs = get_endtoend_definitions("ruby", {}, [], "dev", 200000, 256, "123", "")
    assert isinstance(defs["endtoend_defs"]["parallel_jobs"], list)


@scenarios.test_the_test
def test_get_endtoend_definitions_missing_endtoend_key():
    defs = get_endtoend_definitions("ruby", {"other": ["X"]}, [], "dev", 200000, 256, "123", "")
    assert defs["endtoend_defs"]["parallel_jobs"] == []
def test_nodejs_weblogs_dont_require_prebuild():
    scenario_map = {"endtoend": ["DEFAULT"]}
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
def test_nodejs_build_base_image():
    scenario_map = {"endtoend": ["DEFAULT", "INTEGRATION_FRAMEWORKS"]}
    defs = get_endtoend_definitions("nodejs", scenario_map, [], "dev", 200000, 256, "123", "", build_base_images=True)

    assert defs["endtoend_defs"]["parallel_weblogs"] == []

    jobs = {job["weblog"]: job for job in defs["endtoend_defs"]["parallel_jobs"]}

    # express4 is build_mode=local and has a base Dockerfile → should build base image
    assert jobs["express4"]["build_weblog_base_image"] is True

    # openai-js is build_mode=none and has no base Dockerfile → should not build base image
    assert jobs["openai-js@6.0.0"]["build_weblog_base_image"] is False


@scenarios.test_the_test
def test_python_build_base_image():
    scenario_map = {"endtoend": ["DEFAULT", "INTEGRATION_FRAMEWORKS"]}
    defs = get_endtoend_definitions("python", scenario_map, [], "dev", 200000, 256, "123", "", build_base_images=True)

    # all python weblog has build_mode=prebuild. build_weblog_base_image
    # only applies to build_mode=local weblogs → should not build base image inline
    for job in defs["endtoend_defs"]["parallel_jobs"]:
        assert job["build_weblog_base_image"] is False, job

    # all python weblog with build_mode=prebuild should rebuild base images in the build job
    for job in defs["endtoend_defs"]["parallel_weblogs"]:
        assert job["build_base_images"] is True, job


@scenarios.test_the_test
def test_otel_collector():
    scenario_map = {"endtoend": ["OTEL_COLLECTOR"]}
    defs = get_endtoend_definitions("otel_collector", scenario_map, [], "prod", 200000, 256, "123", "")

    assert defs["endtoend_defs"]["parallel_jobs"] == [
        {
            "binaries_artifact": "",
            "build_weblog_base_image": False,
            "expected_job_time": 74.34217318962216,
            "library": "otel_collector",
            "runs_on": "ubuntu-latest",
            "scenarios": ["OTEL_COLLECTOR"],
            "weblog": "otel_collector",
            "weblog_build_required": False,
            "weblog_instance": 1,
        }
    ]

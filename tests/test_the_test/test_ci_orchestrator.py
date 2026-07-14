from functools import lru_cache
from pathlib import Path

from utils import scenarios, logger
from utils.const import COMPONENT_GROUPS
from utils._context.weblog_metadata import WeblogMetaData
from utils._context._scenarios import get_all_scenarios, Scenario
from utils.scripts.ci_orchestrators.workflow_data import (
    _get_endtoend_weblogs,
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
def test_ipv6_is_not_supported_for_uds_weblogs():
    def _is_supported(weblog: WeblogMetaData, scenario: Scenario) -> bool:
        return weblog.support_scenario(scenario.name, scenario.weblog_categories)

    assert not _is_supported(get_weblog("dotnet", "uds"), scenarios.ipv6)
    assert not _is_supported(get_weblog("python", "uds-flask"), scenarios.ipv6)
    assert _is_supported(get_weblog("python", "flask-poc"), scenarios.ipv6)


@scenarios.test_the_test
def test_debugger_capture_timeout_runs_only_on_weblogs_with_the_fixture():
    expected_supported = {
        ("dotnet", "poc"),
        ("dotnet", "uds"),
        ("java", "spring-boot"),
        ("java", "spring-boot-jetty"),
        ("java", "spring-boot-openliberty"),
        ("java", "spring-boot-payara"),
        ("java", "spring-boot-undertow"),
        ("java", "spring-boot-wildfly"),
        ("java", "uds-spring-boot"),
        ("nodejs", "express4"),
        ("nodejs", "express4-typescript"),
        ("nodejs", "express5"),
        ("nodejs", "fastify"),
        ("nodejs", "uds-express4"),
    }
    libraries = ("dotnet", "golang", "java", "nodejs", "php", "python", "ruby")
    available_weblogs = {(library, weblog_name) for library in libraries for weblog_name in get_weblogs(library)}

    assert expected_supported <= available_weblogs
    for library, weblog_name in available_weblogs:
        weblog = get_weblog(library, weblog_name)
        supported = weblog.support_scenario(
            scenarios.debugger_capture_timeout.name,
            scenarios.debugger_capture_timeout.weblog_categories,
        )
        assert supported == ((library, weblog_name) in expected_supported)


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
def test_nodejs_build_base_image():
    scenario_map = {"endtoend": [scenarios.default, scenarios.integration_frameworks]}
    defs = get_endtoend_definitions("nodejs", scenario_map, [], "dev", 200000, 256, "123", "", build_base_images=True)

    assert defs["endtoend_defs"]["parallel_weblogs"] == []

    jobs = {job["weblog"]: job for job in defs["endtoend_defs"]["parallel_jobs"]}

    # express4 is build_mode=local and has a base Dockerfile → should build base image
    assert jobs["express4"]["build_weblog_base_image"] is True

    # openai-js is build_mode=none and has no base Dockerfile → should not build base image
    assert jobs["openai-js@6.0.0"]["build_weblog_base_image"] is False


@scenarios.test_the_test
def test_python_build_base_image():
    scenario_map = {"endtoend": [scenarios.default, scenarios.integration_frameworks]}
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
    scenario_map = {"endtoend": [scenarios.otel_collector]}
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


@scenarios.test_the_test
def test_legacy_scenario_matrix():
    has_error = False

    for library in sorted(COMPONENT_GROUPS.all):
        for weblog in sorted(WeblogMetaData.load(library), key=lambda w: w.name):
            for scenario in get_all_scenarios():
                legacy = _is_supported_legacy(weblog, scenario, "")
                new_value = weblog.support_scenario(scenario.name, scenario.weblog_categories)
                if legacy is not new_value:
                    has_error = True
                    logger.error((library, legacy, new_value, weblog.name, scenario.name, scenario.weblog_categories))

    assert not has_error


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


# copy of the old function to test compatibility. To be removed once all good
def _is_supported_legacy(weblog: WeblogMetaData, scenario: Scenario, _ci_environment: str) -> bool:
    # this function will remove some couple scenarios/weblog that are not supported

    def _is_uds_weblog(weblog: str) -> bool:
        return weblog == "uds" or weblog.startswith("uds-")

    if scenario.github_workflow != "endtoend":
        return False

    library = weblog.library
    weblog_name = weblog.name

    # Only Allow Lambda scenarios for the lambda libraries
    is_lambda_library = library in (
        "python_lambda",
        "java_lambda",
        "nodejs_lambda",
        "ruby_lambda",
    )
    is_lambda_scenario = scenario.name in (
        "APPSEC_LAMBDA_DEFAULT",
        "APPSEC_LAMBDA_BLOCKING",
        "APPSEC_LAMBDA_API_SECURITY",
        "APPSEC_LAMBDA_RASP",
        "APPSEC_LAMBDA_INFERRED_SPANS",
    )
    if is_lambda_library != is_lambda_scenario:
        return False

    # open-telemetry-automatic
    if scenario.name == "OTEL_INTEGRATIONS":
        possible_values: tuple = (
            ("java_otel", "spring-boot-otel"),
            ("nodejs_otel", "express4-otel"),
            ("python_otel", "flask-poc-otel"),
        )
        if (library, weblog_name) not in possible_values:
            return False

    # open-telemetry-manual
    if scenario.name in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
        if (library, weblog_name) != ("java_otel", "spring-boot-native"):
            return False

    if scenario.name in ("GRAPHQL_APPSEC", "GRAPHQL_ERROR_TRACKING"):
        possible_values: tuple = (
            ("golang", "gqlgen"),
            ("golang", "graph-gophers"),
            ("golang", "graphql-go"),
            ("ruby", "graphql23"),
            ("nodejs", "express4"),
            ("nodejs", "uds-express4"),
            ("nodejs", "express4-typescript"),
            ("nodejs", "express5"),
        )
        if (library, weblog_name) not in possible_values:
            return False

    if scenario.name in ("PERFORMANCES",):
        return False

    if scenario.name == "IPV6":
        if library == "ruby" or _is_uds_weblog(weblog_name):
            return False

    if scenario.name in ("CROSSED_TRACING_LIBRARIES",):
        if weblog_name in ("python3.12", "django-py3.13", "spring-boot-payara"):
            # python 3.13 issue : APMAPI-1096
            return False

    if scenario.name in ("APPSEC_MISSING_RULES", "APPSEC_CORRUPTED_RULES") and library in ("cpp_nginx", "cpp_httpd"):
        # C++ 1.2.0 freeze when the rules file is missing
        return False

    if weblog_name in ["gqlgen", "graph-gophers", "graphql-go", "graphql23"]:
        if scenario.name not in ("GRAPHQL_APPSEC",):
            return False

    # open-telemetry-manual
    if weblog_name == "spring-boot-native":
        if scenario.name not in ("OTEL_LOG_E2E", "OTEL_METRIC_E2E", "OTEL_TRACING_E2E"):
            return False

    # open-telemetry-automatic
    if weblog_name in ["express4-otel", "flask-poc-otel", "spring-boot-otel"]:
        if scenario.name not in ("OTEL_INTEGRATIONS",):
            return False

    # Go proxies
    if weblog.name in ("envoy", "haproxy"):
        if scenario.name not in ("DEFAULT", "APPSEC_BLOCKING"):
            return False

    # otel collector
    if weblog_name == "otel_collector" or scenario.name in ("OTEL_COLLECTOR", "OTEL_COLLECTOR_E2E"):
        return weblog_name == "otel_collector" and scenario.name in ("OTEL_COLLECTOR", "OTEL_COLLECTOR_E2E")

    if "@" in weblog_name or scenario.name == "INTEGRATION_FRAMEWORKS":
        return "@" in weblog_name and scenario.name == "INTEGRATION_FRAMEWORKS"

    return True

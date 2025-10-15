from __future__ import annotations
from pathlib import Path

from functools import wraps

import pytest
from utils.scripts.compute_libraries_and_scenarios import Inputs, process
from utils import scenarios


all_lib_matrix = 'library_matrix=[{"library": "cpp", "version": "prod"}, {"library": "cpp_httpd", "version": "prod"}, {"library": "cpp_nginx", "version": "prod"}, {"library": "dotnet", "version": "prod"}, {"library": "golang", "version": "prod"}, {"library": "java", "version": "prod"}, {"library": "nodejs", "version": "prod"}, {"library": "otel_collector", "version": "prod"}, {"library": "php", "version": "prod"}, {"library": "python", "version": "prod"}, {"library": "python_lambda", "version": "prod"}, {"library": "ruby", "version": "prod"}, {"library": "rust", "version": "prod"}, {"library": "cpp", "version": "dev"}, {"library": "cpp_httpd", "version": "dev"}, {"library": "cpp_nginx", "version": "dev"}, {"library": "dotnet", "version": "dev"}, {"library": "golang", "version": "dev"}, {"library": "java", "version": "dev"}, {"library": "nodejs", "version": "dev"}, {"library": "php", "version": "dev"}, {"library": "python", "version": "dev"}, {"library": "python_lambda", "version": "dev"}, {"library": "ruby", "version": "dev"}, {"library": "rust", "version": "dev"}]'
all_lib_with_dev = 'libraries_with_dev=["cpp", "cpp_httpd", "cpp_nginx", "dotnet", "golang", "java", "nodejs", "php", "python", "python_lambda", "ruby", "rust"]'


def set_env(key, value):
    """Decorator to set an environment variable before test runs using monkeypatch."""

    def decorator(func):
        @wraps(func)
        def wrapper(self):
            monkeypatch = pytest.MonkeyPatch()
            try:
                monkeypatch.setenv(key, value)
                return func(self)
            finally:
                monkeypatch.undo()

        return wrapper

    return decorator


def build_inputs(
    modified_files=None,
    new_manifests="./tests/test_the_test/manifests/manifests_ref/",
    old_manifests="./tests/test_the_test/manifests/manifests_ref/",
):
    if modified_files is None:
        modified_files = []
    with open("modified_files.txt", "w") as f:
        for file in modified_files:
            f.write(f"{file}\n")
    inputs = Inputs(
        scenario_map_file="tests/test_the_test/scenarios.json",
        new_manifests=new_manifests,
        old_manifests=old_manifests,
    )
    Path.unlink(Path("modified_files.txt"))
    return inputs


@scenarios.test_the_test
class Test_ComputeLibrariesAndScenarios:
    def test_complete_file_path(self):
        inputs = build_inputs([".github/workflows/run-docker-ssi.yml"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="docker_ssi"',
        ]

    def test_multiple_file_changes(self):
        inputs = build_inputs([".github/workflows/run-docker-ssi.yml", "README.md"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="docker_ssi"',
        ]

    def test_unknown_file_path(self):
        inputs = build_inputs(["this_does_not_exist"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="all"',
        ]

    def test_docker_file(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
            'libraries_with_dev=["python"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_REF", "refs/heads/main")
    def test_ref_main(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="all"',
        ]

    def test_manifest(self):
        inputs = build_inputs(
            ["manifests/python.yml"],
            new_manifests="./tests/test_the_test/manifests/manifests_python_edit/",
            old_manifests="./tests/test_the_test/manifests/manifests_ref/",
        )
        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
            'libraries_with_dev=["python"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
        ]

    def test_manifest_agent(self):
        inputs = build_inputs(
            ["manifests/agent.yml"],
            new_manifests="./tests/test_the_test/manifests/manifests_agent_edit/",
            old_manifests="./tests/test_the_test/manifests/manifests_ref/",
        )
        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,OTEL_LOG_E2E"',
            'scenarios_groups=""',
        ]

    def test_multiple_pattern_matches(self):
        inputs = build_inputs(["requirements.txt"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="all"',
        ]

    def test_test_file(self):
        inputs = build_inputs(["tests/auto_inject/test_auto_inject_guardrail.py"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
            'scenarios_groups=""',
        ]

    def test_test_file_utils(self):
        inputs = build_inputs(["tests/auto_inject/utils.py"])

        strings_out = process(inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="CHAOS_INSTALLER_AUTO_INJECTION,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,DEFAULT,DEMO_AWS,HOST_AUTO_INJECTION_INSTALL_SCRIPT,HOST_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,INSTALLER_AUTO_INJECTION,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION,LOCAL_AUTO_INJECTION_INSTALL_SCRIPT,MULTI_INSTALLER_AUTO_INJECTION,SIMPLE_AUTO_INJECTION_APPSEC,SIMPLE_AUTO_INJECTION_PROFILING,SIMPLE_INSTALLER_AUTO_INJECTION"',
            'scenarios_groups=""',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_library_tag(self):
        inputs = build_inputs(["utils/build/docker/java/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        with pytest.raises(ValueError):
            process(inputs)

    @set_env("GITHUB_PR_TITLE", "[java@main] Some title")
    def test_wrong_library_tag_with_branch(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag_with_test_file(self):
        inputs = build_inputs(["tests/auto_inject/test_auto_inject_guardrail.py"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
            'scenarios_groups=""',
        ]

    def test_lambda_proxy(self):
        inputs = build_inputs(["utils/build/docker/lambda_proxy/pyproject.toml"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python_lambda", "version": "prod"}, {"library": "python_lambda", "version": "dev"}]',
            'libraries_with_dev=["python_lambda"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=true",
            'scenarios="DEFAULT"',
            'scenarios_groups="lambda_end_to_end"',
        ]

    def test_doc(self):
        inputs = build_inputs(["binaries/dd-trace-go/_tools/README.md"])

        strings_out = process(inputs)

        assert strings_out == [
            "library_matrix=[]",
            "libraries_with_dev=[]",
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
        ]

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "pull_request")
    @set_env("CI_COMMIT_REF_NAME", "")
    def test_gitlab(self):
        inputs = build_inputs(["README.md"])

        strings_out = process(inputs)

        assert strings_out == [
            'CI_PIPELINE_SOURCE="pull_request"',
            'CI_COMMIT_REF_NAME=""',
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
        ]

    def test_manifest_no_edit(self):
        inputs = build_inputs(
            ["manifests/java.yml"],
            new_manifests="./tests/test_the_test/manifests/manifests_ref/",
            old_manifests="./tests/test_the_test/manifests/manifests_ref/",
        )
        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
        ]

    @set_env("GITHUB_PR_TITLE", "[perl] Some title")
    def test_unknown_library_tag(self):
        inputs = build_inputs(["utils/build/docker/java/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="end_to_end,open_telemetry"',
        ]

    def test_otel_library(self):
        inputs = build_inputs(["utils/build/docker/python_otel/test.Dockerfile"])

        strings_out = process(inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python_otel", "version": "prod"}]',
            "libraries_with_dev=[]",
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenarios_groups="open_telemetry"',
        ]

    def test_missing_modified_files(self):
        with pytest.raises(FileNotFoundError):
            Inputs(
                scenario_map_file="tests/test_the_test/scenarios.json",
                new_manifests="./tests/test_the_test/manifests/manifests_ref/",
                old_manifests="./tests/test_the_test/manifests/manifests_ref/",
            )

    def test_missing_original_manifest(self):
        with pytest.raises(FileNotFoundError):
            Inputs(
                scenario_map_file="tests/test_the_test/scenarios.json",
                new_manifests="./tests/test_the_test/manifests/manifests_ref/",
                old_manifests="./wrong/path",
            )

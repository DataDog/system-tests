from __future__ import annotations

from functools import wraps

import pytest
from manifests.parser.core import load as load_manifests
from utils.scripts.compute_libraries_and_scenarios import Inputs, process
from utils import scenarios


all_lib_matrix = 'library_matrix=[{"library": "cpp", "version": "prod"}, {"library": "cpp_httpd", "version": "prod"}, {"library": "cpp_nginx", "version": "prod"}, {"library": "dotnet", "version": "prod"}, {"library": "golang", "version": "prod"}, {"library": "java", "version": "prod"}, {"library": "nodejs", "version": "prod"}, {"library": "php", "version": "prod"}, {"library": "python", "version": "prod"}, {"library": "python_lambda", "version": "prod"}, {"library": "ruby", "version": "prod"}, {"library": "rust", "version": "prod"}, {"library": "cpp", "version": "dev"}, {"library": "cpp_httpd", "version": "dev"}, {"library": "cpp_nginx", "version": "dev"}, {"library": "dotnet", "version": "dev"}, {"library": "golang", "version": "dev"}, {"library": "java", "version": "dev"}, {"library": "nodejs", "version": "dev"}, {"library": "php", "version": "dev"}, {"library": "python", "version": "dev"}, {"library": "python_lambda", "version": "dev"}, {"library": "ruby", "version": "dev"}, {"library": "rust", "version": "dev"}]'
all_lib_with_dev = 'libraries_with_dev=["cpp", "cpp_httpd", "cpp_nginx", "dotnet", "golang", "java", "nodejs", "php", "python", "python_lambda", "ruby", "rust"]'


def set_env(key, value):
    """Decorator to set an environment variable before test runs using monkeypatch."""

    def decorator(func):
        @wraps(func)
        def wrapper(self):
            monkeypatch = pytest.MonkeyPatch()
            try:
                monkeypatch.setenv(key, value)
                # Recreate inputs with the new environment variable
                self.inputs = Inputs(scenario_map_file="tests/test_the_test/scenarios.json", modified_files=[])
                return func(self)
            finally:
                monkeypatch.undo()

        return wrapper

    return decorator


@scenarios.test_the_test
class Test_ComputeLibrariesAndScenarios:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup method that runs before each test to create a fresh Inputs object."""
        self.inputs = Inputs(scenario_map_file="tests/test_the_test/scenarios.json", modified_files=[])

    def test_complete_file_path(self):
        self.inputs.modified_files = [".github/workflows/run-docker-ssi.yml"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="docker_ssi"',
        ]

    def test_multiple_file_changes(self):
        self.inputs.modified_files = [".github/workflows/run-docker-ssi.yml", "README.md"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="docker_ssi"',
        ]

    def test_unknown_file_path(self):
        self.inputs.modified_files = ["this_does_not_exist"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="all"',
        ]

    def test_docker_file(self):
        self.inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
            'libraries_with_dev=["python"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_REF", "refs/heads/main")
    def test_ref_main(self):
        self.inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="all"',
        ]

    def test_manifest(self):
        self.inputs.modified_files = ["manifests/python.yml"]
        self.inputs.new_manifests = load_manifests("./tests/test_the_test/manifests/manifests_python_edit/")
        self.inputs.old_manifests = load_manifests("./tests/test_the_test/manifests/manifests_ref/")

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python", "version": "prod"}, {"library": "python", "version": "dev"}]',
            'libraries_with_dev=["python"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups=""',
        ]

    def test_manifest_agent(self):
        self.inputs.modified_files = ["manifests/agent.yml"]
        self.inputs.new_manifests = load_manifests("./tests/test_the_test/manifests/manifests_agent_edit/")
        self.inputs.old_manifests = load_manifests("./tests/test_the_test/manifests/manifests_ref/")

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,OTEL_LOG_E2E"',
            'scenario_groups=""',
        ]

    def test_multiple_pattern_matches(self):
        self.inputs.modified_files = ["requirements.txt"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="all"',
        ]

    def test_test_file(self):
        self.inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
            'scenario_groups=""',
        ]

    def test_test_file_utils(self):
        self.inputs.modified_files = ["tests/auto_inject/utils.py"]

        strings_out = process(self.inputs)

        assert strings_out == [
            all_lib_matrix,
            all_lib_with_dev,
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="CHAOS_INSTALLER_AUTO_INJECTION,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,DEFAULT,DEMO_AWS,HOST_AUTO_INJECTION_INSTALL_SCRIPT,HOST_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,INSTALLER_AUTO_INJECTION,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION,LOCAL_AUTO_INJECTION_INSTALL_SCRIPT,MULTI_INSTALLER_AUTO_INJECTION,SIMPLE_AUTO_INJECTION_APPSEC,SIMPLE_AUTO_INJECTION_PROFILING,SIMPLE_INSTALLER_AUTO_INJECTION"',
            'scenario_groups=""',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_library_tag(self):
        self.inputs.modified_files = ["utils/build/docker/java/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag(self):
        self.inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        with pytest.raises(ValueError):
            process(self.inputs)

    @set_env("GITHUB_PR_TITLE", "[java@main] Some title")
    def test_wrong_library_tag_with_branch(self):
        self.inputs.modified_files = ["utils/build/docker/python/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="end_to_end,open_telemetry"',
        ]

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag_with_test_file(self):
        self.inputs.modified_files = ["tests/auto_inject/test_auto_inject_guardrail.py"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION"',
            'scenario_groups=""',
        ]

    def test_lambda_proxy(self):
        self.inputs.modified_files = ["utils/build/docker/lambda_proxy/pyproject.toml"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python_lambda", "version": "prod"}, {"library": "python_lambda", "version": "dev"}]',
            'libraries_with_dev=["python_lambda"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=true",
            'scenarios="DEFAULT"',
            'scenario_groups="lambda_end_to_end"',
        ]

    def test_doc(self):
        self.inputs.modified_files = ["binaries/dd-trace-go/_tools/README.md"]

        strings_out = process(self.inputs)

        assert strings_out == [
            "library_matrix=[]",
            "libraries_with_dev=[]",
            "desired_execution_time=3600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups=""',
        ]

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "pull_request")
    @set_env("CI_COMMIT_REF_NAME", "")
    def test_gitlab(self):
        self.inputs.modified_files = ["README.md"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'CI_PIPELINE_SOURCE="pull_request"',
            'CI_COMMIT_REF_NAME=""',
            'scenarios="DEFAULT"',
            'scenario_groups=""',
        ]

    def test_manifest_no_edit(self):
        self.inputs.modified_files = ["manifests/java.yml"]
        self.inputs.new_manifests = load_manifests("./tests/test_the_test/manifests/manifests_ref/")
        self.inputs.old_manifests = load_manifests("./tests/test_the_test/manifests/manifests_ref/")

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups=""',
        ]

    @set_env("GITHUB_PR_TITLE", "[perl] Some title")
    def test_unknown_library_tag(self):
        self.inputs.modified_files = ["utils/build/docker/java/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "java", "version": "prod"}, {"library": "java", "version": "dev"}]',
            'libraries_with_dev=["java"]',
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="end_to_end,open_telemetry"',
        ]

    def test_otel_library(self):
        self.inputs.modified_files = ["utils/build/docker/python_otel/test.Dockerfile"]

        strings_out = process(self.inputs)

        assert strings_out == [
            'library_matrix=[{"library": "python_otel", "version": "prod"}]',
            "libraries_with_dev=[]",
            "desired_execution_time=600",
            "rebuild_lambda_proxy=false",
            'scenarios="DEFAULT"',
            'scenario_groups="open_telemetry"',
        ]

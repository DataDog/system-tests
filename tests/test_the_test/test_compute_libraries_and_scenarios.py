from collections.abc import Callable
import json
from pathlib import Path

from functools import wraps

import pytest
from utils.scripts.compute_libraries_and_scenarios import Inputs, process
from utils import scenarios


default_libs_with_prod = [
    "cpp",
    "cpp_httpd",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "nodejs",
    "otel_collector",
    "php",
    "python",
    "python_lambda",
    "ruby",
]
default_libs_with_dev = [
    "cpp",
    "cpp_httpd",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "nodejs",
    "php",
    "python",
    "python_lambda",
    "ruby",
    "rust",
]
default_otel_libs = ["java_otel", "nodejs_otel", "python_otel"]


@pytest.fixture(autouse=True)
def set_default_env():
    default_env = {
        "CI_PIPELINE_SOURCE": "",
        "CI_COMMIT_REF_NAME": "",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REF": "",
        "GITHUB_PR_TITLE": "",
    }
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.delenv("GITLAB_CI", raising=False)
        for name, value in default_env.items():
            monkeypatch.setenv(name, value)
        yield
    finally:
        monkeypatch.undo()


def set_env(key: str, value: str):
    """Decorator to set an environment variable before test runs using monkeypatch."""

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self: object):
            monkeypatch = pytest.MonkeyPatch()
            try:
                monkeypatch.setenv(key, value)
                return func(self)
            finally:
                monkeypatch.undo()

        return wrapper

    return decorator


def build_inputs(
    modified_files: list | None = None,
    new_manifests: Path = Path("./tests/test_the_test/manifests/manifests_ref/"),
    old_manifests: Path = Path("./tests/test_the_test/manifests/manifests_ref/"),
):
    if modified_files is None:
        modified_files = []
    with open("modified_files.txt", "w") as f:
        f.writelines(f"{line}\n" for line in modified_files)
    inputs = Inputs(
        scenario_map_file="tests/test_the_test/scenarios.json",
        new_manifests=new_manifests,
        old_manifests=old_manifests,
    )
    Path.unlink(Path("modified_files.txt"))
    return inputs


def assert_github_processor(
    inputs: Inputs,
    libs_with_prod: list[str],
    libs_with_dev: list[str],
    desired_execution_time: int,
    rebuild_lambda_proxy: str,
    scenarios: str,
    scenarios_groups: str,
):
    def get_value(output_line: str) -> str:
        return output_line.split("=", 1)[1]

    def get_json_value(output_line: str) -> list:
        return json.loads(get_value(output_line))

    expected_library_matrix = [{"library": lib, "version": "prod"} for lib in sorted(libs_with_prod)] + [
        {"library": lib, "version": "dev"} for lib in sorted(libs_with_dev)
    ]

    output = process(inputs)

    assert get_json_value(output[0]) == expected_library_matrix
    assert get_json_value(output[1]) == libs_with_dev
    assert get_json_value(output[2]) == desired_execution_time
    assert get_value(output[3]) == rebuild_lambda_proxy
    assert get_json_value(output[4]) == scenarios
    assert get_json_value(output[5]) == scenarios_groups


@scenarios.test_the_test
class Test_ComputeLibrariesAndScenarios:
    def test_complete_file_path(self):
        inputs = build_inputs([".github/workflows/run-docker-ssi.yml"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "docker_ssi",
        )

    def test_multiple_file_changes(self):
        inputs = build_inputs([".github/workflows/run-docker-ssi.yml", "README.md"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "docker_ssi",
        )

    def test_unknown_file_path(self):
        inputs = build_inputs(["this_does_not_exist"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "all",
        )

    def test_docker_file(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["python"],
            ["python"],
            600,
            "false",
            "DEFAULT",
            "end_to_end,open_telemetry",
        )

    @set_env("GITHUB_REF", "refs/heads/main")
    def test_ref_main(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        assert_github_processor(inputs, default_libs_with_prod, default_libs_with_dev, 3600, "false", "DEFAULT", "all")

    def test_manifest(self):
        inputs = build_inputs(
            ["manifests/python.yml"],
            new_manifests=Path("./tests/test_the_test/manifests/manifests_python_edit/"),
            old_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
        )
        assert_github_processor(
            inputs,
            ["python"],
            ["python"],
            600,
            "false",
            "APPSEC_API_SECURITY,DEFAULT",
            "",
        )

    def test_manifest_agent(self):
        inputs = build_inputs(
            ["manifests/agent.yml"],
            new_manifests=Path("./tests/test_the_test/manifests/manifests_agent_edit/"),
            old_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
        )
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,SAMPLING",
            "",
        )

    def test_multiple_pattern_matches(self):
        inputs = build_inputs(["requirements.txt"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "all",
        )

    def test_test_file(self):
        inputs = build_inputs(["tests/auto_inject/test_auto_inject_guardrail.py"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION",
            "",
        )

    def test_test_file_utils(self):
        inputs = build_inputs(["tests/auto_inject/utils.py"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "CHAOS_INSTALLER_AUTO_INJECTION,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,DEFAULT,HOST_AUTO_INJECTION_INSTALL_SCRIPT,HOST_AUTO_INJECTION_INSTALL_SCRIPT_APPSEC,HOST_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING,INSTALLER_AUTO_INJECTION,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION,LOCAL_AUTO_INJECTION_INSTALL_SCRIPT,MULTI_INSTALLER_AUTO_INJECTION,SIMPLE_AUTO_INJECTION_APPSEC,SIMPLE_AUTO_INJECTION_PROFILING,SIMPLE_INSTALLER_AUTO_INJECTION",
            "",
        )

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_library_tag(self):
        inputs = build_inputs(["utils/build/docker/java/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["java"],
            ["java"],
            600,
            "false",
            "DEFAULT",
            "end_to_end,open_telemetry",
        )

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["java", "python"],
            ["java", "python"],
            3600,
            "false",
            "DEFAULT",
            "end_to_end,open_telemetry",
        )

    @set_env("GITHUB_PR_TITLE", "[java@main] Some title")
    def test_wrong_library_tag_with_branch(self):
        inputs = build_inputs(["utils/build/docker/python/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["java"],
            ["java"],
            600,
            "false",
            "DEFAULT",
            "end_to_end,open_telemetry",
        )

    @set_env("GITHUB_PR_TITLE", "[java] Some title")
    def test_wrong_library_tag_with_test_file(self):
        inputs = build_inputs(["tests/auto_inject/test_auto_inject_guardrail.py"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,INSTALLER_NOT_SUPPORTED_AUTO_INJECTION",
            "",
        )

    def test_lambda_proxy(self):
        inputs = build_inputs(["utils/build/docker/lambda_proxy/pyproject.toml"])

        assert_github_processor(
            inputs,
            ["python_lambda"],
            ["python_lambda"],
            600,
            "true",
            "DEFAULT",
            "lambda_end_to_end",
        )

    def test_doc(self):
        inputs = build_inputs(["binaries/dd-trace-go/_tools/README.md"])

        assert_github_processor(
            inputs,
            [],
            [],
            3600,
            "false",
            "DEFAULT",
            "",
        )

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
            new_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
            old_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
        )
        assert_github_processor(
            inputs,
            ["java"],
            ["java"],
            600,
            "false",
            "DEFAULT",
            "",
        )

    @set_env("GITHUB_PR_TITLE", "[perl] Some title")
    def test_unknown_library_tag(self):
        inputs = build_inputs(["utils/build/docker/java/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["java"],
            ["java"],
            600,
            "false",
            "DEFAULT",
            "end_to_end,open_telemetry",
        )

    def test_otel_library(self):
        inputs = build_inputs(["utils/build/docker/python_otel/test.Dockerfile"])

        assert_github_processor(
            inputs,
            ["python_otel"],
            [],
            600,
            "false",
            "DEFAULT",
            "open_telemetry",
        )

    def test_otel_test_file(self):
        inputs = build_inputs(modified_files=["tests/integrations/test_open_telemetry.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod + default_otel_libs,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,OTEL_INTEGRATIONS",
            "",
        )

    def test_json_modification(self):
        inputs = build_inputs(modified_files=["tests/debugger/utils/probe_snapshot_log_line.json"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEBUGGER_EXCEPTION_REPLAY,DEBUGGER_EXPRESSION_LANGUAGE,DEBUGGER_INPRODUCT_ENABLEMENT,DEBUGGER_PII_REDACTION,DEBUGGER_PROBES_SNAPSHOT,DEBUGGER_PROBES_SNAPSHOT_WITH_SCM,DEBUGGER_PROBES_STATUS,DEBUGGER_SYMDB,DEBUGGER_TELEMETRY,DEFAULT,TRACING_CONFIG_NONDEFAULT_4",
            "",
        )

    def test_missing_modified_files(self):
        with pytest.raises(FileNotFoundError):
            Inputs(
                scenario_map_file="tests/test_the_test/scenarios.json",
                new_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
                old_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
            )

    def test_missing_original_manifest(self):
        with pytest.raises(FileNotFoundError):
            Inputs(
                scenario_map_file="tests/test_the_test/scenarios.json",
                new_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
                old_manifests=Path("./wrong/path"),
            )

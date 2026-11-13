from collections.abc import Callable
import json
from pathlib import Path

from functools import wraps

from utils import pytest
from utils.scripts.compute_libraries_and_scenarios import (
    Inputs,
    get_gitlab_ssi_libraries,
    get_gitlab_ssi_library,
    process,
)
from utils import scenarios
from utils._context._scenarios import scenario_groups as all_scenario_groups


default_libs_with_prod = [
    "cpp",
    "cpp_httpd",
    "cpp_kong",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "java_lambda",
    "nodejs",
    "nodejs_lambda",
    "otel_collector",
    "php",
    "python",
    "python_lambda",
    "ruby",
    "ruby_lambda",
    "rust",
]
default_libs_with_dev = [
    "cpp",
    "cpp_httpd",
    "cpp_kong",
    "cpp_nginx",
    "dotnet",
    "golang",
    "java",
    "java_lambda",
    "nodejs",
    "nodejs_lambda",
    "php",
    "python",
    "python_lambda",
    "ruby",
    "ruby_lambda",
    "rust",
]
default_otel_libs = ["java_otel", "python_otel"]


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
    *,
    select_main_push_from_diff: bool = False,
):
    if modified_files is None:
        modified_files = []
    with open("modified_files.txt", "w") as f:
        f.writelines(f"{line}\n" for line in modified_files)
    inputs = Inputs(
        scenario_map_file="tests/test_the_test/scenarios.json",
        new_manifests=new_manifests,
        old_manifests=old_manifests,
        select_main_push_from_diff=select_main_push_from_diff,
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

    def test_gitlab_ssi_title_resolver_file_does_not_select_scenarios(self):
        inputs = build_inputs(["utils/scripts/ci_orchestrators/resolve_gitlab_pr_title.sh"])

        assert_github_processor(
            inputs,
            [],
            [],
            3600,
            "false",
            "DEFAULT",
            "",
        )

    def test_gitignore_does_not_select_scenarios(self):
        inputs = build_inputs([".gitignore"])

        assert_github_processor(
            inputs,
            [],
            [],
            3600,
            "false",
            "DEFAULT",
            "",
        )

    def test_review_learning_files_do_not_select_scenarios(self):
        inputs = build_inputs(
            [
                ".agents/skills/system-tests-review-learn/SKILL.md",
                ".gitignore",
                ".claude/skills/system-tests-review-learn/SKILL.md",
                "docs/ai/review-learning.md",
                "tests/test_the_test/test_review_learning.py",
                "utils/scripts/review_learning/collect.py",
                "utils/scripts/review_learning/filters.yml",
            ]
        )

        assert_github_processor(
            inputs,
            [],
            [],
            3600,
            "false",
            "DEFAULT",
            "",
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
            "end_to_end,integration_frameworks,open_telemetry",
        )

    def test_aws_java_weblog_file(self):
        inputs = build_inputs(["utils/build/virtual_machine/weblogs/java/provision_test-app-java.yml"])

        assert_github_processor(
            inputs,
            ["java"],
            ["java"],
            600,
            "false",
            "DEFAULT",
            "onboarding",
        )

    @pytest.mark.parametrize(
        ("library", "file", "scenario_groups"),
        [
            (
                "dotnet",
                "lib-injection/build/docker/dotnet/dd-lib-dotnet-init-test-app/Dockerfile",
                "docker_ssi,lib_injection,onboarding",
            ),
            (
                "java",
                "lib-injection/build/docker/java/dd-lib-java-init-test-app/Dockerfile",
                "docker_ssi,lib_injection,onboarding",
            ),
            (
                "nodejs",
                "lib-injection/build/docker/nodejs/sample-app/Dockerfile",
                "docker_ssi,lib_injection,onboarding",
            ),
            ("php", "lib-injection/build/docker/php/dd-lib-php-init-test-app/Dockerfile", "lib_injection"),
            (
                "python",
                "lib-injection/build/docker/python/dd-lib-python-init-test-django/Dockerfile",
                "docker_ssi,lib_injection,onboarding",
            ),
            (
                "ruby",
                "lib-injection/build/docker/ruby/dd-lib-ruby-init-test-rails/Dockerfile",
                "docker_ssi,lib_injection,onboarding",
            ),
        ],
    )
    def test_lib_injection_weblog_file(self, library: str, file: str, scenario_groups: str) -> None:
        inputs = build_inputs([file])

        assert_github_processor(
            inputs,
            [library],
            [library],
            300 if library == "nodejs" else 600,
            "false",
            "DEFAULT",
            scenario_groups,
        )

    @pytest.mark.parametrize(
        "file",
        [
            "lib-injection/build/build_lib_injection_images.sh",
            "lib-injection/build/build_lib_injection_weblog.sh",
        ],
    )
    def test_lib_injection_build_script(self, file: str) -> None:
        inputs = build_inputs([file])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "lib_injection",
        )

    def test_integration_frameworks_docker_file(self):
        for library, file, desired_execution_time in (
            ("python", "utils/build/docker/python/openai-py.Dockerfile", 600),
            ("python", "utils/build/docker/python/anthropic_app/main.py", 600),
            ("nodejs", "utils/build/docker/nodejs/google_genai-js.Dockerfile", 300),
            ("java", "utils/build/docker/java/openai_app/pom.xml", 600),
        ):
            inputs = build_inputs([file])

            assert_github_processor(
                inputs,
                [library],
                [library],
                desired_execution_time,
                "false",
                "DEFAULT",
                "end_to_end,integration_frameworks,open_telemetry",
            )

    def test_python_parametric_base_docker_file(self):
        inputs = build_inputs(["utils/build/docker/python/parametric.base.Dockerfile"])

        assert_github_processor(
            inputs,
            ["python"],
            ["python"],
            600,
            "false",
            "DEFAULT,PARAMETRIC",
            "",
        )

    def test_php_parametric_base_docker_file(self):
        inputs = build_inputs(["utils/build/docker/php/parametric.base.Dockerfile"])

        assert_github_processor(
            inputs,
            ["php"],
            ["php"],
            600,
            "false",
            "DEFAULT,PARAMETRIC",
            "",
        )

    def test_nodejs_docker_file(self):
        inputs = build_inputs(["utils/build/docker/nodejs/express5.Dockerfile"])

        assert_github_processor(
            inputs,
            ["nodejs"],
            ["nodejs"],
            300,
            "false",
            "DEFAULT",
            "end_to_end,integration_frameworks,open_telemetry",
        )

    def test_c_docker_file(self):
        inputs = build_inputs(["utils/build/docker/c/perl-mojolicious.Dockerfile"])

        assert_github_processor(
            inputs,
            [],
            [],
            600,
            "false",
            "DEFAULT",
            "end_to_end",
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

    def test_gitlab_libraries_config_runs_all_but_ssi(self):
        inputs = build_inputs(["utils/scripts/gitlab_libraries.py"])

        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,PARAMETRIC",
            "end_to_end,exotics,ffe,integration_frameworks,open_telemetry",
        )

    @pytest.mark.parametrize("pattern", ["utils/scripts/gitlab_libraries.py", "utils/ci/gitlab/*"])
    def test_gitlab_libraries_config_scenarios(self, pattern: str):
        """The rules of the GitLab end-to-end pipeline select every scenario of the all group but the SSI ones"""
        ssi_workflows = {"aws_ssi", "dockerssi", "libinjection", "k8s_injector_dev"}
        param = build_inputs([]).impacts[pattern]
        selected = {
            scenario.name for group in param.scenario_groups for scenario in all_scenario_groups[group].scenarios
        }
        selected |= param.scenarios
        all_group = all_scenario_groups.all.scenarios

        assert selected >= {scenario.name for scenario in all_group if scenario.github_workflow not in ssi_workflows}
        assert not selected & {scenario.name for scenario in all_group if scenario.github_workflow in ssi_workflows}
        # the exotics job of .github/workflows/ci.yml runs on the exotics or all group only
        assert "exotics" in param.scenario_groups

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

    def test_sub_utils_folder(self):
        """Checks that if a file inside ./tests/xx/utils/ folder is modified, then all files ./tests/xx/test_stuff.py will be executed"""

        inputs = build_inputs(["tests/schemas/utils/core.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,TRACE_STATS_COMPUTATION",
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
            "end_to_end,integration_frameworks,open_telemetry",
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
            "end_to_end,integration_frameworks,open_telemetry",
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
            "end_to_end,integration_frameworks,open_telemetry",
        )

    @set_env("GITHUB_PR_TITLE", "[c@feature/native-http] Some title")
    def test_c_library_tag_with_branch(self):
        inputs = build_inputs(["utils/build/docker/c/perl-mojolicious.Dockerfile"])

        assert_github_processor(
            inputs,
            [],
            [],
            600,
            "false",
            "DEFAULT",
            "end_to_end",
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
            ["java_lambda", "nodejs_lambda", "python_lambda", "ruby_lambda"],
            ["java_lambda", "nodejs_lambda", "python_lambda", "ruby_lambda"],
            3600,
            "true",
            "DEFAULT",
            "lambda_end_to_end",
        )

    def test_ruby_lambda_docker_file(self):
        inputs = build_inputs(["utils/build/docker/ruby_lambda/ruby-apigw-rest.Dockerfile"])

        assert_github_processor(
            inputs,
            ["ruby_lambda"],
            ["ruby_lambda"],
            600,
            "false",
            "DEFAULT",
            "appsec_lambda",
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

    def test_agent_tooling_files(self):
        for file in (
            ".agents/config.json",
            ".claude/settings.json",
            ".cursor/mcp.json",
            ".promptfoo/tests_overview.yaml",
            "format.sh",
            "utils/scripts/check_agent_instructions.py",
        ):
            inputs = build_inputs([file])

            assert_github_processor(
                inputs,
                default_libs_with_prod,
                default_libs_with_dev,
                3600,
                "false",
                "DEFAULT",
                "",
            )

    def test_nix_workflow(self):
        inputs = build_inputs([".github/workflows/nix.yml"])

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
            'ssi_libraries=""',
            'scenarios="DEFAULT"',
            'scenarios_groups=""',
        ]

    @pytest.mark.parametrize(
        ("pr_title", "expected"),
        [
            ("", None),
            ("[nodejs] Test Node.js", "nodejs"),
            ("[java] Test Java", "java"),
            ("[dotnet] Test .NET", "dotnet"),
            ("[PYTHON] Test Python", "python"),
            ("[php] Test PHP", "php"),
            ("[ruby] Test Ruby", "ruby"),
            ("[golang] Test Go", None),
            ("[java@feature] Test a Java branch", None),
            ("Test Java [java]", None),
        ],
    )
    def test_gitlab_ssi_library_title(self, pr_title: str, expected: str | None):
        assert get_gitlab_ssi_library(pr_title) == expected

    @pytest.mark.parametrize(
        ("pr_title", "impacted_libraries", "expected"),
        [
            ("", {"java"}, {"java"}),
            ("", {"java", "python_lambda"}, {"java"}),
            ("", {"golang"}, set()),
            ("[nodejs] Test Node.js", {"java"}, {"nodejs"}),
            ("[java@feature] Test a Java branch", {"python"}, {"python"}),
        ],
    )
    def test_gitlab_ssi_libraries(
        self,
        pr_title: str,
        impacted_libraries: set[str],
        expected: set[str],
    ) -> None:
        assert get_gitlab_ssi_libraries(pr_title, impacted_libraries) == expected

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "pull_request")
    @set_env("CI_COMMIT_REF_NAME", "")
    @set_env("GITHUB_PR_TITLE", "[java] Test Java")
    def test_gitlab_ssi_library_output(self):
        inputs = build_inputs(["README.md"])

        assert 'ssi_libraries="java"' in process(inputs)

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "push")
    @set_env("CI_COMMIT_REF_NAME", "feature/aws-java-weblog")
    def test_gitlab_ssi_libraries_from_aws_weblog(self):
        inputs = build_inputs(["utils/build/virtual_machine/weblogs/java/provision_test-app-java.yml"])

        output = process(inputs)
        assert 'ssi_libraries="java"' in output
        assert 'scenarios_groups="onboarding"' in output

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "push")
    @set_env("CI_COMMIT_REF_NAME", "feature/k8s-nodejs-weblog")
    def test_gitlab_ssi_libraries_from_lib_injection_weblog(self):
        inputs = build_inputs(["lib-injection/build/docker/nodejs/sample-app/Dockerfile"])

        output = process(inputs)
        assert 'ssi_libraries="nodejs"' in output
        assert 'scenarios_groups="docker_ssi,lib_injection,onboarding"' in output

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "push")
    @set_env("CI_COMMIT_REF_NAME", "feature/common-aws-weblog")
    def test_gitlab_ssi_libraries_from_common_file(self):
        inputs = build_inputs(["utils/build/virtual_machine/weblogs/common/pull_agent_image.sh"])

        output = process(inputs)
        assert 'ssi_libraries="dotnet java nodejs php python ruby"' in output
        assert 'scenarios_groups="onboarding"' in output

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "push")
    @set_env("CI_COMMIT_REF_NAME", "feature/docker-ssi-scenario")
    def test_gitlab_ssi_libraries_from_scenario(self):
        inputs = build_inputs(["utils/_context/_scenarios/docker_ssi.py"])

        assert 'ssi_libraries="dotnet java nodejs php python ruby"' in process(inputs)

    @set_env("GITLAB_CI", "true")
    @set_env("CI_PIPELINE_SOURCE", "push")
    @set_env("CI_COMMIT_REF_NAME", "feature/golang-weblog")
    def test_gitlab_ssi_libraries_empty_for_unsupported_library(self):
        inputs = build_inputs(["lib-injection/build/docker/golang/sample-app/Dockerfile"])

        output = process(inputs)
        assert 'ssi_libraries=""' in output
        assert 'scenarios_groups="lib_injection"' in output

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
            "end_to_end,integration_frameworks,open_telemetry",
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

    def test_agentless_ffe_test_file(self):
        inputs = build_inputs(modified_files=["tests/ffe/test_agentless_configuration.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS",
            "",
        )

    def test_exposure_egress_test_file(self):
        inputs = build_inputs(modified_files=["tests/ffe/test_exposure_egress.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,FEATURE_FLAGGING_AND_EXPERIMENTATION,"
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_DIRECT,"
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_SERVERLESS",
            "",
        )

    def test_scenario_definition_file_with_two_scenarios(self):
        """appsec_blocking.py defines two scenarios: both run, and only them"""
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/appsec_blocking.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "APPSEC_BLOCKING,APPSEC_BLOCKING_FULL_DENYLIST,DEFAULT",
            "",
        )

    def test_scenarios_init_file(self):
        """It only instantiates scenarios: nothing runs"""
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/__init__.py"])
        assert_github_processor(inputs, [], [], 3600, "false", "DEFAULT", "")

    def test_fake_datadog_keys_file(self):
        """Tests get the fake keys from the scenario, none depends on a value: nothing runs"""
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/_core/fake_datadog_keys.py"])
        assert_github_processor(inputs, [], [], 3600, "false", "DEFAULT", "")

    @pytest.mark.parametrize(
        "file",
        [
            "utils/_context/_scenarios/_core/scenario.py",
            "utils/_context/_scenarios/_core/__init__.py",
            "utils/_context/_scenarios/_core/new_module.py",  # any future module of _core
            "utils/_context/_scenarios/new_package/module.py",  # any other subfolder
        ],
    )
    def test_scenario_core_file(self, file: str):
        """Base classes shared by many scenarios, or any other subfolder: everything runs"""
        inputs = build_inputs(modified_files=[file])
        assert_github_processor(inputs, default_libs_with_prod, default_libs_with_dev, 3600, "false", "DEFAULT", "all")

    def test_open_telemetry_scenario_file(self):
        """No scenario group, but the scenarios it defines run, only with OTel libraries"""
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/open_telemetry.py"])
        assert_github_processor(
            inputs,
            default_otel_libs,
            [],
            3600,
            "false",
            "DEFAULT,OTEL_INTEGRATIONS",
            "",
        )

    @pytest.mark.parametrize("file", ["utils/mocked_backend/ffe.py", "utils/mocked_backend/_backend_ffe.py"])
    def test_agentless_ffe_mocked_backend_file(self, file: str):
        inputs = build_inputs(modified_files=[file])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,PARAMETRIC",
            "agentless",
        )

    @pytest.mark.parametrize(
        "file",
        [
            "utils/mocked_backend/__init__.py",
            "utils/mocked_backend/__main__.py",
            "utils/mocked_backend/_backend.py",
            "utils/mocked_backend/_client.py",
            "utils/mocked_backend/_request_handler.py",
            "utils/mocked_backend/_utils.py",
            "utils/mocked_backend/_tls.py",
        ],
    )
    def test_generic_mocked_backend_file(self, file: str):
        inputs = build_inputs(modified_files=[file])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "APM_TRACING_E2E_OTEL,APM_TRACING_E2E_SINGLE_SPAN,DEFAULT,PARAMETRIC",
            "agentless",
        )

    def test_end_to_end_scenario_framework_file(self):
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/_core/endtoend.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT",
            "end_to_end",
        )

    def test_end_to_end_agentless_scenario_framework_file(self):
        inputs = build_inputs(modified_files=["utils/_context/_scenarios/agentless_endtoend.py"])
        assert_github_processor(
            inputs,
            default_libs_with_prod,
            default_libs_with_dev,
            3600,
            "false",
            "DEFAULT,FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS,"
            "FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_DIRECT,FEATURE_FLAGGING_AND_EXPERIMENTATION_AGENTLESS_SERVERLESS",
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
            "DEBUGGER_CAPTURE_TIMEOUT,DEBUGGER_EVALUATION_TIMEOUT,DEBUGGER_EXCEPTION_REPLAY,DEBUGGER_EXPRESSION_LANGUAGE,DEBUGGER_INPRODUCT_ENABLEMENT,DEBUGGER_PII_REDACTION,DEBUGGER_PROBES_SNAPSHOT,DEBUGGER_PROBES_SNAPSHOT_WITH_SCM,DEBUGGER_SYMDB,DEBUGGER_TELEMETRY,DEFAULT,TRACING_CONFIG_NONDEFAULT_4",
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


@scenarios.test_the_test
class Test_GitLabMode:
    @pytest.mark.parametrize(
        ("source", "expected_event"),
        [("merge_request_event", "pull_request"), ("push", "push"), ("schedule", "schedule")],
    )
    def test_event_and_ref_normalization(self, monkeypatch: pytest.MonkeyPatch, source: str, expected_event: str):
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", source)
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "feat-x")
        inputs = build_inputs()
        assert inputs.event_name == expected_event
        assert inputs.ref == "refs/heads/feat-x"
        assert inputs.is_gitlab

    def test_empty_ref(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "")
        inputs = build_inputs()
        assert inputs.ref == ""

    def test_libraries_output_sorted(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "feat-x")
        # all-libs trigger file
        inputs = build_inputs(modified_files=[".github/workflows/run-docker-ssi.yml"])
        output = process(inputs)
        libs_line = next((line for line in output if line.startswith("libraries=")), None)
        assert libs_line is not None, "GitLab mode must emit 'libraries=' output"
        libs = json.loads(libs_line.split("=", 1)[1])
        parts = libs.split()
        assert parts == sorted(parts)

    @pytest.mark.parametrize("source", ["merge_request_event", "push"])
    def test_pr_pipeline_selects_c(self, monkeypatch: pytest.MonkeyPatch, source: str) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", source)
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "feature/native-c")
        inputs = build_inputs(modified_files=["utils/build/docker/c/perl-mojolicious.Dockerfile"])

        assert 'libraries="c"' in process(inputs)

    @staticmethod
    def _library_weblog_scenarios(output: list[str]) -> dict | None:
        line = next((line for line in output if line.startswith("library_weblog_scenarios=")), None)
        return None if line is None else json.loads(json.loads(line.split("=", 1)[1]))

    @pytest.mark.parametrize("source", ["merge_request_event", "push"])
    def test_pr_pipeline_selects_php_weblog_map(self, monkeypatch: pytest.MonkeyPatch, source: str) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", source)
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "feature/php")
        inputs = build_inputs(modified_files=["utils/build/docker/php/apache-mod-8.0.Dockerfile"])

        output = process(inputs)
        assert self._library_weblog_scenarios(output) == {"php": {"apache-mod-8.0": ["THREAD_CONTEXT_SHARING"]}}
        assert not any(line.startswith("libraries=") for line in output)

    def test_pr_pipeline_does_not_select_php_if_not_impacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "feature/c")
        inputs = build_inputs(modified_files=["utils/build/docker/c/perl-mojolicious.Dockerfile"])

        assert self._library_weblog_scenarios(process(inputs)) is None

    def test_main_push_uses_main_weblog_maps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "main")
        inputs = build_inputs(modified_files=["utils/build/docker/python/flask-poc.Dockerfile"])

        output = process(inputs)
        assert 'libraries="python"' in output
        # python runs all its weblogs on main, php only its weblog map
        assert self._library_weblog_scenarios(output) == {"php": {"apache-mod-8.0": ["THREAD_CONTEXT_SHARING"]}}

    @pytest.mark.parametrize(
        ("source", "ref"),
        [("push", "some_branch"), ("schedule", "main"), ("schedule", "some_branch")],
    )
    def test_non_main_and_scheduled_pipelines_do_not_select_python(
        self,
        monkeypatch: pytest.MonkeyPatch,
        source: str,
        ref: str,
    ) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", source)
        monkeypatch.setenv("CI_COMMIT_REF_NAME", ref)
        inputs = build_inputs()

        assert 'libraries="python"' not in process(inputs)

    def test_main_push_without_opt_in_keeps_full_matrix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "main")
        inputs = build_inputs(modified_files=["utils/virtual_machine/virtual_machines.json"])

        output = process(inputs)
        assert 'libraries="python"' in output
        assert 'scenarios_groups="all"' in output
        assert not any(line.startswith("ssi_libraries=") for line in output)

    def test_main_push_with_opt_in_selects_only_impacted_scenarios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "main")
        inputs = build_inputs(
            modified_files=["utils/virtual_machine/virtual_machines.json"],
            select_main_push_from_diff=True,
        )

        output = process(inputs)
        assert 'libraries="python"' in output
        assert 'ssi_libraries="dotnet java nodejs php python ruby"' in output
        assert 'scenarios_groups="onboarding"' in output
        assert 'scenarios_groups="all"' not in output

    def test_main_push_with_opt_in_compares_manifests(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "push")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "main")
        inputs = build_inputs(
            modified_files=["manifests/python.yml"],
            new_manifests=Path("./tests/test_the_test/manifests/manifests_python_edit/"),
            old_manifests=Path("./tests/test_the_test/manifests/manifests_ref/"),
            select_main_push_from_diff=True,
        )

        output = process(inputs)
        assert 'libraries="python"' in output
        assert 'scenarios="APPSEC_API_SECURITY,DEFAULT"' in output
        assert 'scenarios_groups=""' in output

    def test_scheduled_main_still_selects_all_scenarios(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITLAB_CI", "true")
        monkeypatch.setenv("CI_PIPELINE_SOURCE", "schedule")
        monkeypatch.setenv("CI_COMMIT_REF_NAME", "main")
        inputs = build_inputs(
            modified_files=["utils/virtual_machine/virtual_machines.json"],
            select_main_push_from_diff=True,
        )

        output = process(inputs)
        assert 'scenarios_groups="all"' in output
        assert not any(line.startswith("ssi_libraries=") for line in output)
        assert not any(line.startswith("libraries=") for line in output)

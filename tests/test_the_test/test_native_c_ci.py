from pathlib import Path
import re

import yaml

from utils import scenarios


def _is_ignored(patterns: list[str], check_name: str) -> bool:
    """Return whether ensure-ci-success ignores this check name.

    The action anchors every pattern with ^ and $.
    """
    return any(re.fullmatch(pattern, check_name) is not None for pattern in patterns)


@scenarios.test_the_test
class Test_NativeCGitLabCI:
    def test_generated_jobs_inherit_dind_runner(self) -> None:
        documents = list(yaml.safe_load_all(Path("utils/ci/gitlab/templates.yml").read_text()))
        templates = documents[-1]

        assert templates[".system_tests_base"]["tags"] == ["docker-in-docker:amd64"]
        assert templates[".system_tests_base"]["variables"]["SYSTEM_TESTS_WEBLOG_HOST"] == "localhost"

    def test_coordinator_jobs_remain_on_amd64(self) -> None:
        documents = list(yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text()))
        component = documents[-1]

        assert component[".system_tests_param_base"]["tags"] == ["arch:amd64"]
        assert component["system_tests_build_pipeline"]["tags"] == ["arch:amd64"]

    def test_all_child_pipeline_bridges_are_merge_blocking(self) -> None:
        workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
        ignored_patterns = workflow["jobs"]["all-jobs-are-green"]["steps"][0]["with"]["ignored-name-patterns"]
        patterns = ignored_patterns.splitlines()

        for index in range(3):
            check_name = f"dd-gitlab/system_tests_e2e_run_pipeline_{index}"
            assert not _is_ignored(patterns, check_name)

        assert _is_ignored(patterns, "dd-gitlab/unrelated-job")

    def test_ssi_scenario_jobs_are_merge_blocking(self) -> None:
        workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
        ignored_patterns = workflow["jobs"]["all-jobs-are-green"]["steps"][0]["with"]["ignored-name-patterns"]
        patterns = ignored_patterns.splitlines()

        for check_name in (
            "dd-gitlab/sample.HOS",
            "dd-gitlab/sample.HOS: [weblog]",
            "dd-gitlab/sample.DO5A: [node:22]",
            "dd-gitlab/K8S_LIB_INJECTION: [js-app]",
            "dd-gitlab/Ubuntu_24_amd64.HOS: [test-app-nodejs]",
            "dd-gitlab/js-app.amd64.DOC: [node:22]",
        ):
            assert not _is_ignored(patterns, check_name)

        for check_name in (
            "dd-gitlab/compute_pipeline",
            "dd-gitlab/system_tests_run_php_THREAD_CONTEXT_SHARING_apache-mod-8.0",
            "dd-gitlab/something.DOCUMENTED",
            "devflow/merge",
            "DDCI Status",
        ):
            assert _is_ignored(patterns, check_name)

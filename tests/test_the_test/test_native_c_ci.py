from pathlib import Path
import re

import yaml

from utils import scenarios


def _is_ignored(patterns: list[str], check_name: str) -> bool:
    """Return whether ensure-ci-success ignores this check name.

    The action anchors every pattern with ^ and $.
    """
    return any(re.fullmatch(pattern, check_name) is not None for pattern in patterns)


# Prefixes from gitlab_exporter._generate_unique_prefix for every AWS and Docker SSI scenario.
_SSI_SCENARIO_PREFIXES = (
    "CHA",
    "CO1B",
    "CO9C",
    "CON",
    "DO57",
    "DO5A",
    "DOA9",
    "DOC",
    "HOAA",
    "HOBC",
    "HOS",
    "IN1C",
    "INS",
    "LOC",
    "MUL",
    "SI94",
    "SID0",
    "SIM",
)


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

        for prefix in _SSI_SCENARIO_PREFIXES:
            assert not _is_ignored(patterns, f"dd-gitlab/sample.{prefix}")
            assert not _is_ignored(patterns, f"dd-gitlab/sample.{prefix}: [weblog]")

        assert not _is_ignored(patterns, "dd-gitlab/K8S_LIB_INJECTION: [js-app]")
        assert not _is_ignored(patterns, "dd-gitlab/Ubuntu_24_amd64.HOS: [test-app-nodejs]")
        assert not _is_ignored(patterns, "dd-gitlab/js-app.amd64.DOC: [node:22]")
        assert _is_ignored(patterns, "dd-gitlab/compute_pipeline")
        assert _is_ignored(patterns, "dd-gitlab/system_tests_run_php_THREAD_CONTEXT_SHARING_apache-mod-8.0")
        assert _is_ignored(patterns, "devflow/merge")
        assert _is_ignored(patterns, "DDCI Status")

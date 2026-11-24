from pathlib import Path

import yaml

from utils import scenarios


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

    def test_all_gitlab_jobs_are_merge_blocking(self) -> None:
        pipeline = yaml.safe_load(Path(".gitlab-ci.yml").read_text())
        job = pipeline["all-gitlab-jobs-are-green"]

        # no needs + last stage + default `when: on_success`: it waits for all jobs, and runs only if all succeeded
        assert "needs" not in job
        assert job["stage"] == pipeline["stages"][-1]
        assert job.get("when", "on_success") == "on_success"
        assert job.get("allow_failure", False) is False

    def test_legacy_gate_blocks_on_all_gitlab_jobs(self) -> None:
        workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
        ignored_patterns = workflow["jobs"]["all-jobs-are-green"]["steps"][0]["with"]["ignored-name-patterns"]
        patterns = ignored_patterns.splitlines()

        assert patterns == ["devflow/merge", "devflow/mergegate", "DDCI Status"]

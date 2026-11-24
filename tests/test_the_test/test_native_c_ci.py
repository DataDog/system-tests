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

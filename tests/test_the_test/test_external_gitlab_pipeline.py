"""Tests for utils/scripts/ci_orchestrators/external_gitlab_pipeline.py."""

from pathlib import Path

import yaml

from utils import pytest

from utils import scenarios
from utils.scripts.ci_orchestrators.external_gitlab_pipeline import (
    _is_local_include,
    _strip_local_includes,
    filter_yaml,
)


@scenarios.test_the_test
class Test_ExternalGitlabPipeline:
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ({"local": "/foo"}, True),
            ("bare-string", True),
            ({"project": "p", "file": "f"}, False),
            ({"remote": "https://example.com/x.yml"}, False),
        ],
    )
    def test_is_local_include(self, entry: object, expected: object):
        assert _is_local_include(entry) is expected

    def test_strip_local_includes_removes_only_local(self):
        remote = {"remote": "https://example.com/x.yml"}
        data = {"include": [{"local": "/utils/ci/gitlab/main.yml"}, "bare", remote]}
        _strip_local_includes(data)
        assert data["include"] == [remote]

    def test_filter_yaml_keeps_only_requested_language(self):
        data = {
            "stages": ["configure", "python", "java", "pipeline-status"],
            "variables": {},
            "include": [],
            "configure_job": {"stage": "configure", "script": ["echo"]},
            "python_job": {"stage": "python", "script": ["echo"]},
            "java_job": {"stage": "java", "script": ["echo"]},
            "status_job": {"stage": "pipeline-status", "script": ["echo"]},
        }
        result = filter_yaml(data, "python")
        assert "java_job" not in result
        assert "python_job" in result
        assert "configure_job" in result
        assert result["stages"] == ["configure", "python", "pipeline-status"]

    def test_external_pipeline_keeps_compute_contract(self) -> None:
        data = yaml.safe_load(Path(".gitlab-ci.yml").read_text())
        _strip_local_includes(data)

        result = filter_yaml(data, "java")

        assert result["stages"] == ["configure", "java", "pipeline-status"]
        assert "java_ssi_pipeline" in result
        assert "nodejs_ssi_pipeline" not in result
        assert result["compute_pipeline"]["image"] == ("registry.ddbuild.io/ci/libdatadog-build/system-tests:146143169")
        assert result["compute_pipeline"]["needs"] == [
            {"job": "resolve_ssi_pr_title", "artifacts": True, "optional": True}
        ]
        compute_script = "\n".join(result["compute_pipeline"]["script"])
        assert "ssi_libraries" in compute_script
        assert "GITHUB_PR_BASE_SHA" in compute_script
        assert "${ssi_libraries+x}" in compute_script
        assert 'git merge-base "$GITHUB_PR_BASE_SHA" "$CI_COMMIT_SHA"' in compute_script

        resolver = result["resolve_ssi_pr_title"]
        assert resolver["image"] == "registry.ddbuild.io/system-tests/ci-runner:9b1520f98ee9"
        assert '$CI_PROJECT_PATH == "DataDog/system-tests"' in resolver["rules"][0]["if"]
        assert '$CI_PIPELINE_SOURCE == "push"' in resolver["rules"][0]["if"]
        assert "$SYSTEM_TESTS_SCENARIOS == null" in resolver["rules"][0]["if"]
        assert "$SYSTEM_TESTS_SCENARIOS_GROUPS == null" in resolver["rules"][0]["if"]

        resolver_script = Path("utils/scripts/ci_orchestrators/resolve_gitlab_pr_title.sh").read_text()
        assert "GITHUB_PR_BASE_SHA" in resolver_script

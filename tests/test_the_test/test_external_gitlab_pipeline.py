"""Tests for utils/scripts/ci_orchestrators/external_gitlab_pipeline.py."""
import yaml
import pytest

from utils import scenarios
from utils.scripts.ci_orchestrators.external_gitlab_pipeline import (
    _is_local_include,
    _strip_local_includes,
    filter_yaml,
    main,
)


@scenarios.test_the_test
class Test_ExternalGitlabPipeline:
    @pytest.mark.parametrize(
        "entry,expected",
        [
            ({"local": "/foo"}, True),
            ("bare-string", True),
            ({"project": "p", "file": "f"}, False),
            ({"remote": "https://example.com/x.yml"}, False),
        ],
    )
    def test_is_local_include(self, entry, expected):
        assert _is_local_include(entry) is expected

    def test_strip_local_includes_removes_only_local(self):
        remote = {"remote": "https://example.com/x.yml"}
        data = {"include": [{"local": "/utils/ci/gitlab/main.yml"}, "bare", remote]}
        _strip_local_includes(data)
        assert data["include"] == [remote]

    def test_main_strips_locals_from_real_repo_yaml(self, capsys):
        main(language=None)
        out = capsys.readouterr().out
        data = yaml.safe_load(out)
        for entry in data.get("include", []):
            if isinstance(entry, dict):
                assert "local" not in entry

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

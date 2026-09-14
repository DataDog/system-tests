"""Structural assertions on generated GitLab pipeline chunk YAML."""

import json
from pathlib import Path

import yaml

from utils import scenarios
from utils.ci.gitlab.build_pipeline import build


MINIMAL_PARAMS = {
    "endtoend_defs": {
        "parallel_weblogs": [{"name": "flask"}],
        "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
    },
    "miscs": {"binaries_artifact": "flask-binaries"},
    "parametric": {"enable": False, "parallel_jobs": []},
}


@scenarios.test_the_test
def test_gitlab_component_allow_failure_input_is_wired() -> None:
    spec, pipeline = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())

    input_definition = spec["spec"]["inputs"]["allow_failure"]
    assert input_definition["type"] == "boolean"
    assert input_definition["default"] is False

    for job_name in (".system_tests_param_base", "system_tests_build_pipeline", ".run_test_pipeline_base"):
        assert pipeline[job_name]["allow_failure"] == "$[[ inputs.allow_failure ]]"


@scenarios.test_the_test
def test_generated_chunk_jobs_have_required_keys(tmp_path: Path):
    (tmp_path / "params_python.json").write_text(json.dumps(MINIMAL_PARAMS))
    out = tmp_path / "out"
    build(["python"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=3)

    for i in range(3):
        chunk = yaml.safe_load((out / f"generated-pipeline-chunk-{i}.yml").read_text())
        for name, job in chunk.items():
            if (
                not isinstance(job, dict)
                or name.startswith(".")
                or name in ("workflow", "stages", "include", "variables", "default")
            ):
                continue
            has_stage = "stage" in job or "extends" in job
            assert has_stage, f"job '{name}' in chunk {i} has no stage or extends"

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
def test_gitlab_parametric_workers_input_is_wired(tmp_path: Path) -> None:
    spec, _ = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())
    assert spec["spec"]["inputs"]["parametric_workers"]["default"] == "auto"

    params = {
        "endtoend_defs": {"parallel_weblogs": [], "parallel_jobs": []},
        "miscs": {"binaries_artifact": ""},
        "parametric": {"enable": True, "job_count": 2, "job_matrix": [1, 2], "workers": "4"},
    }
    (tmp_path / "params_nodejs.json").write_text(json.dumps(params))
    out = tmp_path / "out"
    build(["nodejs"], tmp_path, out, stage="e2e", ci_image="img", chunks=1)

    chunk = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
    parametric_jobs = [
        job
        for name, job in chunk.items()
        if isinstance(job, dict) and name.startswith("system_tests_run_nodejs_PARAMETRIC")
    ]
    assert parametric_jobs
    for job in parametric_jobs:
        assert job["variables"]["PYTEST_XDIST_AUTO_NUM_WORKERS"] == "4"


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

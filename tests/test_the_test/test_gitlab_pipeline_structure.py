"""Structural assertions on generated GitLab pipeline chunk YAML."""

import json
from pathlib import Path

import yaml

from utils import pytest, scenarios
from utils.ci.gitlab.build_pipeline import build, main


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
def test_parametric_jobs_limit_xdist_workers_and_preserve_throughput(tmp_path: Path) -> None:
    spec, _ = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())
    job_count = spec["spec"]["inputs"]["parametric_job_count"]["default"]
    worker_count = spec["spec"]["inputs"]["parametric_workers"]["default"]
    assert job_count == 6
    assert worker_count == 4
    assert job_count * worker_count == 24

    params = {
        "endtoend_defs": {"parallel_weblogs": [], "parallel_jobs": []},
        "miscs": {"binaries_artifact": ""},
        "parametric": {
            "enable": True,
            "job_count": job_count,
            "job_matrix": list(range(1, job_count + 1)),
            "workers": worker_count,
        },
    }
    (tmp_path / "params_python.json").write_text(json.dumps(params))
    out = tmp_path / "out"
    build(["python"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=1)

    pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
    jobs = [pipeline[f"system_tests_run_python_PARAMETRIC_{index}"] for index in range(1, job_count + 1)]
    assert all(job["variables"]["SYSTEM_TESTS_PARAMETRIC_WORKERS"] == str(worker_count) for job in jobs)
    assert [job["variables"]["SYSTEM_TESTS_PARAMETRIC_GROUP"] for job in jobs] == [
        str(index) for index in range(1, job_count + 1)
    ]


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


GOLDEN_DIR = Path("tests/test_the_test/gitlab_pipeline_golden")
# component inputs (arguments) and pipeline variables of each golden case, with the fixed params of GOLDEN_DIR
GOLDEN_CASES: dict[str, tuple[list[str], dict[str, str]]] = {
    "default": (
        [
            "--push-to-test-optimization",
            "true",
            "--force-execute",
            "tests/a.py::Test_A",
            "--pipeline-start-time",
            "1000",
        ],
        {"LIBRARIES": "python php"},
    ),
    "upstream_grouped_split": (
        ["--binaries-artifacts", "build_a;build b", "--binaries-artifact-path", "out/bin", "--split-pipeline", "true"],
        {"LIBRARIES": "python php", "SYSTEM_TESTS_ENDTOEND_JOB_COUNT": "3"},
    ),
}


@scenarios.test_the_test
@pytest.mark.parametrize("case", sorted(GOLDEN_CASES))
@pytest.mark.parametrize("dev_mode", [{}, {"SYSTEM_TESTS_E2E_DEV_MODE": "false"}])
def test_generated_chunks_match_golden_files(tmp_path: Path, case: str, dev_mode: dict[str, str]) -> None:
    """Without dev mode, the generated chunks are byte-identical to the golden files.

    The golden files were generated before the dev mode was added. When the generated pipeline is meant to change,
    regenerate them: run main() with the arguments of GOLDEN_CASES, --stage e2e --ci-image img --ref abc
    --params-dir tests/test_the_test/gitlab_pipeline_golden, and CI_PIPELINE_ID=42 in the environment.
    """
    args, environ = GOLDEN_CASES[case]
    out = tmp_path / case
    argv = ["--stage", "e2e", "--ci-image", "img", "--ref", "abc", "--output-dir", str(out), "--params-dir"]
    assert main([*argv, str(GOLDEN_DIR), *args], environ={"CI_PIPELINE_ID": "42", **environ, **dev_mode}) == 0

    golden = sorted(path.name for path in (GOLDEN_DIR / case).iterdir())
    assert sorted(path.name for path in out.glob("*.yml")) == golden
    for name in golden:
        assert (out / name).read_bytes() == (GOLDEN_DIR / case / name).read_bytes(), name

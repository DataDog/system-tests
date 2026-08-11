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


@scenarios.test_the_test
def test_generated_chunk_preserves_duplicated_job_identity_and_environment(tmp_path: Path):
    params = {
        "endtoend_defs": {
            "parallel_weblogs": [{"name": "spring-boot-jetty"}],
            "parallel_jobs": [
                {
                    "weblog": "spring-boot-jetty",
                    "weblog_instance": 1,
                    "weblog_env": {},
                    "scenarios": ["DEFAULT"],
                    "weblog_build_required": True,
                },
                {
                    "weblog": "spring-boot-jetty",
                    "weblog_instance": "1_v1",
                    "weblog_env": {"DD_TRACE_AGENT_PROTOCOL_VERSION": "1.0"},
                    "scenarios": ["DEFAULT"],
                    "weblog_build_required": True,
                },
            ],
        },
        "miscs": {"binaries_artifact": "java-binaries"},
        "parametric": {"enable": False, "parallel_jobs": []},
    }
    (tmp_path / "params_java.json").write_text(json.dumps(params))
    out = tmp_path / "out"

    build(["java"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=1)

    chunk = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
    original_job = chunk["system_tests_run_java_DEFAULT_spring-boot-jetty"]
    duplicated_job = chunk["system_tests_run_java_DEFAULT_spring-boot-jetty_1_v1"]
    assert json.loads(original_job["variables"]["SYSTEM_TESTS_WEBLOG_ENV"]) == {}
    assert json.loads(duplicated_job["variables"]["SYSTEM_TESTS_WEBLOG_ENV"]) == {
        "DD_TRACE_AGENT_PROTOCOL_VERSION": "1.0"
    }

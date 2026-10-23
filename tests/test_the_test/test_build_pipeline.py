"""Tests for utils/ci/gitlab/build_pipeline.py — chunking, rendering, and CLI."""

import json
import re
from pathlib import Path

from utils import pytest
import yaml

from utils import scenarios
from utils.ci.gitlab.build_pipeline import build, main


MINIMAL_PARAMS = {
    "endtoend_defs": {
        "parallel_weblogs": [{"name": "flask"}],
        "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
    },
    "miscs": {"binaries_artifact": "flask-binaries"},
    "parametric": {"enable": False, "parallel_jobs": []},
}


def write_params(tmp_path: Path, *libs: str) -> None:
    for lib in libs:
        (tmp_path / f"params_{lib}.json").write_text(json.dumps(MINIMAL_PARAMS))


@scenarios.test_the_test
class Test_BuildPipeline:
    @pytest.mark.parametrize(
        "libs",
        [
            [],
            ["a"],
            ["a", "b"],
            ["a", "b", "c"],
            ["a", "b", "c", "d", "e", "f"],
        ],
    )
    def test_chunking_distribution(self, tmp_path: Path, libs: list[str]):
        write_params(tmp_path, *libs)
        out = tmp_path / "out"
        build(libs, tmp_path, out, stage="e2e", ci_image="myimage", chunks=3)

        # Expected round-robin assignment
        expected: dict[int, list[str]] = {i: [] for i in range(3)}
        for idx, lib in enumerate(libs):
            expected[idx % 3].append(lib)

        for i in range(3):
            chunk = yaml.safe_load((out / f"generated-pipeline-chunk-{i}.yml").read_text())
            if not expected[i]:
                assert "noop" in chunk, f"chunk {i} should be noop"
            else:
                jobs = {k: v for k, v in chunk.items() if isinstance(v, dict) and ("extends" in v or "script" in v)}
                assert jobs, f"chunk {i} should have jobs for {expected[i]}"

    def test_missing_params_exits_nonzero(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "--stage",
                    "e2e",
                    "--libraries",
                    "python",
                    "--params-dir",
                    str(tmp_path),
                    "--ci-image",
                    "x",
                    "--output-dir",
                    str(tmp_path / "out"),
                    "--chunks",
                    "3",
                ]
            )
        assert exc.value.code != 0

    def test_concatenation_no_duplicate_top_level_keys(self, tmp_path: Path):
        """Two libs in same chunk (chunks=1) must not produce duplicate top-level YAML keys."""
        write_params(tmp_path, "python", "java")
        out = tmp_path / "out"
        build(["python", "java"], tmp_path, out, stage="e2e", ci_image="img", chunks=1)
        text = (out / "generated-pipeline-chunk-0.yml").read_text()
        for key in ("workflow:", "stages:", "include:"):
            count = len(re.findall(rf"^{re.escape(key)}", text, re.MULTILINE))
            assert count <= 1, f"duplicate top-level key '{key}' found {count} times"

    def test_c_pipeline_renders_three_scenarios_and_package_artifact(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [{"name": "perl-mojolicious"}],
                "parallel_jobs": [
                    {
                        "weblog": "perl-mojolicious",
                        "scenarios": ["DEFAULT", "SAMPLING", "IPV6"],
                        "weblog_build_required": True,
                    }
                ],
            },
            "miscs": {"binaries_artifact": ""},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_c.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(
            ["c"],
            tmp_path,
            out,
            stage="e2e",
            ci_image="myimage",
            chunks=1,
            binaries_artifacts="system_tests_package_refs",
            binaries_artifact_path="system-tests-binaries",
        )

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        expected_run_jobs = {
            f"system_tests_run_c_{scenario}_perl-mojolicious" for scenario in ("DEFAULT", "SAMPLING", "IPV6")
        }
        assert expected_run_jobs <= pipeline.keys()

        build_job = pipeline["system_tests_build_c_perl-mojolicious"]
        assert build_job["extends"] == ".system_tests_build"
        assert build_job["needs"] == [
            {
                "job": "system_tests_package_refs",
                "artifacts": True,
                "pipeline": "$UPSTREAM_PIPELINE_ID",
            }
        ]
        assert build_job["variables"] == {
            "TEST_LIBRARY": "c",
            "WEBLOG_VARIANT": "perl-mojolicious",
            "SYSTEM_TESTS_WEBLOG": "perl-mojolicious",
            "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH": "system-tests-binaries",
        }

        for job_name in expected_run_jobs:
            run_job = pipeline[job_name]
            assert run_job["extends"] == [".system_tests_run"]
            # binaries come from the build job, not from upstream
            assert run_job["needs"] == [{"job": "system_tests_build_c_perl-mojolicious", "artifacts": True}]
            assert run_job["variables"]["SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED"] == "true"
            assert "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH" not in run_job["variables"]

    def test_run_job_without_build_uses_upstream_binaries(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [],
                "parallel_jobs": [
                    {"weblog": "envoy", "scenarios": ["GO_PROXIES_DEFAULT"], "weblog_build_required": False}
                ],
            },
            "miscs": {"binaries_artifact": "envoy-binaries"},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_golang.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(
            ["golang"],
            tmp_path,
            out,
            stage="e2e",
            ci_image="myimage",
            chunks=1,
            push_to_test_optimization=True,
            binaries_artifact_path="bin",
        )

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert pipeline["system_tests_run_golang_GO_PROXIES_DEFAULT_envoy"] == {
            "extends": [".system_tests_run", ".push_to_test_optimization"],
            "variables": {
                "TEST_LIBRARY": "golang",
                "WEBLOG_VARIANT": "envoy",
                "SYSTEM_TESTS_WEBLOG": "envoy",
                "SYSTEM_TESTS_SCENARIO": "GO_PROXIES_DEFAULT",
                "SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED": "false",
                "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH": "bin",
            },
            "needs": [{"job": "envoy-binaries", "artifacts": True, "pipeline": "$UPSTREAM_PIPELINE_ID"}],
        }

    def test_header_includes_static_files_and_pipeline_variables(self, tmp_path: Path) -> None:
        write_params(tmp_path, "python")
        out = tmp_path / "out"
        build(
            ["python"],
            tmp_path,
            out,
            stage="e2e",
            ci_image="img",
            ref="my-ref",
            chunks=1,
            pipeline_start_time="1700000000",
        )

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert [include["file"] for include in pipeline["include"]] == [
            "utils/ci/gitlab/templates.yml",
            "utils/ci/gitlab/child-pipeline.yml",
        ]
        assert all(include["ref"] == "my-ref" for include in pipeline["include"])
        assert pipeline["variables"] == {
            "CI_IMAGE": "img",
            "SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME": "1700000000",
        }

    def test_generated_jobs_extend_hidden_jobs_of_child_pipeline(self, tmp_path: Path) -> None:
        params = dict(MINIMAL_PARAMS)
        params["parametric"] = {"enable": True, "job_count": 1, "job_matrix": [1], "workers": 2}
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        out = tmp_path / "out"
        build(["python"], tmp_path, out, stage="e2e", ci_image="img", chunks=1, push_to_test_optimization=True)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        child = yaml.safe_load(Path("utils/ci/gitlab/child-pipeline.yml").read_text())
        templates = list(yaml.safe_load_all(Path("utils/ci/gitlab/templates.yml").read_text()))[-1]
        for name, job in pipeline.items():
            if name in ("workflow", "include", "stages", "variables"):
                continue
            extends = job["extends"] if isinstance(job["extends"], list) else [job["extends"]]
            for parent in extends:
                assert parent in child, f"{name} extends unknown job {parent}"
                assert child[parent].get("extends", ".system_tests_base") in child.keys() | templates.keys()

    def test_thread_context_sharing_runs_on_cws_runner(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [{"name": "flask"}],
                "parallel_jobs": [
                    {
                        "weblog": "flask",
                        "scenarios": ["DEFAULT", "THREAD_CONTEXT_SHARING"],
                        "weblog_build_required": True,
                    }
                ],
            },
            "miscs": {"binaries_artifact": ""},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(["python"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=1)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert pipeline["system_tests_run_python_THREAD_CONTEXT_SHARING_flask"]["tags"] == [
            "docker-in-docker:amd64-cws"
        ]
        # other jobs keep the default runner, from .system_tests_base
        assert "tags" not in pipeline["system_tests_run_python_DEFAULT_flask"]
        assert "tags" not in pipeline["system_tests_build_python_flask"]

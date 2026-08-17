"""Tests for utils/ci/gitlab/build_pipeline.py — chunking, rendering, and CLI."""

import json
import re
from pathlib import Path

import pytest
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
        assert build_job["extends"] == ".system_tests_base"
        assert build_job["needs"] == [
            {
                "job": "system_tests_package_refs",
                "artifacts": True,
                "pipeline": "$UPSTREAM_PIPELINE_ID",
            }
        ]
        assert any("system-tests-binaries/." in command for command in build_job["script"])

        for job_name in expected_run_jobs:
            assert ".system_tests_base" in pipeline[job_name]["extends"]

    def test_build_job_stages_target_artifacts_without_upstream_bundle(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [{"name": "flask"}],
                "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
            },
            "miscs": {"binaries_artifact": "", "ci_environment": "prod"},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(["python"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=1)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        build_script = pipeline["system_tests_build_python_flask"]["script"]
        assert "python3 utils/scripts/stage-target-artifacts.py python prod" in build_script
        assert not any(job_name.startswith("system_tests_stage") for job_name in pipeline)

    def test_parametric_job_stages_target_artifacts_without_upstream_bundle(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {"parallel_weblogs": [], "parallel_jobs": []},
            "miscs": {"binaries_artifact": "", "ci_environment": "dev"},
            "parametric": {"enable": True, "job_count": 1, "job_matrix": [1]},
        }
        (tmp_path / "params_nodejs.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(["nodejs"], tmp_path, out, stage="e2e", ci_image="myimage", chunks=1)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        run_script = pipeline["system_tests_run_nodejs_PARAMETRIC_1"]["script"]
        assert "python3 utils/scripts/stage-target-artifacts.py nodejs dev" in run_script

    def test_upstream_artifact_bundle_skips_target_artifact_staging(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [{"name": "flask"}],
                "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
            },
            "miscs": {"binaries_artifact": "", "ci_environment": "custom"},
            "parametric": {"enable": True, "job_count": 1, "job_matrix": [1]},
        }
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(
            ["python"],
            tmp_path,
            out,
            stage="e2e",
            ci_image="myimage",
            chunks=1,
            binaries_artifacts="upstream-binaries",
            binaries_artifact_path="system-tests-binaries",
        )

        text = (out / "generated-pipeline-chunk-0.yml").read_text()
        assert "stage-target-artifacts.py" not in text

    def test_buildx_cache_updates_system_tests_main(self, tmp_path: Path) -> None:
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
            ref="main",
            ci_project_name="system-tests",
            ci_commit_branch="main",
            ci_default_branch="main",
        )

        text = (out / "generated-pipeline-chunk-0.yml").read_text()
        assert (
            "--cache-to=type=registry,ref=registry.ddbuild.io/system-tests/cache/c/perl-mojolicious:main,mode=max"
            in text
        )
        assert (
            "--cache-to=type=registry,ref=registry.ddbuild.io/system-tests/cache/c/perl-mojolicious:lib_main,mode=max"
            not in text
        )

    def test_buildx_cache_updates_library_default_branch(self, tmp_path: Path) -> None:
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
            ref="main",
            ci_project_name="dd-trace-rb",
            ci_commit_branch="master",
            ci_default_branch="master",
        )

        text = (out / "generated-pipeline-chunk-0.yml").read_text()
        assert (
            "--cache-to=type=registry,ref=registry.ddbuild.io/system-tests/cache/c/perl-mojolicious:lib_main,mode=max"
            in text
        )
        assert (
            "--cache-to=type=registry,ref=registry.ddbuild.io/system-tests/cache/c/perl-mojolicious:main,mode=max"
            not in text
        )

    def test_buildx_cache_does_not_update_from_not_main(self, tmp_path: Path) -> None:
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
            ref="some-branch",
            ci_project_name="system-tests",
            ci_commit_branch="some-branch",
            ci_default_branch="main",
        )

        assert not re.search("--cache-to=type=registry,ref=", (out / "generated-pipeline-chunk-0.yml").read_text())

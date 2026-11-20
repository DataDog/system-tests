"""Tests for the dev mode of the GitLab end-to-end pipeline (build_pipeline.py, SYSTEM_TESTS_E2E_DEV_MODE)."""

import json
from pathlib import Path

import yaml

from utils import pytest, scenarios
from utils.ci.gitlab import build_pipeline
from utils.ci.gitlab.build_pipeline import (
    DEV_BINARIES_PATH,
    DEV_MODE_LIBRARIES,
    DEV_MODE_UNSUPPORTED_LIBRARIES,
    build,
    main,
)
from utils.ci.gitlab.jobs import load_dev_binaries
from utils.const import COMPONENT_GROUPS


def _params(library_weblogs: dict[str, str], *, parametric: bool = True) -> dict:
    """Params with a prebuilt weblog (build_mode: prebuild, in parallel_weblogs) and a local one, per weblog name."""
    return {
        "endtoend_defs": {
            "parallel_weblogs": [{"name": weblog} for weblog, mode in library_weblogs.items() if mode == "prebuild"],
            "parallel_jobs": [
                {"weblog": weblog, "scenarios": ["DEFAULT"], "weblog_build_required": True}
                for weblog in library_weblogs
            ],
        },
        "miscs": {"binaries_artifact": ""},
        "parametric": {"enable": parametric, "job_count": 2, "job_matrix": [1, 2], "workers": 4},
    }


def _build(tmp_path: Path, library: str, *, target_branches: dict[str, str] | None) -> dict:
    (tmp_path / f"params_{library}.json").write_text(json.dumps(_params({"flask": "prebuild", "uwsgi": "local"})))
    out = tmp_path / "out"
    build([library], tmp_path, out, stage="e2e", ci_image="img", chunks=1, target_branches=target_branches)
    return yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())


def _main(tmp_path: Path, *args: str, environ: dict[str, str]) -> int:
    return main(
        ["--stage", "e2e", "--ci-image", "img", "--output-dir", str(tmp_path / "out"), "--parametric-job-count", "2"]
        + list(args),
        environ={"CI_PIPELINE_ID": "42", **environ},
    )


def _main_with_params(tmp_path: Path, environ: dict[str, str], library: str = "python") -> int:
    """main() with pre-computed params: only the checks and the generation are tested."""
    (tmp_path / f"params_{library}.json").write_text(json.dumps(_params({"flask": "prebuild"})))
    return _main(tmp_path, "--params-dir", str(tmp_path), environ={"LIBRARIES": library, **environ})


def _chunk(tmp_path: Path) -> dict:
    return yaml.safe_load((tmp_path / "out" / "generated-pipeline-chunk-0.yml").read_text())


@scenarios.test_the_test
class Test_GitlabDevMode:
    def test_off_by_default(self, tmp_path: Path) -> None:
        """Without dev mode: no dev binaries job, no dev mode variable, no needs (no upstream binaries)."""
        assert _main_with_params(tmp_path, {}) == 0
        pipeline = _chunk(tmp_path)

        assert not [name for name in pipeline if "dev" in name]
        assert "SYSTEM_TESTS_DEV_MODE" not in pipeline["variables"]
        assert "SYSTEM_TESTS_REPORT_ENVIRONMENT" not in pipeline["variables"]
        assert "needs" not in pipeline["system_tests_build_python_flask"]

    @pytest.mark.parametrize("value", ["false", "False", ""])
    def test_off_values(self, tmp_path: Path, value: str) -> None:
        assert _main_with_params(tmp_path, {"SYSTEM_TESTS_E2E_DEV_MODE": value}) == 0
        assert "system_tests_dev_binaries_python" not in _chunk(tmp_path)

    def test_dev_binaries_job_feeds_all_jobs_of_the_library(self, tmp_path: Path) -> None:
        pipeline = _build(tmp_path, "python", target_branches={})
        dev_job = "system_tests_dev_binaries_python"
        dev_needs = [{"job": dev_job, "artifacts": True}]

        # once per library, listed first, without needs (same pipeline, nothing upstream)
        assert next(name for name in pipeline if name.startswith("system_tests_")) == dev_job
        assert pipeline[dev_job] == {
            "extends": ".system_tests_dev_binaries",
            "variables": {"TEST_LIBRARY": "python"},
        }
        # jobs downloading the dev binaries copy them into binaries/: build jobs, run jobs of local weblogs and
        # parametric jobs. Run jobs of prebuilt weblogs get them from the artifacts of their build job
        for name in (
            "system_tests_build_python_flask",
            "system_tests_run_python_DEFAULT_uwsgi",
            "system_tests_run_python_PARAMETRIC_1",
            "system_tests_run_python_PARAMETRIC_2",
        ):
            assert pipeline[name]["needs"] == dev_needs, name
            assert pipeline[name]["variables"]["SYSTEM_TESTS_BINARIES_ARTIFACT_PATH"] == DEV_BINARIES_PATH, name
        run_prebuilt = pipeline["system_tests_run_python_DEFAULT_flask"]
        assert run_prebuilt["needs"] == [{"job": "system_tests_build_python_flask", "artifacts": True}]
        assert "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH" not in run_prebuilt["variables"]
        # no cross-pipeline needs: there is no upstream job
        assert not [job for job in pipeline.values() if isinstance(job, dict) and "pipeline" in str(job.get("needs"))]

    def test_no_dev_binaries_job_without_other_jobs(self, tmp_path: Path) -> None:
        params = _params({}, parametric=False)
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        build(["python"], tmp_path, tmp_path / "out", stage="e2e", ci_image="img", chunks=1, target_branches={})
        assert "system_tests_dev_binaries_python" not in _chunk(tmp_path)

    def test_dev_mode_variables(self, tmp_path: Path) -> None:
        """Run jobs get SYSTEM_TESTS_DEV_MODE (read by conftest.py), like the GitHub workflows."""
        assert _main_with_params(tmp_path, {"SYSTEM_TESTS_E2E_DEV_MODE": "true"}) == 0
        pipeline = _chunk(tmp_path)

        assert pipeline["variables"]["SYSTEM_TESTS_DEV_MODE"] == "true"
        assert pipeline["variables"]["SYSTEM_TESTS_REPORT_ENVIRONMENT"] == "dev"
        assert pipeline["system_tests_build_python_flask"]["needs"] == [
            {"job": "system_tests_dev_binaries_python", "artifacts": True}
        ]

    def test_target_branch_map(self, tmp_path: Path) -> None:
        environ = {
            "SYSTEM_TESTS_E2E_DEV_MODE": "true",
            # the branches of other libraries are ignored, like in the GitHub workflows
            "SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"python": "user/my-branch", "agent": "7.70.x", "java": "other"}',
        }
        assert _main_with_params(tmp_path, environ) == 0

        assert _chunk(tmp_path)["system_tests_dev_binaries_python"]["variables"] == {
            "TEST_LIBRARY": "python",
            "LIBRARY_TARGET_BRANCH": "user/my-branch",
            "AGENT_TARGET_BRANCH": "7.70.x",
        }

    def test_github_token_only_where_needed(self, tmp_path: Path) -> None:
        assert _main_with_params(tmp_path, {"SYSTEM_TESTS_E2E_DEV_MODE": "true"}, library="golang") == 0

        variables = _chunk(tmp_path)["system_tests_dev_binaries_golang"]["variables"]
        assert variables["SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN"] == "true"

    @pytest.mark.parametrize(
        ("environ", "error"),
        [
            ({"BINARIES_ARTIFACTS": "build_python"}, "can't be used with binaries_artifacts"),
            ({"BINARIES_ARTIFACT_PATH": "out"}, "can't be used with binaries_artifacts"),
            ({"LIBRARIES": "cpp_nginx"}, "cpp_nginx: load-binary.sh downloads GitHub Actions artifacts"),
            ({"LIBRARIES": "python_otel"}, "python_otel: no dev version"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": "{"}, "invalid JSON"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '["python"]'}, "expected a JSON object"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"pyhton": "x"}'}, "unknown library 'pyhton'"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"python": "$CI_JOB_TOKEN"}'}, "invalid branch"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"python": 1}'}, "invalid branch"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"c": "x"}'}, "c can't have a target branch"),
            ({"SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"auto_inject": "x"}'}, "auto_inject can't have"),
        ],
    )
    def test_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], environ: dict[str, str], error: str
    ) -> None:
        environ = {"LIBRARIES": "python", "SYSTEM_TESTS_E2E_DEV_MODE": "true", **environ}
        assert _main(tmp_path, environ=environ) == 1
        assert error in capsys.readouterr().err
        assert not (tmp_path / "out" / "generated-pipeline-chunk-0.yml").exists()

    def test_target_branch_map_needs_dev_mode(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        environ = {"LIBRARIES": "python", "SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP": '{"python": "x"}'}
        assert _main(tmp_path, environ=environ) == 1
        assert "target_branch_map can only be used in dev mode" in capsys.readouterr().err

    def test_compute_workflow_parameters_in_dev_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """compute-workflow-parameters.py gets --system-tests-dev-mode in dev mode only, nothing else changes."""
        commands: list[list[str]] = []

        class _Result:
            returncode = 0

        def record(command: list[str], **_: object) -> _Result:
            commands.append(command)
            Path(command[command.index("--output") + 1]).write_text(json.dumps(_params({"flask": "prebuild"})))
            return _Result()

        monkeypatch.setattr(build_pipeline.subprocess, "run", record)
        for dev_mode in ("false", "true"):
            environ = {"LIBRARIES": "python", "SYSTEM_TESTS_E2E_DEV_MODE": dev_mode}
            assert _main(tmp_path / dev_mode, environ=environ) == 0

        # the output folder is the only other difference
        default, dev = ([arg for arg in command if not arg.startswith(str(tmp_path))] for command in commands)
        assert "--system-tests-dev-mode" not in default
        assert [arg for arg in dev if arg not in ("--system-tests-dev-mode", "true")] == default
        assert dev[dev.index("--system-tests-dev-mode") + 1] == "true"

    def test_weblogs_of_the_dev_environment(self, tmp_path: Path) -> None:
        """With the real compute-workflow-parameters.py: the dev mode gets the weblogs of the dev environment."""
        mapping = '{"golang": {"net-http-span-pool": ["DEFAULT"]}}'
        for dev_mode in ("false", "true"):
            out = tmp_path / dev_mode
            assert (
                _main(out, "--library-weblog-scenarios", mapping, environ={"SYSTEM_TESTS_E2E_DEV_MODE": dev_mode}) == 0
            )
            jobs = {name for name in _chunk(out) if name.startswith("system_tests_")}
            if dev_mode == "true":
                assert jobs == {
                    "system_tests_dev_binaries_golang",
                    "system_tests_build_golang_net-http-span-pool",
                    "system_tests_run_golang_DEFAULT_net-http-span-pool",
                }
            else:
                # its tracer support is not released yet: not run in prod
                assert jobs == set()

    def test_dev_mode_libraries_are_up_to_date(self) -> None:
        """Each library is either supported in dev mode, or has a reason not to be."""
        assert set(DEV_MODE_LIBRARIES) | set(DEV_MODE_UNSUPPORTED_LIBRARIES) == set(COMPONENT_GROUPS.all)
        assert not set(DEV_MODE_LIBRARIES) & set(DEV_MODE_UNSUPPORTED_LIBRARIES)

    def test_dev_binaries_hidden_job(self) -> None:
        child_pipeline = yaml.safe_load(Path("utils/ci/gitlab/child-pipeline.yml").read_text())
        job = child_pipeline[".system_tests_dev_binaries"]

        assert job["extends"] == ".system_tests_base"
        assert job["script"] == ["python utils/ci/gitlab/run_job.py load_dev_binaries"]
        # the path the job script writes to, and the one the other jobs copy the binaries from
        assert job["artifacts"]["paths"] == [f"{DEV_BINARIES_PATH}/"]
        assert load_dev_binaries.ARTIFACT_PATH == DEV_BINARIES_PATH
        assert job["id_tokens"]["DDOCTOSTS_ID_TOKEN"] == {"aud": "dd-octo-sts"}
        # the job can't hang longer than all its attempts
        assert int(job["timeout"].split()[0]) * 60 > load_dev_binaries.LOAD_ATTEMPTS * (
            load_dev_binaries.LOAD_TIMEOUT_SECONDS + load_dev_binaries.RETRY_DELAY_SECONDS * 2
        )

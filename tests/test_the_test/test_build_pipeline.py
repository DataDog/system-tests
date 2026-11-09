"""Tests for utils/ci/gitlab/build_pipeline.py — chunking, rendering, and CLI."""

import copy
import json
import re
from pathlib import Path

from utils import pytest
import yaml

from utils import scenarios
from utils.ci.gitlab import build_pipeline
from utils.ci.gitlab.build_pipeline import build, main, parse_args, resolve_inputs


MINIMAL_PARAMS = {
    "endtoend_defs": {
        "parallel_weblogs": [{"name": "flask"}],
        "parallel_jobs": [{"weblog": "flask", "scenarios": ["DEFAULT"], "weblog_build_required": True}],
    },
    "miscs": {"binaries_artifact": "flask-binaries"},
    "parametric": {"enable": False, "parallel_jobs": []},
}


def _timed_params(weblog: str, times: dict[str, int]) -> dict:
    """Params with one end-to-end job for the weblog, with the time of each scenario, like compute_params() writes."""
    return {
        "endtoend_defs": {
            "parallel_weblogs": [{"name": weblog}],
            "parallel_jobs": [
                {
                    "weblog": weblog,
                    "weblog_instance": 1,
                    "scenarios": sorted(times),
                    "scenarios_times": times,
                    "expected_job_time": sum(times.values()),
                    "weblog_build_required": True,
                }
            ],
        },
        "miscs": {"binaries_artifact": ""},
        "parametric": {"enable": False, "parallel_jobs": []},
    }


def _jobs(params: dict) -> list[tuple[str, int, list[str]]]:
    return [
        (job["weblog"], job["weblog_instance"], job["scenarios"]) for job in params["endtoend_defs"]["parallel_jobs"]
    ]


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
                ],
                environ={},
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
                "SYSTEM_TESTS_WEBLOG": "envoy",
                "SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED": "false",
                "SYSTEM_TESTS_BINARIES_ARTIFACT_PATH": "bin",
                "SYSTEM_TESTS_SCENARIOS": "GO_PROXIES_DEFAULT",
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
            pipeline_variables={"SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME": "1700000000"},
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

    def test_scenarios_are_not_grouped_by_default(self, tmp_path: Path) -> None:
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [],
                "parallel_jobs": [
                    {"weblog": "flask", "scenarios": ["DEFAULT", "SAMPLING"], "weblog_build_required": True}
                ],
            },
            "miscs": {"binaries_artifact": ""},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_python.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(["python"], tmp_path, out, stage="e2e", ci_image="img", chunks=1)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert pipeline["system_tests_run_python_DEFAULT_flask"]["variables"]["SYSTEM_TESTS_SCENARIOS"] == "DEFAULT"
        assert pipeline["system_tests_run_python_SAMPLING_flask"]["variables"]["SYSTEM_TESTS_SCENARIOS"] == "SAMPLING"

    def test_scheduler_balances_scenarios_of_all_libraries(self, tmp_path: Path) -> None:
        python_times = {"DEFAULT": 400, "SAMPLING": 300, "IPV6": 200, "PROFILING": 100, "THREAD_CONTEXT_SHARING": 50}
        (tmp_path / "params_python.json").write_text(json.dumps(_timed_params("flask", python_times)))
        (tmp_path / "params_java.json").write_text(
            json.dumps(_timed_params("spring-boot", {"DEFAULT": 500, "IPV6": 100}))
        )
        out = tmp_path / "out"

        build(["python", "java"], tmp_path, out, stage="e2e", ci_image="img", chunks=1, endtoend_job_count=5)

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        run_jobs = [
            (name, job["variables"]["SYSTEM_TESTS_SCENARIOS"])
            for name, job in pipeline.items()
            if name.startswith("system_tests_run_")
        ]
        # 1 job per weblog. The 3rd one goes to flask, which has the longest job (1050s, split into 500s+550s), the
        # 4th one to spring-boot (600s, split into 500s+100s), the 5th one to flask again (400s+350s+300s).
        # Jobs of a weblog are ordered by expected time, longest first, then by scenarios
        assert run_jobs == [
            ("system_tests_run_python_DEFAULT_flask", "DEFAULT"),
            ("system_tests_run_python_flask_2", "SAMPLING,THREAD_CONTEXT_SHARING"),
            ("system_tests_run_python_flask_3", "IPV6,PROFILING"),
            ("system_tests_run_java_DEFAULT_spring-boot", "DEFAULT"),
            ("system_tests_run_java_IPV6_spring-boot", "IPV6"),
        ]
        # the CWS runners can run the other scenarios too
        assert pipeline["system_tests_run_python_flask_2"]["tags"] == ["docker-in-docker:amd64-cws"]
        assert "tags" not in pipeline["system_tests_run_python_flask_3"]
        # twice the expected time, plus 5 minutes
        assert pipeline["system_tests_run_python_flask_2"]["timeout"] == "17 minutes"
        assert "timeout" not in pipeline["system_tests_run_java_DEFAULT_spring-boot"]

    def test_scheduler_is_deterministic(self) -> None:
        """Ties are broken by the order of the params, then by scenario names."""
        times = {"A": 100, "B": 100, "C": 100, "D": 100}
        all_params = {
            "python": _timed_params("flask", times),
            "java": _timed_params("spring-boot", times),
        }

        build_pipeline.EndToEndScheduler(all_params).schedule(job_count=3)

        assert [_jobs(params) for params in all_params.values()] == [
            # first weblog with the longest job: it gets the 3rd job
            [("flask", 1, ["A", "C"]), ("flask", 2, ["B", "D"])],
            [("spring-boot", 1, ["A", "B", "C", "D"])],
        ]

    def test_scheduler_does_not_add_useless_jobs(self) -> None:
        """Another job is only added if it may make the longest job shorter, and never more jobs than scenarios."""
        all_params: dict[str, dict] = {
            "python": {
                "endtoend_defs": {
                    "parallel_jobs": [
                        {
                            "weblog": "flask",
                            "scenarios": ["DEFAULT", "IPV6", "SAMPLING"],
                            "scenarios_times": {"DEFAULT": 1000, "IPV6": 100, "SAMPLING": 100},
                        },
                        {"weblog": "django", "scenarios": ["DEFAULT", "IPV6"], "expected_job_time": 100},
                    ]
                }
            }
        }

        build_pipeline.EndToEndScheduler(all_params).schedule(job_count=100)

        jobs = all_params["python"]["endtoend_defs"]["parallel_jobs"]
        # without scenarios times, the expected time of the job is shared between its scenarios
        assert [
            (job["weblog"], job["weblog_instance"], job["scenarios"], job["expected_job_time"]) for job in jobs
        ] == [
            ("flask", 1, ["DEFAULT"], 1000),
            ("flask", 2, ["IPV6", "SAMPLING"], 200),
            ("django", 1, ["DEFAULT"], 50),
            ("django", 2, ["IPV6"], 50),
        ]
        assert all("scenarios_times" not in job for job in jobs)

    def test_runner_tags_follow_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build_pipeline, "SCENARIO_RUNNER_TAGS", {"B": ["runner-b"], "A": ["runner-a"]})

        # the tags of the first entry win, whatever the order of the scenarios
        assert build_pipeline._runner_tags(["A", "B", "C"]) == ["runner-b"]  # noqa: SLF001
        assert build_pipeline._runner_tags(["A", "C"]) == ["runner-a"]  # noqa: SLF001
        assert build_pipeline._runner_tags(["C"]) is None  # noqa: SLF001

    def test_scheduler_uses_at_least_one_job_per_weblog(self) -> None:
        all_params = {lib: _timed_params("w", {"DEFAULT": 100, "IPV6": 100}) for lib in ("python", "java")}

        build_pipeline.EndToEndScheduler(all_params).schedule(job_count=1)

        # scenarios of different weblogs can't share a job
        assert [_jobs(params) for params in all_params.values()] == [
            [("w", 1, ["DEFAULT", "IPV6"])],
            [("w", 1, ["DEFAULT", "IPV6"])],
        ]

    @pytest.mark.parametrize(
        ("desired_execution_time", "expected_job_count"),
        [
            (10000, 2),  # one job per weblog
            (600, 3),  # flask (1000s) is split into 2 jobs of 500s
            (500, 4),  # spring-boot (600s) too: 500s + 100s
            (400, 5),  # flask into 3 jobs: 400s (DEFAULT) + 300s + 300s
            (1, 5),  # DEFAULT alone is the longest job of flask and spring-boot: they can't be shortened
        ],
    )
    def test_scheduler_with_max_job_time(
        self, tmp_path: Path, desired_execution_time: int, expected_job_count: int
    ) -> None:
        python_times = {"DEFAULT": 400, "SAMPLING": 300, "IPV6": 200, "PROFILING": 100}
        all_params = {
            "python": _timed_params("flask", python_times),
            "java": _timed_params("spring-boot", {"DEFAULT": 500, "IPV6": 100}),
        }
        for library, params in all_params.items():
            (tmp_path / f"params_{library}.json").write_text(json.dumps(params))

        job_count = build_pipeline.EndToEndScheduler(copy.deepcopy(all_params)).schedule(
            max_job_time=desired_execution_time
        )
        assert job_count == expected_job_count

        # both stop the same sequence of steps: same result as with the job count it ends with
        build(
            ["python", "java"],
            tmp_path,
            tmp_path / "sized",
            stage="e2e",
            ci_image="img",
            chunks=1,
            desired_execution_time=desired_execution_time,
        )
        build(
            ["python", "java"],
            tmp_path,
            tmp_path / "counted",
            stage="e2e",
            ci_image="img",
            chunks=1,
            endtoend_job_count=job_count,
        )
        sized = (tmp_path / "sized" / "generated-pipeline-chunk-0.yml").read_text()
        assert sized == (tmp_path / "counted" / "generated-pipeline-chunk-0.yml").read_text()
        run_jobs = [name for name in yaml.safe_load(sized) if name.startswith("system_tests_run_")]
        assert len(run_jobs) == expected_job_count

    @pytest.mark.parametrize(
        ("arguments", "environ", "expected"),
        [
            ([], {}, {"endtoend_job_count": 0, "desired_execution_time": -1}),
            (["--desired-execution-time", "900"], {}, {"endtoend_job_count": 0, "desired_execution_time": 900}),
            (
                ["--desired-execution-time", "-1"],
                {"SYSTEM_TESTS_DESIRED_EXECUTION_TIME": "600"},
                {"endtoend_job_count": 0, "desired_execution_time": 600},
            ),
            (["--endtoend-job-count", "20"], {}, {"endtoend_job_count": 20, "desired_execution_time": -1}),
            (
                ["--endtoend-job-count", "20"],
                {"SYSTEM_TESTS_ENDTOEND_JOB_COUNT": "0"},
                {"endtoend_job_count": 0, "desired_execution_time": -1},
            ),
        ],
    )
    def test_job_count_inputs_are_passed_to_build(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        arguments: list[str],
        environ: dict[str, str],
        expected: dict[str, int],
    ) -> None:
        computed: list[list[str]] = []

        def fake_compute(command: list[str], *, check: bool) -> object:  # noqa: ARG001
            computed.append(command)
            Path(command[command.index("--output") + 1]).write_text(json.dumps(MINIMAL_PARAMS))
            return type("Result", (), {"returncode": 0})()

        monkeypatch.setattr(build_pipeline.subprocess, "run", fake_compute)
        built: list[dict] = []
        monkeypatch.setattr(build_pipeline, "build", lambda **kwargs: built.append(kwargs))

        main(
            [
                *("--stage", "e2e", "--ci-image", "img", "--output-dir", str(tmp_path), "--libraries", "python"),
                *arguments,
            ],
            environ=environ,
        )

        # params always have one job per weblog, with the time of each scenario: build() splits them into run jobs
        assert "--include-scenarios-times" in computed[0]
        assert "--desired-execution-time" not in computed[0]
        assert {name: built[0][name] for name in expected} == expected

    @pytest.mark.parametrize("name", ["desired-execution-time", "endtoend-job-count"])
    def test_decimal_job_count_inputs_are_rejected(
        self, tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = main(
            [
                *("--stage", "e2e", "--ci-image", "img", "--output-dir", str(tmp_path), "--libraries", "python"),
                *(f"--{name}", "900.5"),
            ],
            environ={},
        )
        assert result == 1
        assert f"{name.replace('-', '_')}: expected an integer, got '900.5'" in capsys.readouterr().err

    def test_endtoend_job_count_and_desired_execution_time_are_exclusive(self, tmp_path: Path) -> None:
        result = main(
            [
                *("--stage", "e2e", "--ci-image", "img", "--output-dir", str(tmp_path), "--libraries", "python"),
                *("--desired-execution-time", "900", "--endtoend-job-count", "20"),
            ],
            environ={},
        )
        assert result == 1

    def test_inputs_are_merged_with_pipeline_variables(self) -> None:
        args = parse_args(
            [
                *("--stage", "e2e", "--ci-image", "img", "--output-dir", "out"),
                *("--libraries", "python, java", "--scenarios", "DEFAULT", "--weblogs", "flask"),
                *("--excluded-scenarios", "OTEL_LOG_E2E,INTEGRATION_FRAMEWORKS"),
                *("--force-execute", "tests/a.py::Test_A[with space]"),
                *("--parametric-job-count", "6", "--parametric-workers", "4"),
                *("--push-to-test-optimization", "false", "--split-pipeline", "false"),
            ]
        )
        inputs = resolve_inputs(
            args,
            {
                "LIBRARIES": "java golang",
                "SCENARIOS": "SAMPLING,DEFAULT",
                "EXCLUDED_SCENARIOS": "APPSEC_BLOCKING,OTEL_LOG_E2E",
                "FORCE_EXECUTE": "tests/b.py::Test_B",
                "SYSTEM_TESTS_PARAMETRIC_JOB_COUNT": "2",
                "SYSTEM_TESTS_PUSH_TO_TEST_OPTIMIZATION": "true",
                "SYSTEM_TESTS_SPLIT_PIPELINE": "true",
                "SYSTEM_TESTS_PIPELINE_START_TIME": "1700000000",
            },
        )

        # lists are merged with the inputs, without duplicates
        assert inputs.libraries == ["python", "java", "golang"]
        assert inputs.scenarios == ["DEFAULT", "SAMPLING"]
        assert inputs.weblogs == ["flask"]
        assert inputs.excluded_scenarios == ["APPSEC_BLOCKING", "INTEGRATION_FRAMEWORKS", "OTEL_LOG_E2E"]
        # only libraries are split on spaces, node IDs may contain some
        assert inputs.force_execute == ["tests/a.py::Test_A[with space]", "tests/b.py::Test_B"]
        # scalars are replaced
        assert inputs.parametric_job_count == 2
        assert inputs.parametric_workers == 4
        assert inputs.push_to_test_optimization is True
        assert inputs.split_pipeline is True
        assert inputs.pipeline_start_time == "1700000000"

    def test_main_computes_params_and_writes_parent_values_in_child_pipeline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        computed: list[list[str]] = []

        def fake_compute(command: list[str], *, check: bool) -> object:  # noqa: ARG001
            computed.append(command)
            Path(command[command.index("--output") + 1]).write_text(json.dumps(MINIMAL_PARAMS))
            return type("Result", (), {"returncode": 0})()

        monkeypatch.setattr(build_pipeline.subprocess, "run", fake_compute)
        out = tmp_path / "out"

        main(
            [
                *("--stage", "e2e", "--ci-image", "img", "--output-dir", str(out)),
                *("--libraries", "python", "--scenarios", "DEFAULT", "--parametric-job-count", "3"),
                *("--skip-empty-scenario", "true", "--force-execute", "tests/a.py::Test_A"),
            ],
            environ={
                "LIBRARIES": "java",
                "SYSTEM_TESTS_SPLIT_PIPELINE": "true",
                "CI_PIPELINE_ID": "42",
                "SYSTEM_TESTS_PIPELINE_START_TIME": "1700000000",
            },
        )

        assert [command[2] for command in computed] == ["python", "java"]
        python_command = computed[0]
        assert python_command[python_command.index("--scenarios") + 1] == "DEFAULT"
        assert python_command[python_command.index("--parametric-job-count") + 1] == "3"
        # trigger jobs don't forward variables, values of the parent pipeline are written in the child pipeline
        chunk = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert chunk["variables"] == {
            "CI_IMAGE": "img",
            "UPSTREAM_PIPELINE_ID": "42",
            "SYSTEM_TESTS_FORCE_EXECUTE": "tests/a.py::Test_A",
            "SYSTEM_TESTS_SKIP_EMPTY_SCENARIO": "true",
            "SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME": "1700000000",
        }
        # split pipeline: one chunk per trigger job of main.yml
        assert sorted(path.name for path in out.glob("generated-pipeline-chunk-*.yml")) == [
            f"generated-pipeline-chunk-{i}.yml" for i in range(build_pipeline.SPLIT_PIPELINE_CHUNKS)
        ]

    def test_chunk_count_matches_trigger_jobs_of_main_yml(self) -> None:
        _, pipeline = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())
        triggers = [name for name in pipeline if name.startswith("system_tests_e2e_run_pipeline_")]
        assert len(triggers) == build_pipeline.SPLIT_PIPELINE_CHUNKS

    def test_trigger_jobs_do_not_forward_variables(self) -> None:
        _, pipeline = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())
        base = pipeline[".run_test_pipeline_base"]
        assert base["trigger"]["forward"] == {"yaml_variables": False}
        assert "variables" not in base

    def test_local_build_weblog_is_built_in_run_job(self, tmp_path: Path) -> None:
        """build_mode: local weblogs require a build (build.sh is called), but don't get a build job."""
        params = {
            "endtoend_defs": {
                "parallel_weblogs": [{"name": "express5"}],
                "parallel_jobs": [
                    {"weblog": "express4", "scenarios": ["DEFAULT"], "weblog_build_required": True},
                    {"weblog": "express5", "scenarios": ["DEFAULT"], "weblog_build_required": True},
                ],
            },
            "miscs": {"binaries_artifact": "nodejs-binaries"},
            "parametric": {"enable": False, "parallel_jobs": []},
        }
        (tmp_path / "params_nodejs.json").write_text(json.dumps(params))
        out = tmp_path / "out"

        build(["nodejs"], tmp_path, out, stage="e2e", ci_image="img", chunks=1, binaries_artifact_path="bin")

        pipeline = yaml.safe_load((out / "generated-pipeline-chunk-0.yml").read_text())
        assert "system_tests_build_nodejs_express4" not in pipeline
        local = pipeline["system_tests_run_nodejs_DEFAULT_express4"]
        assert local["needs"] == [{"job": "nodejs-binaries", "artifacts": True, "pipeline": "$UPSTREAM_PIPELINE_ID"}]
        assert local["variables"]["SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED"] == "true"
        assert local["variables"]["SYSTEM_TESTS_BINARIES_ARTIFACT_PATH"] == "bin"

        # every job a run job needs is defined, or comes from the upstream pipeline
        for name, job in pipeline.items():
            for need in job.get("needs", []) if isinstance(job, dict) else []:
                assert "pipeline" in need or need["job"] in pipeline, f"{name} needs undefined job {need['job']}"

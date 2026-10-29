"""Tests for the library -> weblog -> scenarios mapping of the GitLab end-to-end component."""

from pathlib import Path

import yaml

from utils import pytest, scenarios
from utils.ci.gitlab.build_pipeline import build
from utils.ci.gitlab.library_weblog_scenarios import get_compute_args, main, merge_params
from utils.ci.gitlab.validate_param_env import validate_library_weblog_scenarios


def _params(weblog: str, scenario_names: list[str], *, parametric: bool = False) -> dict:
    return {
        "endtoend_defs": {
            "parallel_enable": len(scenario_names) > 0,
            "parallel_weblogs": [{"name": weblog}] if scenario_names else [],
            "parallel_jobs": [{"weblog": weblog, "scenarios": scenario_names, "weblog_build_required": True}]
            if scenario_names
            else [],
        },
        "miscs": {"binaries_artifact": ""},
        "parametric": {"enable": parametric, "job_count": 2, "job_matrix": [1, 2], "workers": 4},
    }


@scenarios.test_the_test
def test_gitlab_component_library_weblog_scenarios_input_is_wired() -> None:
    spec, pipeline = yaml.safe_load_all(Path("utils/ci/gitlab/main.yml").read_text())

    assert spec["spec"]["inputs"]["library_weblog_scenarios"]["default"] == ""
    job = pipeline["system_tests_build_pipeline"]
    assert job["variables"]["SYSTEM_TESTS_LIBRARY_WEBLOG_SCENARIOS_INPUT"] == "$[[ inputs.library_weblog_scenarios ]]"
    assert any("utils/ci/gitlab/library_weblog_scenarios.py" in line for line in job["script"])


@scenarios.test_the_test
def test_compute_args() -> None:
    assert get_compute_args(
        ["DEFAULT", "appsec", "OTEL_LOG_E2E", "tracer_release"], "OTEL_TRACING_E2E, OTEL_LOG_E2E"
    ) == [
        "--scenarios",
        "DEFAULT,OTEL_LOG_E2E",
        "--groups",
        "appsec,tracer_release",
        # explicitly listed scenarios are not excluded, exclusion only applies to groups
        "--excluded-scenarios",
        "OTEL_TRACING_E2E",
    ]


@scenarios.test_the_test
def test_merge_params() -> None:
    merged = merge_params(
        [
            _params("django-poc", ["DEFAULT"]),
            _params("flask-poc", ["APPSEC_BLOCKING", "DEFAULT"]),
            _params("fastapi", []),
        ],
        _params("", [], parametric=True),
    )

    assert merged["endtoend_defs"]["parallel_enable"] is True
    assert [w["name"] for w in merged["endtoend_defs"]["parallel_weblogs"]] == ["django-poc", "flask-poc"]
    assert [(j["weblog"], j["scenarios"]) for j in merged["endtoend_defs"]["parallel_jobs"]] == [
        ("django-poc", ["DEFAULT"]),
        ("flask-poc", ["APPSEC_BLOCKING", "DEFAULT"]),
    ]
    assert merged["parametric"]["enable"] is True


@scenarios.test_the_test
def test_parametric_is_only_enabled_by_the_parametric_key() -> None:
    # e.g. if a group listed under a weblog contains PARAMETRIC
    merged = merge_params([_params("flask-poc", ["DEFAULT"], parametric=True)], None)

    assert merged["parametric"]["enable"] is False


def _generated_jobs(tmp_path: Path, library_weblog_scenarios: str) -> set[str]:
    # same argument layout as in main.yml, including an empty value after "--"
    main(
        [
            library_weblog_scenarios,
            "--excluded-scenarios",
            "OTEL_TRACING_E2E",
            "--params-dir",
            str(tmp_path),
            "--",
            "--explicit-binaries-artifact",
            "",
            "--parametric-job-count",
            "2",
        ]
    )
    build(["python"], tmp_path, tmp_path, stage="e2e", ci_image="myimage", chunks=1)

    pipeline = yaml.safe_load((tmp_path / "generated-pipeline-chunk-0.yml").read_text())
    return {name for name in pipeline if name.startswith(("system_tests_build_", "system_tests_run_"))}


@scenarios.test_the_test
@pytest.mark.parametrize("parametric", ["[]", '["PARAMETRIC"]'])
def test_each_weblog_runs_only_its_scenarios(tmp_path: Path, parametric: str) -> None:
    jobs = _generated_jobs(
        tmp_path,
        f'{{"python": {{"parametric": {parametric}, "flask-poc": ["DEFAULT", "APPSEC_BLOCKING"], '
        '"django-poc": ["DEFAULT"]}}',
    )

    assert jobs == {
        "system_tests_build_python_django-poc",
        "system_tests_build_python_flask-poc",
        "system_tests_run_python_DEFAULT_django-poc",
        "system_tests_run_python_APPSEC_BLOCKING_flask-poc",
        "system_tests_run_python_DEFAULT_flask-poc",
        "system_tests_run_python_PARAMETRIC_1",
        "system_tests_run_python_PARAMETRIC_2",
    }


@scenarios.test_the_test
def test_parametric_only(tmp_path: Path) -> None:
    jobs = _generated_jobs(tmp_path, '{"python": {"parametric": []}}')

    assert jobs == {"system_tests_run_python_PARAMETRIC_1", "system_tests_run_python_PARAMETRIC_2"}


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("library_weblog_scenarios", "error"),
    [
        ('{"python": {"flask-poc": ["DEFAULT", "PARAMETRIC"]}}', 'must be listed as "parametric"'),
        ('{"python": {"parametric": ["DEFAULT"]}}', "expects"),
        ('{"python": {}}', "no weblog listed"),
    ],
)
def test_invalid_parametric_usage(tmp_path: Path, library_weblog_scenarios: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        main([library_weblog_scenarios, f"--params-dir={tmp_path}"])


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("value", "is_valid"),
    [
        ('{"python": {"flask-poc": ["DEFAULT", "APPSEC_BLOCKING"]}, "java": {"spring-boot": ["DEFAULT"]}}', True),
        ('{"python": {"flask-poc": ["DEFAULT", "appsec", "tracer_release"]}}', True),
        ('{"python": {"flask-poc": ["Default"]}}', False),
        ("not json", False),
        ('["python"]', False),
        ('{"python": ["DEFAULT"]}', False),
        ('{"python": {"flask-poc": "DEFAULT"}}', False),
        ('{"Python": {"flask-poc": ["DEFAULT"]}}', False),
    ],
)
def test_validate_library_weblog_scenarios(value: str, *, is_valid: bool) -> None:
    errors = validate_library_weblog_scenarios("LIBRARY_WEBLOG_SCENARIOS", value)
    assert (errors == []) is is_valid, errors

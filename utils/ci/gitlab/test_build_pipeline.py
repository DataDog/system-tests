"""Tests for build_pipeline.py"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent / "build_pipeline.py"
CI_IMAGE = "registry.example.com/ci-runner:abc123"
STAGE = "test"
LIBRARY = "python"


def _params(
    scenarios=("DEFAULT",),
    weblogs=("flask",),
    binaries_artifact="",
    parametric_enable=False,
    parametric_job_count=1,
    dockerssi_scenario_defs=None,
    libinjection_scenario_defs=None,
):
    return {
        "endtoend": {
            "scenarios": list(scenarios),
            "weblogs": list(weblogs),
        },
        "miscs": {
            "binaries_artifact": binaries_artifact,
            "ci_environment": "gitlab",
        },
        "parametric": {
            "job_count": parametric_job_count,
            "job_matrix": list(range(1, parametric_job_count + 1)),
            "enable": parametric_enable,
        },
        "dockerssi_scenario_defs": dockerssi_scenario_defs or {},
        "libinjection_scenario_defs": libinjection_scenario_defs or {},
    }


def _run(params, extra_args=(), ref="abc1234"):
    params_file = pytest.tmp_path_factory.mktemp("params") / "params.json"
    params_file.write_text(json.dumps(params))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--stage", STAGE,
            "--library", LIBRARY,
            "--params", str(params_file),
            "--ci-image", CI_IMAGE,
            "--ref", ref,
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.fixture()
def run(tmp_path):
    def _inner(params, extra_args=(), ref="abc1234"):
        params_file = tmp_path / "params.json"
        params_file.write_text(json.dumps(params))
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--stage", STAGE,
                "--library", LIBRARY,
                "--params", str(params_file),
                "--ci-image", CI_IMAGE,
                "--ref", ref,
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    return _inner


class TestOutputIsValidYaml:
    def test_basic(self, run):
        output = run(_params())
        assert yaml.safe_load(output) is not None

    def test_multiple_scenarios_and_weblogs(self, run):
        output = run(_params(scenarios=["DEFAULT", "APPSEC_SCENARIOS"], weblogs=["flask", "django"]))
        assert yaml.safe_load(output) is not None

    def test_with_parametric(self, run):
        output = run(_params(parametric_enable=True, parametric_job_count=3))
        assert yaml.safe_load(output) is not None

    def test_with_push_to_test_optimization(self, run):
        output = run(_params(), extra_args=["--push-to-test-optimization", "true"])
        assert yaml.safe_load(output) is not None


class TestBuildJobs:
    def test_one_build_job_per_weblog(self, run):
        output = run(_params(weblogs=["flask", "django"]))
        jobs = yaml.safe_load(output)
        assert f"build_{LIBRARY}_flask" in jobs
        assert f"build_{LIBRARY}_django" in jobs

    def test_build_job_has_no_needs_without_binaries_artifact(self, run):
        output = run(_params(weblogs=["flask"]))
        jobs = yaml.safe_load(output)
        assert "needs" not in jobs[f"build_{LIBRARY}_flask"]

    def test_build_job_needs_binaries_artifact(self, run):
        output = run(_params(weblogs=["flask"], binaries_artifact="upstream_binaries"))
        jobs = yaml.safe_load(output)
        needs = jobs[f"build_{LIBRARY}_flask"]["needs"]
        assert any(n.get("job") == "upstream_binaries" for n in needs)


class TestRunJobs:
    def test_one_run_job_per_scenario_and_weblog(self, run):
        output = run(_params(scenarios=["DEFAULT", "APPSEC_SCENARIOS"], weblogs=["flask", "django"]))
        jobs = yaml.safe_load(output)
        for scenario in ["DEFAULT", "APPSEC_SCENARIOS"]:
            for weblog in ["flask", "django"]:
                assert f"run_{LIBRARY}_{scenario}_{weblog}" in jobs

    def test_run_job_needs_build_job(self, run):
        output = run(_params(scenarios=["DEFAULT"], weblogs=["flask"]))
        jobs = yaml.safe_load(output)
        needs = jobs[f"run_{LIBRARY}_DEFAULT_flask"]["needs"]
        assert any(n.get("job") == f"build_{LIBRARY}_flask" for n in needs)


class TestParametricJobs:
    def test_no_parametric_jobs_when_disabled(self, run):
        output = run(_params(parametric_enable=False))
        jobs = yaml.safe_load(output)
        assert not any(k.startswith(f"run_{LIBRARY}_PARAMETRIC_") for k in jobs)

    def test_parametric_jobs_created_when_enabled(self, run):
        output = run(_params(parametric_enable=True, parametric_job_count=2))
        jobs = yaml.safe_load(output)
        assert f"run_{LIBRARY}_PARAMETRIC_1" in jobs
        assert f"run_{LIBRARY}_PARAMETRIC_2" in jobs

    def test_parametric_job_count(self, run):
        output = run(_params(parametric_enable=True, parametric_job_count=4))
        jobs = yaml.safe_load(output)
        parametric_jobs = [k for k in jobs if k.startswith(f"run_{LIBRARY}_PARAMETRIC_")]
        assert len(parametric_jobs) == 4


class TestPushTestOptimization:
    def test_no_push_job_by_default(self, run):
        output = run(_params(scenarios=["DEFAULT"], weblogs=["flask"]))
        jobs = yaml.safe_load(output)
        assert f"push_{LIBRARY}_test_optimization" not in jobs

    def test_push_job_created_when_enabled(self, run):
        output = run(_params(scenarios=["DEFAULT"], weblogs=["flask"]), extra_args=["--push-to-test-optimization", "true"])
        jobs = yaml.safe_load(output)
        assert f"push_{LIBRARY}_test_optimization" in jobs

    def test_push_job_needs_all_run_jobs(self, run):
        output = run(
            _params(scenarios=["DEFAULT", "APPSEC_SCENARIOS"], weblogs=["flask"]),
            extra_args=["--push-to-test-optimization", "true"],
        )
        jobs = yaml.safe_load(output)
        push_needs = {n["job"] for n in jobs[f"push_{LIBRARY}_test_optimization"]["needs"]}
        assert f"run_{LIBRARY}_DEFAULT_flask" in push_needs
        assert f"run_{LIBRARY}_APPSEC_SCENARIOS_flask" in push_needs

    def test_push_job_uses_custom_datadog_site(self, run):
        output = run(
            _params(scenarios=["DEFAULT"], weblogs=["flask"]),
            extra_args=["--push-to-test-optimization", "true", "--test-optimization-datadog-site", "datadoghq.eu"],
        )
        jobs = yaml.safe_load(output)
        push_job = jobs[f"push_{LIBRARY}_test_optimization"]
        assert push_job["variables"]["DATADOG_SITE"] == "datadoghq.eu"


class TestCiImageAndRef:
    def test_ci_image_used_in_push_job(self, run):
        output = run(
            _params(scenarios=["DEFAULT"], weblogs=["flask"]),
            extra_args=["--push-to-test-optimization", "true"],
        )
        jobs = yaml.safe_load(output)
        push_job = jobs[f"push_{LIBRARY}_test_optimization"]
        assert push_job["image"] == CI_IMAGE

    def test_ref_passed_to_template_include(self, run):
        output = run(_params(), ref="deadbeef")
        # The include block is at the top of the YAML
        parsed = yaml.safe_load(output)
        include = parsed.get("include", [])
        assert any("deadbeef" in str(item) for item in include)


_DOCKERSSI_DEFS = {
    "DOCKER_SSI": {
        "my-weblog": [
            {"ubuntu:22.04": ["3.8", "3.9"], "arch": "linux/amd64"},
            {"ubuntu:22.04": ["3.8"], "arch": "linux/arm64"},
        ]
    }
}

_LIBINJECTION_DEFS = {
    "K8S_LIB_INJECTION": ["weblog1", "weblog2"],
    "K8S_LIB_INJECTION_NO_AC": ["weblog1"],
}


class TestDockerSSI:
    def test_no_dockerssi_jobs_when_empty(self, run):
        output = run(_params())
        jobs = yaml.safe_load(output)
        assert not any("DOCKER_SSI" in k for k in jobs)

    def test_dockerssi_jobs_created(self, run):
        output = run(_params(dockerssi_scenario_defs=_DOCKERSSI_DEFS))
        jobs = yaml.safe_load(output)
        # one job per (weblog, arch, runtime) combination
        assert f"run_{LIBRARY}_DOCKER_SSI_my-weblog_amd64_3_8" in jobs
        assert f"run_{LIBRARY}_DOCKER_SSI_my-weblog_amd64_3_9" in jobs
        assert f"run_{LIBRARY}_DOCKER_SSI_my-weblog_arm64_3_8" in jobs

    def test_dockerssi_job_has_static_variables(self, run):
        output = run(_params(dockerssi_scenario_defs=_DOCKERSSI_DEFS))
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_DOCKER_SSI_my-weblog_amd64_3_8"]
        assert job["variables"]["IMAGE"] == "ubuntu:22.04"
        assert job["variables"]["RUNTIME"] == "3.8"
        assert job["variables"]["ARCH"] == "linux/amd64"
        assert "parallel" not in job

    def test_dockerssi_job_sets_ssi_library_version(self, run):
        output = run(
            _params(dockerssi_scenario_defs=_DOCKERSSI_DEFS),
            extra_args=["--ssi-library-version", "1.2.3"],
        )
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_DOCKER_SSI_my-weblog_amd64_3_8"]
        assert job["variables"]["DD_INSTALLER_LIBRARY_VERSION"] == "1.2.3"

    def test_dockerssi_job_no_ssi_version_by_default(self, run):
        output = run(_params(dockerssi_scenario_defs=_DOCKERSSI_DEFS))
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_DOCKER_SSI_my-weblog_amd64_3_8"]
        assert "DD_INSTALLER_LIBRARY_VERSION" not in job.get("variables", {})

    def test_output_is_valid_yaml_with_dockerssi(self, run):
        output = run(_params(dockerssi_scenario_defs=_DOCKERSSI_DEFS))
        assert yaml.safe_load(output) is not None


class TestLibInjection:
    def test_no_libinjection_jobs_when_empty(self, run):
        output = run(_params())
        jobs = yaml.safe_load(output)
        assert not any("K8S_LIB_INJECTION" in k for k in jobs)

    def test_libinjection_jobs_created(self, run):
        output = run(_params(libinjection_scenario_defs=_LIBINJECTION_DEFS))
        jobs = yaml.safe_load(output)
        # one job per (scenario, weblog) combination
        assert f"run_{LIBRARY}_K8S_LIB_INJECTION_weblog1" in jobs
        assert f"run_{LIBRARY}_K8S_LIB_INJECTION_weblog2" in jobs
        assert f"run_{LIBRARY}_K8S_LIB_INJECTION_NO_AC_weblog1" in jobs

    def test_libinjection_job_has_static_variables(self, run):
        output = run(_params(libinjection_scenario_defs=_LIBINJECTION_DEFS))
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_K8S_LIB_INJECTION_weblog1"]
        assert job["variables"]["K8S_WEBLOG"] == "weblog1"
        assert "parallel" not in job

    def test_libinjection_job_sets_k8s_lib_init_img(self, run):
        output = run(
            _params(libinjection_scenario_defs=_LIBINJECTION_DEFS),
            extra_args=["--k8s-lib-init-img", "my-registry/lib-init:latest"],
        )
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_K8S_LIB_INJECTION_weblog1"]
        assert job["variables"]["K8S_LIB_INIT_IMG"] == "my-registry/lib-init:latest"

    def test_libinjection_job_no_k8s_img_by_default(self, run):
        output = run(_params(libinjection_scenario_defs=_LIBINJECTION_DEFS))
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_K8S_LIB_INJECTION_weblog1"]
        assert "K8S_LIB_INIT_IMG" not in job.get("variables", {})

    def test_output_is_valid_yaml_with_libinjection(self, run):
        output = run(_params(libinjection_scenario_defs=_LIBINJECTION_DEFS))
        assert yaml.safe_load(output) is not None


class TestSsiVariablesNotLeakedIntoEndToEndJobs:
    def test_no_ssi_variables_in_endtoend_run_job(self, run):
        output = run(
            _params(scenarios=["DEFAULT"], weblogs=["flask"]),
            extra_args=["--ssi-library-version", "2.0.0", "--k8s-lib-init-img", "my-registry/lib-init:v1"],
        )
        jobs = yaml.safe_load(output)
        job = jobs[f"run_{LIBRARY}_DEFAULT_flask"]
        variables = job.get("variables") or {}
        assert "DD_INSTALLER_LIBRARY_VERSION" not in variables
        assert "K8S_LIB_INIT_IMG" not in variables

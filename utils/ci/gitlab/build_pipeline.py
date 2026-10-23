"""Generate the GitLab child pipeline(s) running system-tests end-to-end and parametric scenarios.

Generated jobs only carry what differs from one job to another (variables, needs, runner tags). Their
script, artifacts and other static settings come from the hidden jobs of child-pipeline.yml, and the job
logic lives in the scripts of utils/ci/gitlab/jobs/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Mapping

TEMPLATES_FILE = "utils/ci/gitlab/templates.yml"
CHILD_PIPELINE_FILE = "utils/ci/gitlab/child-pipeline.yml"

# CWS needs the Kata VM's kernel filesystems, which this runner pool mounts under /vm-host
# (see docs/understand/scenarios/thread_context_sharing.md)
SCENARIO_RUNNER_TAGS: dict[str, list[str]] = {"THREAD_CONTEXT_SHARING": ["docker-in-docker:amd64-cws"]}


def noop_stub(stage: str) -> str:
    """Return a minimal valid GitLab pipeline YAML for an empty chunk."""
    return f"""workflow:
  name: "System-tests end to end (empty chunk)"
stages:
  - {stage}
noop:
  stage: {stage}
  tags:
    - arch:amd64
  script:
    - echo "no libraries assigned to this chunk"
"""


def pipeline_header(*, stage: str, ci_image: str, ref: str, pipeline_variables: Mapping[str, str]) -> dict:
    """Top-level keys of a chunk. Static content lives in the included files.

    The trigger jobs of main.yml don't forward any variable (trigger:forward:yaml_variables: false), so the
    values the child pipeline needs from the parent pipeline are written here, as literals.
    """
    return {
        "workflow": {"name": "System-tests end to end"},
        "include": [
            {
                "project": "DataDog/system-tests",
                "ref": ref,
                "file": TEMPLATES_FILE,
                "inputs": {"stage": stage, "ref": ref},
            },
            {"project": "DataDog/system-tests", "ref": ref, "file": CHILD_PIPELINE_FILE},
        ],
        "stages": [stage],
        "variables": {"CI_IMAGE": ci_image, **pipeline_variables},
    }


def library_jobs(
    library: str,
    params: dict,
    *,
    push_to_test_optimization: bool,
    binaries_artifact_path: str,
    binaries_artifacts: str,
) -> dict[str, dict]:
    """Jobs of one library. They only carry what differs between jobs, the rest comes from child-pipeline.yml.

    Job variables are read by the job scripts (utils/ci/gitlab/jobs/) and by system-tests commands.
    """
    endtoend_defs = params.get("endtoend_defs", {})
    parametric = params["parametric"]

    upstream_jobs = _upstream_artifact_jobs(binaries_artifacts, params["miscs"]["binaries_artifact"])
    upstream_needs = [{"job": job, "artifacts": True, "pipeline": "$UPSTREAM_PIPELINE_ID"} for job in upstream_jobs]
    # copy upstream binaries into binaries/, only on jobs that download them
    copy_binaries = (
        {"SYSTEM_TESTS_BINARIES_ARTIFACT_PATH": binaries_artifact_path}
        if upstream_jobs and binaries_artifact_path
        else {}
    )
    test_mixins = [".push_to_test_optimization"] if push_to_test_optimization else []

    jobs: dict[str, dict] = {}

    for weblog_def in endtoend_defs.get("parallel_weblogs", []):
        weblog = weblog_def["name"]
        jobs[_build_job_name(library, weblog)] = _job(
            ".system_tests_build",
            variables=_weblog_variables(library, weblog) | copy_binaries,
            needs=upstream_needs,
        )

    for job_def in endtoend_defs.get("parallel_jobs", []):
        weblog = job_def["weblog"]
        build_required = job_def.get("weblog_build_required", True)
        for scenario in job_def.get("scenarios", []):
            variables = _weblog_variables(library, weblog) | {
                "SYSTEM_TESTS_SCENARIO": scenario,
                "SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED": _bool(build_required),
            }
            if build_required:
                needs = [{"job": _build_job_name(library, weblog), "artifacts": True}]
            else:
                variables |= copy_binaries
                needs = upstream_needs
            jobs[f"system_tests_run_{library}_{scenario}_{weblog}"] = _job(
                [".system_tests_run", *test_mixins],
                variables=variables,
                needs=needs,
                tags=SCENARIO_RUNNER_TAGS.get(scenario),
            )

    if parametric["enable"]:
        for group in parametric["job_matrix"]:
            jobs[f"system_tests_run_{library}_PARAMETRIC_{group}"] = _job(
                [".system_tests_parametric", *test_mixins],
                variables={
                    "TEST_LIBRARY": library,
                    "SYSTEM_TESTS_PARAMETRIC_GROUP": str(group),
                    "SYSTEM_TESTS_PARAMETRIC_JOB_COUNT": str(parametric["job_count"]),
                    "SYSTEM_TESTS_PARAMETRIC_WORKERS": str(parametric["workers"]),
                }
                | copy_binaries,
                needs=upstream_needs,
            )

    return jobs


def _upstream_artifact_jobs(binaries_artifacts: str, binaries_artifact: str) -> list[str]:
    """Upstream jobs to download artifacts from: binaries_artifacts if provided, else the job from params."""
    if binaries_artifacts:
        return [job.strip() for job in binaries_artifacts.split(";") if job.strip()]
    if binaries_artifact:
        return [binaries_artifact]
    return []


def _build_job_name(library: str, weblog: str) -> str:
    return f"system_tests_build_{library}_{weblog}"


def _weblog_variables(library: str, weblog: str) -> dict[str, str]:
    # TEST_LIBRARY/WEBLOG_VARIANT are read by build.sh, TEST_LIBRARY/SYSTEM_TESTS_WEBLOG by run.sh
    return {"TEST_LIBRARY": library, "WEBLOG_VARIANT": weblog, "SYSTEM_TESTS_WEBLOG": weblog}


def _job(
    extends: str | list[str],
    *,
    variables: dict[str, str],
    needs: list[dict],
    tags: list[str] | None = None,
) -> dict:
    job: dict = {"extends": extends, "variables": variables}
    if needs:
        job["needs"] = needs
    if tags:
        job["tags"] = tags
    return job


def _bool(value: bool) -> str:  # noqa: FBT001
    return "true" if value else "false"


def to_yaml(pipeline: dict) -> str:
    """Dump each top-level key separately, with a blank line in between, for readability."""
    return "\n".join(yaml.safe_dump({key: value}, sort_keys=False, width=1000) for key, value in pipeline.items())


def build(
    libraries: list[str],
    params_dir: Path,
    output_dir: Path,
    *,
    stage: str,
    ci_image: str,
    ref: str = "",
    push_to_test_optimization: bool = False,
    chunks: int = 3,
    binaries_artifact_path: str = "",
    binaries_artifacts: str = "",
    pipeline_variables: Mapping[str, str] | None = None,
) -> None:
    """Render pipeline chunk files into *output_dir*, one per chunk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Assign libraries to chunks via simple round-robin
    chunk_libraries: dict[int, list[str]] = {i: [] for i in range(chunks)}
    for idx, library in enumerate(libraries):
        chunk_libraries[idx % chunks].append(library)

    # Render and write all chunks; empty chunks get a noop stub so trigger jobs
    # always have a valid pipeline file — dotenv vars are not available in rules:
    # at pipeline-creation time (gitlab-org/gitlab#235812).
    for chunk_idx, chunk_libs in chunk_libraries.items():
        chunk_file = output_dir / f"generated-pipeline-chunk-{chunk_idx}.yml"

        if not chunk_libs:
            chunk_file.write_text(noop_stub(stage))
            continue

        pipeline = pipeline_header(
            stage=stage,
            ci_image=ci_image,
            ref=ref,
            pipeline_variables=pipeline_variables or {},
        )
        for library in chunk_libs:
            params_file = params_dir / f"params_{library}.json"
            if not params_file.exists():
                print(f"ERROR: params file not found for library '{library}': {params_file}", file=sys.stderr)  # noqa: T201
                sys.exit(1)
            with open(params_file) as f:
                params = json.load(f)
            pipeline |= library_jobs(
                library,
                params,
                push_to_test_optimization=push_to_test_optimization,
                binaries_artifact_path=binaries_artifact_path,
                binaries_artifacts=binaries_artifacts,
            )

        chunk_file.write_text(to_yaml(pipeline))


# Pipeline variables a caller can set to complement or override the component inputs
# (validated by validate_param_env.py). List values are merged with the inputs, scalars replace them.
MERGED_LIST_VARIABLES = {
    "libraries": "LIBRARIES",
    "scenarios": "SCENARIOS",
    "scenario_groups": "SCENARIO_GROUPS",
    "weblogs": "WEBLOGS",
    "excluded_scenarios": "EXCLUDED_SCENARIOS",
    "force_execute": "FORCE_EXECUTE",
}
OVERRIDE_VARIABLES = {
    "parametric_job_count": "SYSTEM_TESTS_PARAMETRIC_JOB_COUNT",
    "parametric_workers": "SYSTEM_TESTS_PARAMETRIC_WORKERS",
    "push_to_test_optimization": "SYSTEM_TESTS_PUSH_TO_TEST_OPTIMIZATION",
    "skip_empty_scenario": "SYSTEM_TESTS_SKIP_EMPTY_SCENARIO",
    "binaries_artifacts": "BINARIES_ARTIFACTS",
    "binaries_artifact_path": "BINARIES_ARTIFACT_PATH",
    "split_pipeline": "SYSTEM_TESTS_SPLIT_PIPELINE",
    "pipeline_start_time": "SYSTEM_TESTS_PIPELINE_START_TIME",
}

COMPUTE_PARAMETERS_SCRIPT = "utils/scripts/compute-workflow-parameters.py"
SPLIT_PIPELINE_CHUNKS = 3  # must match the number of system_tests_e2e_run_pipeline_N jobs of main.yml


def _split(value: str, separators: str = ",") -> list[str]:
    """Split a list on any of *separators*, dropping empty items and duplicates, keeping order."""
    items = (item.strip() for item in re.split(f"[{re.escape(separators)}]", value))
    return list(dict.fromkeys(item for item in items if item))


def resolve_inputs(args: argparse.Namespace, environ: Mapping[str, str]) -> argparse.Namespace:
    """Merge the component inputs (command line arguments) with the pipeline variables set by the caller."""
    resolved = argparse.Namespace(**vars(args))

    for name, variable in MERGED_LIST_VARIABLES.items():
        # libraries were historically space-separated too; node IDs of force_execute may contain spaces
        separators = ", \t\n" if name == "libraries" else ","
        items = _split(getattr(args, name), separators) + _split(environ.get(variable, ""), separators)
        setattr(resolved, name, list(dict.fromkeys(items)))
    resolved.excluded_scenarios = sorted(resolved.excluded_scenarios)

    for name, variable in OVERRIDE_VARIABLES.items():
        if value := environ.get(variable, ""):
            setattr(resolved, name, value)

    resolved.parametric_job_count = int(resolved.parametric_job_count)
    resolved.parametric_workers = int(resolved.parametric_workers)
    for name in ("push_to_test_optimization", "skip_empty_scenario", "split_pipeline"):
        setattr(resolved, name, str(getattr(resolved, name)).lower() == "true")

    return resolved


def compute_params(library: str, inputs: argparse.Namespace, params_dir: Path) -> None:
    """Write params_<library>.json, the scenarios/weblogs/parametric matrix of one library."""
    command = [
        sys.executable,
        COMPUTE_PARAMETERS_SCRIPT,
        library,
        "--format",
        "json",
        "--scenarios",
        ",".join(inputs.scenarios),
        "--groups",
        ",".join(inputs.scenario_groups),
        "--excluded-scenarios",
        ",".join(inputs.excluded_scenarios),
        "--weblogs",
        ",".join(inputs.weblogs),
        "--explicit-binaries-artifact",
        inputs.binaries_artifacts,
        "--parametric-job-count",
        str(inputs.parametric_job_count),
        "--parametric-workers",
        str(inputs.parametric_workers),
        "--output",
        str(params_dir / f"params_{library}.json"),
    ]
    returncode = subprocess.run(command, check=False).returncode
    if returncode != 0:
        sys.exit(returncode)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the child pipeline(s) of the system-tests GitLab component. Arguments are the "
        "component inputs; pipeline variables set by the caller (see OVERRIDE_VARIABLES and "
        "MERGED_LIST_VARIABLES) are read from the environment and merged in."
    )
    parser.add_argument("--stage", required=True, help="GitLab CI stage for the generated jobs")
    parser.add_argument("--ci-image", required=True, help="Full CI image reference for generated jobs")
    parser.add_argument("--ref", default="", help="system-tests ref to clone when called from another repository")
    parser.add_argument("--output-dir", required=True, help="Output directory for the generated files")
    parser.add_argument(
        "--params-dir",
        default=None,
        help="Directory containing pre-computed params_<lib>.json files (computed into --output-dir if omitted)",
    )

    parser.add_argument("--libraries", default="", help="Comma-separated list of libraries")
    parser.add_argument("--scenarios", default="", help="Comma-separated list of scenarios")
    parser.add_argument("--scenario-groups", default="", help="Comma-separated list of scenario groups")
    parser.add_argument("--weblogs", default="", help="Comma-separated list of weblogs (all weblogs if empty)")
    parser.add_argument("--excluded-scenarios", default="", help="Comma-separated list of scenarios not to run")
    parser.add_argument("--force-execute", default="", help="Comma-separated test node IDs to force-execute")
    parser.add_argument("--parametric-job-count", default="1", help="Number of parallel jobs for PARAMETRIC")
    parser.add_argument("--parametric-workers", default="4", help="Maximum pytest-xdist workers per PARAMETRIC job")
    parser.add_argument("--push-to-test-optimization", default="false", help="Upload JUnit reports of run jobs")
    parser.add_argument("--skip-empty-scenario", default="false", help="Skip scenarios with only xfail tests")
    parser.add_argument("--split-pipeline", default="false", help="Split jobs across 3 child pipelines")
    parser.add_argument(
        "--binaries-artifact-path",
        default="",
        help="Path (relative to CI_PROJECT_DIR) of the binaries_artifact contents, copied into binaries/",
    )
    parser.add_argument(
        "--binaries-artifacts",
        default="",
        help="Semicolon-separated list of upstream jobs to download artifacts from in the child pipeline "
        "(';' not ',' because job names may contain commas, e.g. parallel matrix names; "
        "falls back to the single binaries_artifact from params if empty)",
    )
    parser.add_argument(
        "--pipeline-start-time",
        default="",
        help="Unix epoch timestamp (from .system_tests_param_base) written as a literal pipeline variable in "
        "the generated child pipeline, so run jobs can compute elapsed time",
    )
    return parser.parse_args(argv)


def child_pipeline_variables(inputs: argparse.Namespace, environ: Mapping[str, str]) -> dict[str, str]:
    """Values of the parent pipeline needed by the child pipelines, written in the generated files."""
    return {
        # parent pipeline, from which the generated jobs download the upstream binaries (needs:pipeline)
        "UPSTREAM_PIPELINE_ID": environ.get("CI_PIPELINE_ID", ""),
        # read by conftest.py
        "SYSTEM_TESTS_FORCE_EXECUTE": ",".join(inputs.force_execute),
        "SYSTEM_TESTS_SKIP_EMPTY_SCENARIO": _bool(inputs.skip_empty_scenario),
        # read by the job scripts to report the total duration
        "SYSTEM_TESTS_GENERATED_PIPELINE_START_TIME": inputs.pipeline_start_time,
    }


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = os.environ if environ is None else environ
    inputs = resolve_inputs(parse_args(argv), environ)
    output_dir = Path(inputs.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name in (*MERGED_LIST_VARIABLES, *OVERRIDE_VARIABLES):
        value = getattr(inputs, name)
        if isinstance(value, list):
            value = ",".join(value)
        elif isinstance(value, bool):
            value = _bool(value)
        print(f"{name + ':':28}{value}")  # noqa: T201

    if inputs.params_dir is None:
        params_dir = output_dir
        for library in inputs.libraries:
            compute_params(library, inputs, params_dir)
    else:
        params_dir = Path(inputs.params_dir)

    build(
        libraries=inputs.libraries,
        params_dir=params_dir,
        output_dir=output_dir,
        stage=inputs.stage,
        ci_image=inputs.ci_image,
        ref=inputs.ref,
        push_to_test_optimization=inputs.push_to_test_optimization,
        chunks=SPLIT_PIPELINE_CHUNKS if inputs.split_pipeline else 1,
        binaries_artifact_path=inputs.binaries_artifact_path,
        binaries_artifacts=inputs.binaries_artifacts,
        pipeline_variables=child_pipeline_variables(inputs, environ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Generate the GitLab child pipeline(s) running system-tests end-to-end and parametric scenarios.

Generated jobs only carry what differs from one job to another (variables, needs, runner tags). Their
script, artifacts and other static settings come from the hidden jobs of child-pipeline.yml, and the job
logic lives in the scripts of utils/ci/gitlab/jobs/.
"""

from __future__ import annotations

import argparse
import functools
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

TEMPLATES_FILE = "utils/ci/gitlab/templates.yml"
CHILD_PIPELINE_FILE = "utils/ci/gitlab/child-pipeline.yml"

# Runner tags of the scenarios needing a dedicated runner pool, by priority: a run job gets the tags of the first
# entry matching one of its scenarios, so the runners of an entry must be able to run the scenarios of the entries
# after it, and the scenarios without dedicated tags (default runner).
SCENARIO_RUNNER_TAGS: dict[str, list[str]] = {
    # CWS needs the Kata VM's kernel filesystems, which this runner pool mounts under /vm-host
    # (see docs/understand/scenarios/thread_context_sharing.md)
    "THREAD_CONTEXT_SHARING": ["docker-in-docker:amd64-cws"],
}


@functools.cache
def _run_job_timeout_minutes() -> int:
    """Timeout of .system_tests_run in child-pipeline.yml, the one of jobs running a single scenario."""
    child_pipeline = yaml.safe_load((Path(__file__).parent / "child-pipeline.yml").read_text())
    timeout = child_pipeline[".system_tests_run"]["timeout"]
    match = re.fullmatch(r"(\d+) minutes?", timeout)
    if not match:
        raise ValueError(f"Unexpected timeout format for .system_tests_run in {CHILD_PIPELINE_FILE}: {timeout!r}")
    return int(match.group(1))


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
    target_branches: Mapping[str, str] | None = None,
) -> dict[str, dict]:
    """Jobs of one library. They only carry what differs between jobs, the rest comes from child-pipeline.yml.

    Job variables are read by the job scripts (utils/ci/gitlab/jobs/) and by system-tests commands.

    Each end-to-end job of the params (see EndToEndScheduler and split_scenarios_into_jobs) gets a run job, that runs
    all its scenarios.

    In dev mode (target_branches is not None, see check_dev_mode), the binaries come from a dev binaries job of the
    library, in this pipeline, instead of upstream jobs.
    """
    endtoend_defs = params.get("endtoend_defs", {})
    parametric = params["parametric"]

    if target_branches is not None:
        upstream_needs = [{"job": _dev_binaries_job_name(library), "artifacts": True}]
        copy_binaries = {"SYSTEM_TESTS_BINARIES_ARTIFACT_PATH": DEV_BINARIES_PATH}
    else:
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

    # Only weblogs with build_mode: prebuild get a build job. Weblogs with build_mode: local also require a build,
    # but it is light enough to be done by build.sh in their run jobs, from the upstream binaries.
    prebuilt_weblogs = list(
        dict.fromkeys(weblog_def["name"] for weblog_def in endtoend_defs.get("parallel_weblogs", []))
    )

    for weblog in prebuilt_weblogs:
        jobs[_build_job_name(library, weblog)] = _job(
            ".system_tests_build",
            variables=_weblog_variables(library, weblog) | copy_binaries,
            needs=upstream_needs,
        )

    for job_def in endtoend_defs.get("parallel_jobs", []):
        weblog = job_def["weblog"]
        scenarios: list[str] = job_def["scenarios"]
        variables = _weblog_variables(library, weblog) | {
            "SYSTEM_TESTS_SCENARIOS": ",".join(scenarios),
            # run build.sh before run.sh: it loads the image of the build job, or builds it if there is none
            "SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED": _bool(job_def.get("weblog_build_required", True)),
        }
        if weblog in prebuilt_weblogs:
            needs = [{"job": _build_job_name(library, weblog), "artifacts": True}]
        else:
            variables |= copy_binaries
            needs = upstream_needs

        if len(scenarios) == 1:
            name = f"system_tests_run_{library}_{scenarios[0]}_{weblog}"
            timeout = None  # the one of .system_tests_run
        else:
            name = f"system_tests_run_{library}_{weblog}_{job_def['weblog_instance']}"
            timeout = _grouped_run_job_timeout(job_def)
        jobs[name] = _job(
            [".system_tests_run", *test_mixins],
            variables=variables,
            needs=needs,
            tags=_runner_tags(scenarios),
            timeout=timeout,
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

    if target_branches is not None and jobs:
        # first, so that it is listed first
        jobs = {
            _dev_binaries_job_name(library): _job(
                ".system_tests_dev_binaries", variables=dev_binaries_variables(library, target_branches), needs=[]
            )
        } | jobs

    return jobs


# Dev mode: like _system_tests_dev_mode of the GitHub workflows, the agent and the libraries are tested on their dev
# version (last commit of their main branch, or of a target branch), fetched by utils/scripts/load-binary.sh in a
# dev binaries job per library (utils/ci/gitlab/jobs/load_dev_binaries.py).
DEV_BINARIES_PATH = "dev-binaries"  # artifacts of .system_tests_dev_binaries, relative to $CI_PROJECT_DIR

# Libraries whose dev binaries load-binary.sh fetches without any GitHub credentials, or with a token scoped to
# DataDog/system-tests only (the value: True to get one, see jobs/load_dev_binaries.py).
DEV_MODE_LIBRARIES: dict[str, bool] = {
    "c": False,  # only without target branch: see DEV_MODE_UNSUPPORTED_TARGET_BRANCHES
    "cpp": False,
    "cpp_kong": False,
    "dotnet": False,
    # GitHub API, on the public DataDog/dd-trace-go: works unauthenticated too, with a lower rate limit
    "golang": True,
    "java": False,
    "java_lambda": False,
    "nodejs": False,
    "php": False,
    "python": False,
    "ruby": False,
    "ruby_lambda": False,
    "rust": False,
}
# Why the other libraries can't run in dev mode yet
DEV_MODE_UNSUPPORTED_LIBRARIES: dict[str, str] = {
    **dict.fromkeys(
        ("java_otel", "nodejs_otel", "python_otel", "otel_collector"),
        "no dev version (not run in dev mode by the GitHub workflows either)",
    ),
    **dict.fromkeys(
        ("cpp_httpd", "cpp_nginx", "python_lambda", "nodejs_lambda"),
        "load-binary.sh downloads GitHub Actions artifacts of another repository, which needs a GitHub token "
        "allowed to read them: no dd-octo-sts policy provides one to GitLab jobs yet",
    ),
}
# Target branch map keys that can't be used yet
DEV_MODE_UNSUPPORTED_TARGET_BRANCHES: dict[str, str] = dict.fromkeys(
    ("c", "auto_inject"),
    "load-binary.sh resolves it in an internal repository (DataDog/dd-trace-c, DataDog/auto_inject), which needs "
    "a GitHub token allowed to read it: no dd-octo-sts policy provides one to GitLab jobs yet",
)
# Branch names are written in the generated YAML, and read by load-binary.sh: no character GitLab would expand ($)
TARGET_BRANCH_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/+-]*")


def _dev_binaries_job_name(library: str) -> str:
    return f"system_tests_dev_binaries_{library}"


def dev_binaries_variables(library: str, target_branches: Mapping[str, str]) -> dict[str, str]:
    """Variables of the dev binaries job of a library: like the GitHub workflow, the target branches of the map
    read by load-binary.sh are the one of the library, and the one of the agent.
    """
    variables = {"TEST_LIBRARY": library}
    if branch := target_branches.get(library):
        variables["LIBRARY_TARGET_BRANCH"] = branch
    if branch := target_branches.get("agent"):
        variables["AGENT_TARGET_BRANCH"] = branch
    if DEV_MODE_LIBRARIES[library]:
        variables["SYSTEM_TESTS_DEV_BINARIES_GITHUB_TOKEN"] = "true"  # noqa: S105 (not a secret)
    return variables


def parse_target_branch_map(value: str) -> dict[str, str]:
    """Parse the target branch map of the dev mode: JSON object {library or "agent": branch}, like
    _system_tests_library_target_branch_map of the GitHub workflows (e.g. {"python": "my-branch"}).
    """
    if not value.strip():
        return {}
    try:
        mapping = json.loads(value)
    except json.JSONDecodeError as error:
        raise InputError(
            f'target_branch_map: invalid JSON ({error}), expected e.g. {{"python": "my-branch"}}'
        ) from None
    if not isinstance(mapping, dict):
        raise InputError(f'target_branch_map: expected a JSON object, e.g. {{"python": "my-branch"}}, got {value!r}')

    known = {*DEV_MODE_LIBRARIES, *DEV_MODE_UNSUPPORTED_LIBRARIES, "agent", "auto_inject"}
    for key, branch in mapping.items():
        if key not in known:
            raise InputError(f"target_branch_map: unknown library {key!r}, expected one of {', '.join(sorted(known))}")
        if not isinstance(branch, str) or not TARGET_BRANCH_PATTERN.fullmatch(branch):
            raise InputError(f"target_branch_map: invalid branch for {key}: {branch!r}")
        if key in DEV_MODE_UNSUPPORTED_TARGET_BRANCHES:
            raise InputError(
                f"target_branch_map: {key} can't have a target branch: {DEV_MODE_UNSUPPORTED_TARGET_BRANCHES[key]}"
            )
    return mapping


def check_dev_mode(inputs: argparse.Namespace) -> dict[str, str]:
    """Check that the dev mode can be used with the other inputs, and return the target branch map."""
    if inputs.binaries_artifacts or inputs.binaries_artifact_path:
        # both give the binaries to test: rather than one silently winning, ask for one of them
        raise InputError(
            "dev_mode can't be used with binaries_artifacts or binaries_artifact_path: the dev mode tests the dev "
            "binaries it fetches, binaries_artifacts the binaries of upstream jobs"
        )
    if unsupported := [library for library in inputs.libraries if library not in DEV_MODE_LIBRARIES]:
        reasons = (
            f"{library}: {DEV_MODE_UNSUPPORTED_LIBRARIES.get(library, 'unknown library')}" for library in unsupported
        )
        raise InputError(f"dev_mode is not supported for: {'; '.join(reasons)}")
    return parse_target_branch_map(inputs.target_branch_map)


def _runner_tags(scenarios: list[str]) -> list[str] | None:
    """Tags of the highest priority entry of SCENARIO_RUNNER_TAGS matching one of the scenarios, if any."""
    return next((tags for scenario, tags in SCENARIO_RUNNER_TAGS.items() if scenario in scenarios), None)


def _grouped_run_job_timeout(job_def: dict) -> str:
    """Timeout of a run job running several scenarios: twice their expected time (with some margin, as the time
    stats come from GitHub runners), never less than the timeout of a single scenario job.
    """
    minutes = math.ceil(2 * float(job_def["expected_job_time"]) / 60) + 5
    return f"{max(_run_job_timeout_minutes(), minutes)} minutes"


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
    # read by run.sh (TEST_LIBRARY by build.sh too, the weblog is passed to build.sh by the job scripts)
    return {"TEST_LIBRARY": library, "SYSTEM_TESTS_WEBLOG": weblog}


def _job(
    extends: str | list[str],
    *,
    variables: dict[str, str],
    needs: list[dict],
    tags: list[str] | None = None,
    timeout: str | None = None,
) -> dict:
    job: dict = {"extends": extends, "variables": variables}
    if needs:
        job["needs"] = needs
    if tags:
        job["tags"] = tags
    if timeout:
        job["timeout"] = timeout
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
    endtoend_job_count: int = 0,
    desired_execution_time: int = -1,
    target_branches: Mapping[str, str] | None = None,
) -> None:
    """Render pipeline chunk files into *output_dir*, one per chunk.

    End-to-end scenarios of all libraries are split into run jobs by EndToEndScheduler, until there are
    endtoend_job_count jobs, or else until they all fit in desired_execution_time (main() checks that only one of
    them is set). Otherwise, each scenario gets its own run job.

    target_branches: only in dev mode (None otherwise), the target branch map (see library_jobs).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_params: dict[str, dict] = {}
    for library in libraries:
        params_file = params_dir / f"params_{library}.json"
        if not params_file.exists():
            print(f"ERROR: params file not found for library '{library}': {params_file}", file=sys.stderr)  # noqa: T201
            sys.exit(1)
        all_params[library] = json.loads(params_file.read_text())

    if endtoend_job_count > 0:
        EndToEndScheduler(all_params).schedule(job_count=endtoend_job_count)
    elif desired_execution_time > 0:
        job_count = EndToEndScheduler(all_params).schedule(max_job_time=desired_execution_time)
        print(f"desired_execution_time of {desired_execution_time}s: {job_count} end-to-end jobs")  # noqa: T201
    else:
        split_scenarios_into_jobs(all_params)

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
            pipeline |= library_jobs(
                library,
                all_params[library],
                push_to_test_optimization=push_to_test_optimization,
                binaries_artifact_path=binaries_artifact_path,
                binaries_artifacts=binaries_artifacts,
                target_branches=target_branches,
            )

        chunk_file.write_text(to_yaml(pipeline))


def _endtoend_jobs(all_params: Mapping[str, dict]) -> Iterator[dict]:
    """End-to-end jobs of the params, in a deterministic order: libraries in the given order, then jobs in the order
    of the params (sorted by weblog by compute-workflow-parameters.py).
    """
    for params in all_params.values():
        yield from params.get("endtoend_defs", {}).get("parallel_jobs", [])


def _scenarios_times(job_def: dict) -> dict[str, float]:
    """Expected execution time of each scenario of an end-to-end job of the params."""
    scenarios: list[str] = job_def["scenarios"]
    times: dict[str, float] = job_def.get("scenarios_times") or {}
    # params computed without scenarios times: share the expected time of the job between its scenarios
    default_time = float(job_def.get("expected_job_time", len(scenarios))) / max(len(scenarios), 1)
    return {scenario: float(times.get(scenario, default_time)) for scenario in scenarios}


def _set_endtoend_jobs(all_params: Mapping[str, dict], jobs_of: Mapping[int, list[dict]]) -> None:
    """Replace each end-to-end job of the params by the jobs in jobs_of[id(job)], numbered for each weblog."""
    for params in all_params.values():
        endtoend_defs = params.get("endtoend_defs")
        if not endtoend_defs:
            continue
        jobs = [job for job_def in endtoend_defs["parallel_jobs"] for job in jobs_of[id(job_def)]]
        instances: dict[str, int] = {}
        for job in jobs:
            job["weblog_instance"] = instances[job["weblog"]] = instances.get(job["weblog"], 0) + 1
        endtoend_defs["parallel_jobs"] = jobs


def _run_job(job_def: dict, scenarios: list[str], times: Mapping[str, float]) -> dict:
    job = {key: value for key, value in job_def.items() if key != "scenarios_times"}
    job["scenarios"] = sorted(scenarios)
    job["expected_job_time"] = sum(times[scenario] for scenario in scenarios)
    return job


def split_scenarios_into_jobs(all_params: Mapping[str, dict]) -> None:
    """Default, without a number of jobs: each scenario gets its own run job."""
    jobs_of: dict[int, list[dict]] = {}
    for job_def in _endtoend_jobs(all_params):
        times = _scenarios_times(job_def)
        jobs_of[id(job_def)] = [_run_job(job_def, [scenario], times) for scenario in job_def["scenarios"]]
    _set_endtoend_jobs(all_params, jobs_of)


class _WeblogJobs:
    """Groupable scenarios of a weblog (an end-to-end job of the params), split into `count` run jobs."""

    def __init__(self, job_def: dict, times: dict[str, float]):
        self.job_def = job_def
        self.times = times
        self.longest_scenario_time = max(times.values())
        self.count = 0
        self.groups: list[list[str]] = []
        self.longest_job_time = 0.0
        self.add_job()

    def add_job(self) -> None:
        """Split the scenarios into one more job: each scenario, longest first, goes to the job with the lowest
        expected time (the first one if several have the same). Ties between scenarios are broken by name.
        """
        self.count += 1
        groups: list[list[str]] = [[] for _ in range(self.count)]
        group_times = [0.0] * self.count
        for scenario, time in sorted(self.times.items(), key=lambda item: (-item[1], item[0])):
            index = group_times.index(min(group_times))
            groups[index].append(scenario)
            group_times[index] += time
        self.groups = [group for group in groups if group]
        self.longest_job_time = max(group_times)

    def can_be_shortened(self) -> bool:
        """Whether another job may make its longest job shorter: not if it only runs its longest scenario."""
        return self.count < len(self.times) and self.longest_job_time > self.longest_scenario_time


class EndToEndScheduler:
    """Split the end-to-end scenarios of all libraries into run jobs of balanced length.

    A run job only runs scenarios of one weblog: so each weblog gets one job, then each additional job goes to the
    weblog with the longest job
    (the first one, in the order of _endtoend_jobs, if several have the same), as long as another job may make it
    shorter. Jobs are added until there are job_count of them, or until all of them fit in max_job_time: both stop
    the same sequence of steps, so the result only depends on the params and on the number of jobs it ends with.
    """

    def __init__(self, all_params: Mapping[str, dict]):
        self.all_params = all_params
        self.weblogs = [
            _WeblogJobs(job_def, _scenarios_times(job_def))
            for job_def in _endtoend_jobs(all_params)
            if job_def["scenarios"]
        ]

    @property
    def job_count(self) -> int:
        return sum(weblog.count for weblog in self.weblogs)

    def longest_weblog_to_shorten(self) -> _WeblogJobs | None:
        candidates = [weblog for weblog in self.weblogs if weblog.can_be_shortened()]
        # max() returns the first one of the candidates with the longest job
        return max(candidates, key=lambda weblog: weblog.longest_job_time, default=None)

    def schedule(self, *, job_count: int | None = None, max_job_time: float | None = None) -> int:
        """Rewrite the end-to-end jobs of the params, in place, and return the number of run jobs.

        Either (without any, each weblog gets as many jobs as may make its longest job shorter):
            job_count: number of jobs to use, at most (fewer if more would not make the longest job shorter)
            max_job_time: no job may be expected to last more, except jobs that can't be shortened (a scenario alone
                expected to last more), with as few jobs as possible
        """
        if job_count is not None and job_count < self.job_count:
            print(  # noqa: T201
                f"⚠️ {job_count} end-to-end jobs requested, but the scenarios of {len(self.weblogs)} weblogs can't "
                f"share a job: using {self.job_count}"
            )
        while weblog := self.longest_weblog_to_shorten():
            if job_count is not None and self.job_count >= job_count:
                break
            if max_job_time is not None and weblog.longest_job_time <= max_job_time:
                break
            weblog.add_job()
        self.write()
        return self.job_count

    def write(self) -> None:
        jobs_of: dict[int, list[dict]] = {id(job_def): [] for job_def in _endtoend_jobs(self.all_params)}
        for weblog in self.weblogs:
            jobs = [_run_job(weblog.job_def, group, weblog.times) for group in weblog.groups]
            # longest jobs first, so they start first
            jobs_of[id(weblog.job_def)] = sorted(jobs, key=lambda job: (-job["expected_job_time"], job["scenarios"]))
        _set_endtoend_jobs(self.all_params, jobs_of)


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
    "desired_execution_time": "SYSTEM_TESTS_DESIRED_EXECUTION_TIME",
    "endtoend_job_count": "SYSTEM_TESTS_ENDTOEND_JOB_COUNT",
    "push_to_test_optimization": "SYSTEM_TESTS_PUSH_TO_TEST_OPTIMIZATION",
    "skip_empty_scenario": "SYSTEM_TESTS_SKIP_EMPTY_SCENARIO",
    "binaries_artifacts": "BINARIES_ARTIFACTS",
    "binaries_artifact_path": "BINARIES_ARTIFACT_PATH",
    "split_pipeline": "SYSTEM_TESTS_SPLIT_PIPELINE",
    "pipeline_start_time": "SYSTEM_TESTS_PIPELINE_START_TIME",
    "library_weblog_scenarios": "LIBRARY_WEBLOG_SCENARIOS",
    # not SYSTEM_TESTS_DEV_MODE, read by conftest.py: as a pipeline variable, it would reach all the jobs of the
    # parent pipeline running pytest. The generated jobs get SYSTEM_TESTS_DEV_MODE (see child_pipeline_variables)
    "dev_mode": "SYSTEM_TESTS_E2E_DEV_MODE",
    "target_branch_map": "SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP",
}

COMPUTE_PARAMETERS_SCRIPT = "utils/scripts/compute-workflow-parameters.py"
SPLIT_PIPELINE_CHUNKS = 3  # must match the number of system_tests_e2e_run_pipeline_N jobs of main.yml


def _split(value: str, separators: str = ",") -> list[str]:
    """Split a list on any of *separators*, dropping empty items and duplicates, keeping order."""
    items = (item.strip() for item in re.split(f"[{re.escape(separators)}]", value))
    return list(dict.fromkeys(item for item in items if item))


class InputError(ValueError):
    """Invalid component input or pipeline variable, reported without a traceback by main()."""


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

    for name in ("parametric_job_count", "parametric_workers", "desired_execution_time", "endtoend_job_count"):
        value = getattr(resolved, name)
        try:
            setattr(resolved, name, int(value))
        except ValueError:
            raise InputError(f"{name}: expected an integer, got {value!r}") from None
    for name in ("push_to_test_optimization", "skip_empty_scenario", "split_pipeline", "dev_mode"):
        setattr(resolved, name, str(getattr(resolved, name)).lower() == "true")

    return resolved


def compute_params(library: str, inputs: argparse.Namespace, params_dir: Path) -> None:
    """Write params_<library>.json, the scenarios/weblogs/parametric matrix of one library."""
    _compute_workflow_parameters(
        library,
        inputs,
        params_dir / f"params_{library}.json",
        scenarios=inputs.scenarios,
        scenario_groups=inputs.scenario_groups,
        excluded_scenarios=inputs.excluded_scenarios,
        weblogs=inputs.weblogs,
    )


def _compute_workflow_parameters(
    library: str,
    inputs: argparse.Namespace,
    output: Path,
    *,
    scenarios: list[str],
    scenario_groups: list[str],
    excluded_scenarios: list[str],
    weblogs: list[str],
) -> None:
    command = [
        sys.executable,
        COMPUTE_PARAMETERS_SCRIPT,
        library,
        "--format",
        "json",
        "--scenarios",
        ",".join(scenarios),
        "--groups",
        ",".join(scenario_groups),
        "--excluded-scenarios",
        ",".join(excluded_scenarios),
        "--weblogs",
        ",".join(weblogs),
        "--explicit-binaries-artifact",
        inputs.binaries_artifacts,
        "--parametric-job-count",
        str(inputs.parametric_job_count),
        "--parametric-workers",
        str(inputs.parametric_workers),
        # ci_environment dev: binaries_artifact and weblogs of the dev mode, like the GitHub workflows
        *(("--system-tests-dev-mode", "true") if inputs.dev_mode else ()),
        # one end-to-end job per weblog (no --desired-execution-time), with the time of each scenario, split into run
        # jobs by build()
        "--include-scenarios-times",
        "--output",
        str(output),
    ]
    returncode = subprocess.run(command, check=False).returncode
    if returncode != 0:
        sys.exit(returncode)


# library_weblog_scenarios input: JSON object {library: {weblog: [entry, ...]}}, where each entry is either a
# scenario (uppercase, e.g. DEFAULT) or a scenario group (lowercase, e.g. appsec). PARAMETRIC is not weblog-bound:
# it is enabled with the "parametric" key, e.g. {"python": {"parametric": [], "flask-poc": ["DEFAULT"]}}
# (["PARAMETRIC"] is also accepted as value).
PARAMETRIC_KEY = "parametric"
PARAMETRIC_SCENARIO = "PARAMETRIC"


def parse_library_weblog_scenarios(value: str) -> dict[str, dict[str, list[str]]]:
    """Parse and check the library_weblog_scenarios input (its format is checked by validate_param_env.py)."""
    mapping: dict[str, dict[str, list[str]]] = json.loads(value)
    for library, weblog_scenarios in mapping.items():
        parametric_entries = weblog_scenarios.get(PARAMETRIC_KEY)
        if parametric_entries not in (None, [], [PARAMETRIC_SCENARIO]):
            raise ValueError(
                f'{library}: "{PARAMETRIC_KEY}" expects [] or ["{PARAMETRIC_SCENARIO}"], got {parametric_entries}'
            )
        for weblog, entries in weblog_scenarios.items():
            if weblog != PARAMETRIC_KEY and PARAMETRIC_SCENARIO in entries:
                raise ValueError(f'{library}/{weblog}: {PARAMETRIC_SCENARIO} must be listed as "{PARAMETRIC_KEY}": []')
        if not weblog_scenarios:
            raise ValueError(f"{library}: no weblog listed")
    return mapping


def split_weblog_entries(entries: list[str], excluded_scenarios: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Return the scenarios, scenario groups and excluded scenarios of one weblog of library_weblog_scenarios.

    Explicitly listed scenarios are removed from excluded_scenarios, so the exclusion only applies to
    scenarios coming from groups.
    """
    scenarios = sorted({entry for entry in entries if not entry.islower()})
    groups = sorted({entry for entry in entries if entry.islower()})
    excluded = [name for name in excluded_scenarios if name not in scenarios]
    return scenarios, groups, excluded


def merge_params(weblog_params: list[dict], parametric_params: dict | None) -> dict:
    """Merge params computed for each weblog of a library, and for its parametric scenario.

    Only the parts used by library_jobs() are merged: end-to-end jobs and weblogs are concatenated from the
    weblog params, and parametric comes from the parametric params only (disabled if there are none).
    Other parts (miscs, SSI matrices...) are taken from the first params.
    """
    all_params = weblog_params + ([parametric_params] if parametric_params is not None else [])
    result = dict(all_params[0])
    parallel_jobs = [job for p in weblog_params for job in p["endtoend_defs"]["parallel_jobs"]]
    result["endtoend_defs"] = {
        "parallel_enable": len(parallel_jobs) > 0,
        "parallel_weblogs": [w for p in weblog_params for w in p["endtoend_defs"]["parallel_weblogs"]],
        "parallel_jobs": parallel_jobs,
    }
    if parametric_params is not None:
        result["parametric"] = parametric_params["parametric"]
    else:
        result["parametric"] = {**result["parametric"], "enable": False, "scenarios": []}
    return result


def compute_mapped_params(
    library: str, weblog_scenarios: dict[str, list[str]], inputs: argparse.Namespace, params_dir: Path
) -> None:
    """Write params_<library>.json for a library of library_weblog_scenarios.

    compute-workflow-parameters.py is called once per weblog, with only the scenarios/groups of that weblog,
    plus once for parametric, and the results are merged.
    """
    weblog_params = []
    for weblog, entries in weblog_scenarios.items():
        if weblog == PARAMETRIC_KEY:
            continue
        scenarios, groups, excluded = split_weblog_entries(entries, inputs.excluded_scenarios)
        output = params_dir / f"params_{library}__{weblog}.json"
        _compute_workflow_parameters(
            library,
            inputs,
            output,
            scenarios=scenarios,
            scenario_groups=groups,
            excluded_scenarios=excluded,
            weblogs=[weblog],
        )
        params = json.loads(output.read_text())
        if not params["endtoend_defs"]["parallel_jobs"]:
            print(  # noqa: T201
                f"⚠️ {library}/{weblog}: no job to run, the weblog does not exist or "
                f"does not support any of {', '.join(entries)}"
            )
        weblog_params.append(params)

    parametric_params = None
    if PARAMETRIC_KEY in weblog_scenarios:
        output = params_dir / f"params_{library}__{PARAMETRIC_KEY}.json"
        _compute_workflow_parameters(
            library,
            inputs,
            output,
            scenarios=[PARAMETRIC_SCENARIO],
            scenario_groups=[],
            excluded_scenarios=[],
            weblogs=[],
        )
        parametric_params = json.loads(output.read_text())
        if not parametric_params["parametric"]["enable"]:
            print(f"⚠️ {library}: {PARAMETRIC_SCENARIO} is not supported, no job to run")  # noqa: T201

    params = merge_params(weblog_params, parametric_params)
    (params_dir / f"params_{library}.json").write_text(json.dumps(params))


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
    parser.add_argument(
        "--desired-execution-time",
        default="-1",
        help="In seconds. If positive, the number of end-to-end run jobs is computed so that they are expected to "
        "last at most this time, then scenarios are split between them like with --endtoend-job-count. Otherwise, "
        "each scenario runs in its own job",
    )
    parser.add_argument(
        "--endtoend-job-count",
        default="0",
        help="If positive, the end-to-end scenarios of all libraries are split between this number of run jobs "
        "(runners), of balanced expected length. Can't be used with --desired-execution-time",
    )
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
    parser.add_argument(
        "--library-weblog-scenarios",
        default="",
        help='JSON object {library: {weblog: [scenario or group, ...]}}, e.g. {"python": {"flask-poc": ["DEFAULT"]}}. '
        "Can be combined with --libraries/--scenarios/--scenario-groups/--weblogs, for other libraries",
    )
    parser.add_argument(
        "--dev-mode",
        default="false",
        help="Test the dev version of the agent and of the libraries, fetched by load-binary.sh (like the GitHub "
        "workflows dev mode). Can't be used with --binaries-artifacts/--binaries-artifact-path",
    )
    parser.add_argument(
        "--target-branch-map",
        default="",
        help='Dev mode only: JSON object {library or "agent": branch} of the branches to fetch the dev binaries '
        'from, instead of main/master, e.g. {"python": "my-branch"}',
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
        # read by conftest.py, like in the GitHub workflows: only in dev mode, to keep the pipeline unchanged otherwise
        **({"SYSTEM_TESTS_DEV_MODE": "true", "SYSTEM_TESTS_REPORT_ENVIRONMENT": "dev"} if inputs.dev_mode else {}),
    }


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    environ = os.environ if environ is None else environ
    try:
        inputs = resolve_inputs(parse_args(argv), environ)
    except InputError as error:
        print(f"❌ {error}", file=sys.stderr)  # noqa: T201
        return 1
    output_dir = Path(inputs.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping: dict[str, dict[str, list[str]]] = {}
    if inputs.library_weblog_scenarios:
        # libraries/scenarios/scenarios_groups/weblogs may be used alongside library_weblog_scenarios, for other
        # libraries than the ones of library_weblog_scenarios
        if (inputs.scenarios or inputs.scenario_groups or inputs.weblogs) and not inputs.libraries:
            print(  # noqa: T201
                "❌ scenarios, scenarios_groups and weblogs need libraries when used with library_weblog_scenarios",
                file=sys.stderr,
            )
            return 1
        mapping = parse_library_weblog_scenarios(inputs.library_weblog_scenarios)
        if both := sorted(set(inputs.libraries) & set(mapping)):
            print(  # noqa: T201
                f"❌ {', '.join(both)}: listed in both libraries and library_weblog_scenarios",
                file=sys.stderr,
            )
            return 1
        inputs.libraries = [*inputs.libraries, *mapping]

    target_branches: dict[str, str] | None = None
    if inputs.dev_mode:
        try:
            target_branches = check_dev_mode(inputs)
        except InputError as error:
            print(f"❌ {error}", file=sys.stderr)  # noqa: T201
            return 1
    elif inputs.target_branch_map:
        print("❌ target_branch_map can only be used in dev mode", file=sys.stderr)  # noqa: T201
        return 1

    if inputs.desired_execution_time > 0 and inputs.endtoend_job_count > 0:
        print(  # noqa: T201
            "❌ desired_execution_time and endtoend_job_count can't be used together", file=sys.stderr
        )
        return 1

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
            if library in mapping:
                compute_mapped_params(library, mapping[library], inputs, params_dir)
            else:
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
        endtoend_job_count=inputs.endtoend_job_count,
        desired_execution_time=inputs.desired_execution_time,
        target_branches=target_branches,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Parametric job: run one group of the PARAMETRIC scenario, split across several jobs.

Environment:
    SYSTEM_TESTS_PARAMETRIC_GROUP: 1-based index of the group run by this job
    SYSTEM_TESTS_PARAMETRIC_JOB_COUNT: number of groups the scenario is split into
    SYSTEM_TESTS_PARAMETRIC_WORKERS: maximum number of pytest-xdist workers
    TEST_LIBRARY: read by run.sh
    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH: optional, upstream binaries to copy into binaries/
"""

from utils.ci.gitlab.jobs import _common as ci


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    group = ci.env("SYSTEM_TESTS_PARAMETRIC_GROUP")
    job_count = ci.env("SYSTEM_TESTS_PARAMETRIC_JOB_COUNT")
    workers = ci.env("SYSTEM_TESTS_PARAMETRIC_WORKERS")

    with ci.section("run", f"Running PARAMETRIC (group {group}/{job_count})", collapsed=False):
        ci.tag_job("run")
        ci.copy_upstream_binaries()
        ci.traced(
            f"run {library} PARAMETRIC {group}",
            ["./run.sh", "PARAMETRIC", f"--maxprocesses={workers}", f"--splits={job_count}", f"--group={group}"],
            scenario="PARAMETRIC",
        )

    ci.emit_execution_time_metric()


if __name__ == "__main__":
    main()

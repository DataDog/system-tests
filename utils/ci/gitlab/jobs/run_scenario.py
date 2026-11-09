"""Run job: run one or several end-to-end scenarios against one weblog.

Environment:
    SYSTEM_TESTS_SCENARIOS: comma-separated list of scenarios to run, one after the other. Like the GitHub workflow,
        a failing scenario does not prevent the next ones from running, the job fails at the end
    SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED: "true" to run build.sh before run.sh. build.sh loads the weblog image saved
        by the build job if there is one (build_mode: prebuild), and builds it otherwise (build_mode: local)
    TEST_LIBRARY, SYSTEM_TESTS_WEBLOG: read by run.sh (TEST_LIBRARY by build.sh too)
    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH: optional, upstream binaries to copy into binaries/
"""

import os
import shutil
import sys
from pathlib import Path

from . import _common as ci


def import_built_binaries() -> None:
    """Move the artifacts of the build job ($CI_PROJECT_DIR/binaries) into binaries/, if the job has one."""
    source = ci.project_dir() / "binaries"
    if not source.is_dir():
        ci.log("No build job artifacts, the weblog image will be built by build.sh")
        return

    target = Path("binaries")
    target.mkdir(exist_ok=True)
    for item in source.iterdir():
        if not item.name.startswith("."):
            shutil.move(item, target / item.name)


def pull_images(library: str, weblog: str, scenario: str) -> int:
    """Pull the images of the scenario before running it, like the GitHub workflow: an image missing when the
    session starts its container is pulled then, which is slow and fails on any transient registry error.

    The images needed to build the weblog are not pulled: build.sh builds it with the mirror BuildKit builder, that
    pulls them itself.

    Return the return code of the first failing command, 0 if none failed.
    """
    compose_file = Path("compose.yaml")
    compose_file.unlink(missing_ok=True)
    returncode = ci.run(
        [
            "env",
            "PYTHONPATH=.",
            "python",
            "utils/scripts/get-image-list.py",
            scenario,
            f"--library={library}",
            f"--weblog={weblog}",
            f"--output={compose_file}",
        ],
        check=False,
    )
    if returncode:
        return returncode

    # the pull script fails on an empty compose file
    if not compose_file.is_file() or "image:" not in compose_file.read_text(encoding="utf-8"):
        ci.log("No image to pull")
        return 0

    return ci.run([".github/actions/pull_images/main.sh"], check=False)


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    weblog = ci.env("SYSTEM_TESTS_WEBLOG")
    scenarios = [scenario.strip() for scenario in ci.env("SYSTEM_TESTS_SCENARIOS").split(",") if scenario.strip()]
    build_required = os.environ.get("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "").lower() == "true"

    with ci.section("weblog_setup", "Setting up the weblog"):
        # jobs download either upstream binaries or the artifacts of a build job (see build_pipeline.py)
        ci.copy_upstream_binaries()
        if build_required:
            import_built_binaries()

    ci.tag_job("run")

    if build_required:
        # once for all scenarios: they all run against the same weblog
        with ci.section("weblog_build", "Building weblog", collapsed=False):
            ci.traced(f"build {library} {weblog}", ["./build.sh", "-i", "weblog", "-w", weblog])

    failures: dict[str, int] = {}
    for index, scenario in enumerate(scenarios):
        with ci.section(f"pull_images_{index}", f"Pulling docker images for {scenario}"):
            returncode = pull_images(library, weblog, scenario)

        if returncode == 0:
            with ci.section(f"scenario_run_{index}", f"Running {scenario}", collapsed=False):
                returncode = ci.traced(
                    f"run {library} {scenario} {weblog}", ["./run.sh", scenario], scenario=scenario, check=False
                )

        if returncode:
            failures[scenario] = returncode

    ci.emit_execution_time_metric()

    if failures:
        for scenario, returncode in failures.items():
            ci.log(f"ERROR: {scenario} failed with exit code {returncode}")
        # exit code of the first failure: it may trigger a retry of the job (see child-pipeline.yml)
        sys.exit(next(iter(failures.values())))


if __name__ == "__main__":
    main()

"""Run job: run one end-to-end scenario against one weblog.

Environment:
    SYSTEM_TESTS_SCENARIO: scenario to run
    SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED: "true" if the weblog image comes from a build job of this pipeline
    TEST_LIBRARY, SYSTEM_TESTS_WEBLOG: read by run.sh (TEST_LIBRARY by build.sh too)
    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH: optional, upstream binaries to copy into binaries/
"""

import os
import shutil
from pathlib import Path

from . import _common as ci


def import_built_binaries() -> None:
    """Move the artifacts of the build job ($CI_PROJECT_DIR/binaries) into binaries/."""
    target = Path("binaries")
    target.mkdir(exist_ok=True)
    for item in (ci.project_dir() / "binaries").iterdir():
        if not item.name.startswith("."):
            shutil.move(item, target / item.name)


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    weblog = ci.env("SYSTEM_TESTS_WEBLOG")
    scenario = ci.env("SYSTEM_TESTS_SCENARIO")
    build_required = os.environ.get("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "").lower() == "true"

    with ci.section("weblog_setup", "Setting up the weblog"):
        if build_required:
            import_built_binaries()
        else:
            ci.copy_upstream_binaries()

    with ci.section("scenario_run", "Running scenario", collapsed=False):
        ci.tag_job("run")
        if build_required:
            # loads the weblog image saved in binaries/ by the build job
            ci.traced(f"build {library} {weblog}", ["./build.sh", "-i", "weblog", "-w", weblog])
        ci.traced(f"run {library} {scenario} {weblog}", ["./run.sh", scenario], scenario=scenario)

    ci.emit_execution_time_metric()


if __name__ == "__main__":
    main()

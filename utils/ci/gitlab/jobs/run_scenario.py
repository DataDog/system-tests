"""Run job: run one end-to-end scenario against one weblog.

Environment:
    SYSTEM_TESTS_SCENARIO: scenario to run
    SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED: "true" to run build.sh before run.sh. build.sh loads the weblog image saved
        by the build job if there is one (build_mode: prebuild), and builds it otherwise (build_mode: local)
    TEST_LIBRARY, SYSTEM_TESTS_WEBLOG: read by run.sh (TEST_LIBRARY by build.sh too)
    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH: optional, upstream binaries to copy into binaries/
"""

import os
import shutil
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


def pull_images(library: str, weblog: str, scenario: str) -> None:
    """Pull the images of the scenario before running it, like the GitHub workflow: an image missing when the
    session starts its container is pulled then, which is slow and fails on any transient registry error.

    To call once binaries/ is set up: the images needed to build the weblog are skipped when it's prebuilt.
    """
    compose_file = Path("compose.yaml")
    ci.run(
        [
            "env",
            "PYTHONPATH=.",
            "python",
            "utils/scripts/get-image-list.py",
            scenario,
            f"--library={library}",
            f"--weblog={weblog}",
            f"--output={compose_file}",
        ]
    )

    # the pull script fails on an empty compose file
    if not compose_file.is_file() or "image:" not in compose_file.read_text(encoding="utf-8"):
        ci.log("No image to pull")
        return

    ci.run([".github/actions/pull_images/main.sh"])


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    weblog = ci.env("SYSTEM_TESTS_WEBLOG")
    scenario = ci.env("SYSTEM_TESTS_SCENARIO")
    build_required = os.environ.get("SYSTEM_TESTS_WEBLOG_BUILD_REQUIRED", "").lower() == "true"

    with ci.section("weblog_setup", "Setting up the weblog"):
        # jobs download either upstream binaries or the artifacts of a build job (see build_pipeline.py)
        ci.copy_upstream_binaries()
        if build_required:
            import_built_binaries()

    with ci.section("pull_images", "Pulling docker images"):
        pull_images(library, weblog, scenario)

    with ci.section("scenario_run", "Running scenario", collapsed=False):
        ci.tag_job("run")
        if build_required:
            ci.traced(f"build {library} {weblog}", ["./build.sh", "-i", "weblog", "-w", weblog])
        ci.traced(f"run {library} {scenario} {weblog}", ["./run.sh", scenario], scenario=scenario)

    ci.emit_execution_time_metric()


if __name__ == "__main__":
    main()

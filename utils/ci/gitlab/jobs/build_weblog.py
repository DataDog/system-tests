"""Build job: build the weblog image and save it as an artifact for the run jobs.

Environment:
    TEST_LIBRARY, WEBLOG_VARIANT: read by build.sh
    SYSTEM_TESTS_BINARIES_ARTIFACT_PATH: optional, upstream binaries to copy into binaries/ before building
    SYSTEM_TESTS_DOCKER_AUTH: optional, log in to docker hub before building
"""

import shutil

from utils.ci.gitlab.jobs import _common as ci


def export_built_binaries() -> None:
    """Move binaries/ to $CI_PROJECT_DIR, where the build job artifacts are collected."""
    shutil.move("binaries", ci.project_dir() / "binaries")


def main() -> None:
    library = ci.env("TEST_LIBRARY")
    weblog = ci.env("WEBLOG_VARIANT")

    ci.docker_auth()
    ci.copy_upstream_binaries()

    with ci.section("build", "Building weblog", collapsed=False):
        ci.tag_job("build")
        ci.traced(f"build {library} {weblog}", ["./build.sh", "-i", "weblog", "--save-to-binaries"])
        export_built_binaries()


if __name__ == "__main__":
    main()

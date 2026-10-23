"""after_script of run jobs: upload the JUnit reports to Datadog Test Optimization.

Runs from the system-tests clone. The API key is read from $CI_PROJECT_DIR/dd_api_key.env, written by the
before_script of .system_tests_base (after_script does not inherit the environment of the job script).
"""

import os
from pathlib import Path

from utils.ci.gitlab.jobs import _common as ci


def read_dd_api_key(env_file: Path) -> str:
    for line in env_file.read_text().splitlines():
        if line.startswith("export DD_API_KEY="):
            return line.removeprefix("export DD_API_KEY=").strip()
    return ""


def main() -> None:
    with ci.section("test_optim", "Push to tests optimization"):
        reports = sorted(str(path) for path in Path().glob("logs*/reportJunit.xml"))
        if not reports:
            ci.log("No JUnit report found, nothing to upload")
            return

        os.environ["DD_API_KEY"] = read_dd_api_key(ci.project_dir() / "dd_api_key.env")
        ci.run(["dd-sts", "debug"])
        ci.run(
            [
                "datadog-ci",
                "junit",
                "upload",
                *reports,
                "--service",
                "system-tests",
                "--env",
                "ci",
                "--xpath-tag",
                "test.codeowners=/testcase/properties/property[@name='test.codeowners']",
            ]
        )


if __name__ == "__main__":
    main()

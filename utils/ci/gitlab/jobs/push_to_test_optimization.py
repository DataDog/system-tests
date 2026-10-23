"""after_script of run jobs: upload the JUnit reports to Datadog Test Optimization.

Runs from the system-tests clone. after_script does not inherit the environment of the job script, so the API
key is fetched again: dd-sts exchanges the OIDC token of the job (DD_STS_OIDC_TOKEN) and passes DD_API_KEY to
the upload command only, the key is never written to disk.
"""

from pathlib import Path

from . import _common as ci

DD_STS_POLICY = "system-tests-gitlab"


def main() -> None:
    with ci.section("test_optim", "Push to tests optimization"):
        reports = sorted(str(path) for path in Path().glob("logs*/reportJunit.xml"))
        if not reports:
            ci.log("No JUnit report found, nothing to upload")
            return

        ci.run(["dd-sts", "debug"])
        ci.run(
            [
                *("dd-sts", "exchange", "--policy", DD_STS_POLICY, "--"),
                *("datadog-ci", "junit", "upload", *reports),
                *("--service", "system-tests", "--env", "ci"),
                "--xpath-tag",
                "test.codeowners=/testcase/properties/property[@name='test.codeowners']",
            ]
        )


if __name__ == "__main__":
    main()

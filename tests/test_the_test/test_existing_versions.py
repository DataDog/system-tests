import os
from textwrap import dedent
import requests
import pytest
from utils import scenarios, logger
from utils._context.component_version import Version
from utils.manifest import Manifest
from utils.manifest._internal.rule import match_condition


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("component", "github_repo"),
    [
        # ("agent", "datadog-agent"),
        # ("cpp", "dd-trace-cpp"),
        # ("cpp_httpd", "httpd-datadog"),
        # ("cpp_nginx", "nginx-datadog"),
        # dd-trace-dotnet: GH releases.
        # But this repo use production versions, for their master branch and they are used to declare production
        # versions in manifest, so we cannot really yet activate the safe guard
        # ("dotnet", "dd-trace-dotnet"),
        # ("golang", "dd-trace-go"),  # GH releases
        ("java", "dd-trace-java"),  # GH releases
        # ("nodejs", "dd-trace-js"),
        # ("python", "dd-trace-py"),  # GH releases
        # ("php", "dd-trace-php"),
        # ("ruby", "dd-trace-rb"),
    ],
)
def test_existing_version(component: str, github_repo: str):
    # Prevent form using a version that does not exist
    # This use case leads to test not being activated
    # and thus not being run, which is not what we want.

    manifest_data = Manifest.parse()

    existing_versions = get_github_releases(owner="DataDog", repo=github_repo)

    matched = {}
    for nodeid, conditions in manifest_data.items():
        for condition in conditions:
            if condition["component"] != component:
                continue
            if "component_version" not in condition and "excluded_component_version" not in condition:
                continue
            matched[(nodeid, str(condition))] = 0
            for version in existing_versions:
                if match_condition(condition, component, version, None, version, version, version):
                    count = matched.get((nodeid, str(condition))) or 0
                    matched[(nodeid, str(condition))] += 1

    unmatched = []
    all_matched = []
    for match, count in matched.items():
        if count == 0:
            unmatched.append(match)
        if count == len(existing_versions):
            all_matched.append(match)

    assert not all_matched, dedent(f"""
        The following conditions are matched by all existing versions:
            {all_matched}
        This is likely to originate from an error in the version number used in the
        declaration of those conditions in the manifest file.
    """)
    logger.warning(
        dedent(f"""
        The following conditions are not matched by any existing versions:
            {unmatched}
        This might originate from an error in the version number used in the
        declaration of those conditions in the manifest file.
    """)
    )


def get_github_releases(owner: str, repo: str) -> list[Version]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {}
    if "GITHUB_TOKEN" in os.environ:
        logger.debug("Using GITHUB_TOKEN for GitHub API authentication")
        headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"

    versions = []
    page = 1

    while True:
        response = requests.get(url, headers=headers, params={"per_page": 100, "page": page}, timeout=10)
        if response.status_code != 200:
            raise Exception(f"GitHub API error: {response.status_code} - {response.text}")

        page_data = response.json()
        if not page_data:
            break

        versions.extend([release["tag_name"] for release in page_data])
        page += 1

    result = []

    for version in versions:
        try:
            result.append(Version(version.replace("v", "")))
        except ValueError:
            logger.warning(f"github releases for {owner}/{repo} ships an unvalid version: {version}")

    return sorted(result)

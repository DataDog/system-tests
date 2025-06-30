import os
import requests
import pytest
from utils import scenarios, logger
from utils._context.component_version import ComponentVersion, Version
from manifests.parser.core import load as load_manifests


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
    from utils._decorators import SKIP_DECLARATIONS

    declared_versions = ComponentVersion.known_versions[component].copy()  # copy to avoid modifying the original

    manifests = load_manifests()

    for component_versions in manifests.values():  # the key is nodid, we ignore it
        if component not in component_versions:
            continue

        raw_declarations = component_versions[component]

        if isinstance(raw_declarations, dict):
            declarations = list(raw_declarations.values())
        elif raw_declarations is None:
            declarations = []
        else:
            declarations = [raw_declarations]

        for declaration in declarations:
            if declaration in SKIP_DECLARATIONS:
                pass
            elif declaration.startswith("v"):
                declared_versions.add(declaration[1:])
            else:
                # TODO : CustomSpec
                pass

    existing_versions = get_github_releases(owner="DataDog", repo=github_repo)

    assert all_declared_exist(sorted([Version(v) for v in declared_versions]), existing_versions)


def all_declared_exist(declared: list[Version], existing: list[Version]) -> bool:
    d = e = 0

    contains_error = True

    while d < len(declared) and e < len(existing):
        if declared[d].prerelease or declared[d].build:
            # TODO : check if this pre-release is sooner than the one exposed by default branch
            logger.debug(f"Skipping pre-release version: {declared[d]}")
            d += 1

        elif declared[d] == existing[e]:
            logger.info(f"Found declared version {declared[d]} in existing versions.")
            d += 1
            e += 1
        elif declared[d] > existing[e]:
            logger.debug(f"Found existing version {existing[e]}")
            e += 1
        else:  # declared[i] < existing[j]
            logger.error(f"Found declared version {declared[d]} that does not exists")
            contains_error = False
            d += 1

    # most common error: declare a version higher than the highest existing version
    while d < len(declared):
        if not declared[d].prerelease and not declared[d].build:
            logger.error(f"Found declared version {declared[d]} that does not exists")
            contains_error = False
        d += 1

    return contains_error


def get_github_releases(owner, repo) -> list[Version]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {}
    if "GITHUB_TOKEN" in os.environ:
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

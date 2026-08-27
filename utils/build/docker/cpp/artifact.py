from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver

REPOSITORY = "DataDog/dd-trace-cpp"
GIT_URL = "https://github.com/DataDog/dd-trace-cpp"


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository=REPOSITORY,
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="main",
        ),
    )
    entries = (text_entry("cpp-load-from-git", f"{GIT_URL}@{{library_branch.sha}}"),)


class Prod(SimpleTarget):
    inputs = (GitHubLatestReleaseResolver(name="release", repository=REPOSITORY),)
    entries = (text_entry("cpp-load-from-git", f"{GIT_URL}@{{release.tag_name}}"),)

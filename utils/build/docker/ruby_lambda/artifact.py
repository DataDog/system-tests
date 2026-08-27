from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/datadog-lambda-rb",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="main",
        ),
    )
    entries = (text_entry("ruby-lambda-load-from-git", "https://github.com/DataDog/datadog-lambda-rb@{library_branch.sha}"),)


class Prod(SimpleTarget):
    inputs = (GitHubLatestReleaseResolver(name="release", repository="DataDog/datadog-lambda-rb"),)
    entries = (text_entry("ruby-lambda-load-from-release", "{release.tag_name}"),)
